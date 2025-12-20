package main

import (
	"context"
	"fmt"
	"os"
	"os/signal"
	"syscall"
	"time"

	"tyvt-go/internal/client"
	"tyvt-go/internal/config"
	"tyvt-go/internal/database"
	"tyvt-go/internal/limiter"
	"tyvt-go/internal/models"
	"tyvt-go/internal/rotator"
	"tyvt-go/internal/stream"
)

// Version information
const (
	Version = "1.0.0"
	Module  = "tyvt-go"
)

func main() {
	// Load configuration
	cfg, err := config.LoadConfig()
	if err != nil {
		fmt.Fprintf(os.Stderr, "❌ Configuration error: %v\n", err)
		os.Exit(1)
	}

	// Print banner
	printBanner(cfg)

	// Validate configuration
	if err := cfg.Validate(); err != nil {
		cfg.Logger.Errorf("Configuration validation failed: %v", err)
		os.Exit(1)
	}

	// Print configuration
	cfg.PrintConfig()

	// Setup graceful shutdown
	setupGracefulShutdown(cfg)

	// Route to appropriate execution mode
	cfg.Logger.Infof("Starting execution in %s mode", cfg.Mode)

	var execErr error
	switch cfg.Mode {
	case config.ModeSimple:
		execErr = runSimpleMode(cfg)
	case config.ModeBatch:
		execErr = runBatchMode(cfg)
	case config.ModeStreaming:
		execErr = runStreamingMode(cfg)
	default:
		cfg.Logger.Errorf("Unknown execution mode: %s", cfg.Mode)
		os.Exit(1)
	}

	// Handle execution errors
	if execErr != nil {
		cfg.Logger.Errorf("Execution failed: %v", execErr)
		os.Exit(1)
	}

	cfg.Logger.Info("✅ TYVT scan completed successfully")
}

// runSimpleMode executes the scanner in simple mode (direct subdomain list)
func runSimpleMode(cfg *config.Config) error {
	cfg.Logger.Info("=== Simple Mode Execution ===")
	cfg.Logger.Infof("Target Subdomains: %d", len(cfg.TargetSubdomains))

	// Initialize components
	dbClient := database.NewSupabaseClient(cfg.SupabaseURL, cfg.SupabaseKey)
	repo := database.NewRepository(dbClient, cfg.Logger)
	vtClient := createVTClient(cfg)
	defer vtClient.Close()

	ctx, cancel := context.WithTimeout(context.Background(), cfg.ScanTimeout)
	defer cancel()

	// Process each subdomain
	var totalURLsDiscovered int
	var allDiscoveredURLs []models.DiscoveredURL

	for i, subdomain := range cfg.TargetSubdomains {
		cfg.Logger.Infof("🔍 Querying %d/%d: %s", i+1, len(cfg.TargetSubdomains), subdomain)

		result, err := vtClient.QueryDomain(ctx, subdomain)
		if err != nil {
			cfg.Logger.Warnf("⚠️  Failed to query %s: %v", subdomain, err)
			continue
		}

		if result.ResponseCode != 1 || len(result.UndetectedURLs) == 0 {
			cfg.Logger.Infof("   No undetected URLs for: %s", subdomain)
			continue
		}

		cfg.Logger.Infof("   ✅ Found %d undetected URLs", len(result.UndetectedURLs))
		totalURLsDiscovered += len(result.UndetectedURLs)

		// Convert to database models
		for _, u := range result.UndetectedURLs {
			allDiscoveredURLs = append(allDiscoveredURLs, models.DiscoveredURL{
				ScanJobID:    cfg.ScanJobID,
				AssetID:      cfg.AssetID,
				Subdomain:    subdomain,
				URL:          u.URL,
				Positives:    u.Positives,
				Total:        u.Total,
				ScanDate:     u.ScanDate,
				Source:       "virustotal",
				DiscoveredAt: time.Now(),
			})
		}
	}

	// Store all results
	if len(allDiscoveredURLs) > 0 {
		if err := repo.BatchInsertDiscoveredURLs(allDiscoveredURLs); err != nil {
			cfg.Logger.Errorf("Failed to store URLs: %v", err)
		}
	}

	cfg.Logger.Infof("✅ Simple mode completed: %d subdomains queried, %d URLs discovered",
		len(cfg.TargetSubdomains), totalURLsDiscovered)

	return nil
}

// runBatchMode executes the scanner in batch mode (fetch from database)
func runBatchMode(cfg *config.Config) error {
	cfg.Logger.Info("=== Batch Mode Execution ===")
	cfg.Logger.Infof("Batch ID: %s", cfg.BatchID)
	cfg.Logger.Infof("Batch Range: offset=%d, limit=%d", cfg.BatchOffset, cfg.BatchLimit)

	// Initialize components
	dbClient := database.NewSupabaseClient(cfg.SupabaseURL, cfg.SupabaseKey)
	repo := database.NewRepository(dbClient, cfg.Logger)
	vtClient := createVTClient(cfg)
	defer vtClient.Close()

	// Update scan job status
	_ = repo.UpdateScanJobStatus(cfg.ScanJobID, "running", map[string]interface{}{
		"started_at": time.Now(),
		"mode":       "batch",
		"batch_id":   cfg.BatchID,
	})

	// Fetch subdomains from database (from http_probes for best results)
	cfg.Logger.Infof("Fetching subdomains from database for asset %s", cfg.AssetID)
	subdomains, err := repo.GetHTTPProbesForAsset(cfg.AssetID, cfg.BatchOffset, cfg.BatchLimit)
	if err != nil {
		_ = repo.UpdateScanJobStatus(cfg.ScanJobID, "failed", map[string]interface{}{
			"error":     err.Error(),
			"failed_at": time.Now(),
		})
		return fmt.Errorf("failed to fetch subdomains: %w", err)
	}

	if len(subdomains) == 0 {
		cfg.Logger.Warn("No subdomains found for asset")
		_ = repo.UpdateScanJobStatus(cfg.ScanJobID, "completed", map[string]interface{}{
			"completed_at":   time.Now(),
			"urls_discovered": 0,
			"note":           "no subdomains available",
		})
		return nil
	}

	cfg.Logger.Infof("Retrieved %d subdomains", len(subdomains))

	ctx, cancel := context.WithTimeout(context.Background(), cfg.ScanTimeout)
	defer cancel()

	// Process each subdomain
	var totalURLsDiscovered int
	var allDiscoveredURLs []models.DiscoveredURL

	for i, subdomain := range subdomains {
		cfg.Logger.Infof("🔍 Querying %d/%d: %s", i+1, len(subdomains), subdomain)

		result, err := vtClient.QueryDomain(ctx, subdomain)
		if err != nil {
			cfg.Logger.Warnf("⚠️  Failed to query %s: %v", subdomain, err)
			continue
		}

		if result.ResponseCode != 1 || len(result.UndetectedURLs) == 0 {
			continue
		}

		cfg.Logger.Infof("   ✅ Found %d undetected URLs", len(result.UndetectedURLs))
		totalURLsDiscovered += len(result.UndetectedURLs)

		for _, u := range result.UndetectedURLs {
			allDiscoveredURLs = append(allDiscoveredURLs, models.DiscoveredURL{
				ScanJobID:    cfg.ScanJobID,
				AssetID:      cfg.AssetID,
				Subdomain:    subdomain,
				URL:          u.URL,
				Positives:    u.Positives,
				Total:        u.Total,
				ScanDate:     u.ScanDate,
				Source:       "virustotal",
				DiscoveredAt: time.Now(),
			})
		}
	}

	// Store all results
	if len(allDiscoveredURLs) > 0 {
		if err := repo.BatchInsertDiscoveredURLs(allDiscoveredURLs); err != nil {
			cfg.Logger.Errorf("Failed to store URLs: %v", err)
		}
	}

	// Update scan job status
	_ = repo.UpdateScanJobStatus(cfg.ScanJobID, "completed", map[string]interface{}{
		"completed_at":      time.Now(),
		"subdomains_queried": len(subdomains),
		"urls_discovered":   totalURLsDiscovered,
	})

	cfg.Logger.Infof("✅ Batch mode completed: %d subdomains queried, %d URLs discovered",
		len(subdomains), totalURLsDiscovered)

	return nil
}

// runStreamingMode executes the scanner in streaming mode (consume from HTTPx)
func runStreamingMode(cfg *config.Config) error {
	cfg.Logger.Info("=== Streaming Mode Execution ===")
	cfg.Logger.Infof("Input Stream: %s", cfg.StreamInputKey)
	cfg.Logger.Infof("Output Stream: %s", cfg.StreamOutputKey)
	cfg.Logger.Infof("Consumer Group: %s", cfg.ConsumerGroup)

	// Initialize components
	dbClient := database.NewSupabaseClient(cfg.SupabaseURL, cfg.SupabaseKey)
	repo := database.NewRepository(dbClient, cfg.Logger)
	vtClient := createVTClient(cfg)
	defer vtClient.Close()

	// Update scan job status
	_ = repo.UpdateScanJobStatus(cfg.ScanJobID, "running", map[string]interface{}{
		"started_at": time.Now(),
		"mode":       "streaming",
	})

	// Initialize stream consumer
	consumer, err := stream.NewConsumer(cfg, repo, vtClient)
	if err != nil {
		_ = repo.UpdateScanJobStatus(cfg.ScanJobID, "failed", map[string]interface{}{
			"error":     err.Error(),
			"failed_at": time.Now(),
		})
		return fmt.Errorf("failed to initialize consumer: %w", err)
	}
	defer consumer.Close()

	// Ensure consumer group exists
	if err := consumer.EnsureConsumerGroup(); err != nil {
		_ = repo.UpdateScanJobStatus(cfg.ScanJobID, "failed", map[string]interface{}{
			"error":     err.Error(),
			"failed_at": time.Now(),
		})
		return fmt.Errorf("failed to create consumer group: %w", err)
	}

	// Start consuming
	cfg.Logger.Info("🌊 Starting stream consumption (waiting for subdomains from HTTPx)...")
	consumeResult, err := consumer.Consume()
	if err != nil {
		_ = repo.UpdateScanJobStatus(cfg.ScanJobID, "failed", map[string]interface{}{
			"error":     err.Error(),
			"failed_at": time.Now(),
		})
		return fmt.Errorf("stream consumption failed: %w", err)
	}

	// Update scan job status
	_ = repo.UpdateScanJobStatus(cfg.ScanJobID, "completed", map[string]interface{}{
		"completed_at":       time.Now(),
		"subdomains_received": consumeResult.SubdomainsReceived,
		"subdomains_queried": consumeResult.SubdomainsQueried,
		"urls_discovered":    consumeResult.URLsDiscovered,
		"urls_stored":        consumeResult.URLsStored,
		"processing_time":    consumeResult.ProcessingTime.String(),
	})

	cfg.Logger.Infof("✅ Streaming mode completed: %d subdomains queried, %d URLs discovered",
		consumeResult.SubdomainsQueried, consumeResult.URLsDiscovered)

	return nil
}

// createVTClient creates a new VirusTotal client with key rotation and rate limiting
func createVTClient(cfg *config.Config) *client.VirusTotalClient {
	rateLimiter := limiter.New(cfg.RateLimitDelay)
	keyRotator := rotator.NewKeyRotator(cfg.VTAPIKeys, cfg.RotationInterval)

	return client.NewVirusTotalClient(
		keyRotator,
		rateLimiter,
		cfg.ProxyURL,
		cfg.InsecureTLS,
	)
}

// setupGracefulShutdown handles interrupt signals
func setupGracefulShutdown(cfg *config.Config) {
	sigChan := make(chan os.Signal, 1)
	signal.Notify(sigChan, os.Interrupt, syscall.SIGTERM)

	go func() {
		sig := <-sigChan
		cfg.Logger.Warnf("Received signal: %v", sig)
		cfg.Logger.Info("Initiating graceful shutdown...")
		os.Exit(0)
	}()
}

// printBanner displays the module banner
func printBanner(cfg *config.Config) {
	banner := fmt.Sprintf(`
╔════════════════════════════════════════════════════════════╗
║           TYVT - VIRUSTOTAL DOMAIN SCANNER                 ║
║                  NeoBot-Net v2                             ║
╠════════════════════════════════════════════════════════════╣
║  Version: %-49s ║
║  Mode: %-52s ║
╚════════════════════════════════════════════════════════════╝
`, Version, cfg.Mode)

	fmt.Println(banner)
}


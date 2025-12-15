package main

import (
	"context"
	"fmt"
	"os"
	"os/signal"
	"syscall"
	"time"

	"katana-go/internal/config"
	"katana-go/internal/database"
	"katana-go/internal/scanner"
)

// Version information
const (
	Version = "1.0.0"
	Module  = "katana-go"
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
		cfg.Logger.Error("Configuration validation failed: %v", err)
		os.Exit(1)
	}

	// Print configuration
	cfg.PrintConfig()

	// Setup graceful shutdown
	setupGracefulShutdown(cfg)

	// Route to appropriate execution mode
	cfg.Logger.Info("Starting execution in %s mode", cfg.Mode)

	var execErr error
	switch cfg.Mode {
	case config.ModeSimple:
		execErr = runSimpleMode(cfg)
	case config.ModeBatch:
		execErr = runBatchMode(cfg)
	case config.ModeStreaming:
		execErr = runStreamingMode(cfg)
	default:
		cfg.Logger.Error("Unknown execution mode: %s", cfg.Mode)
		os.Exit(1)
	}

	// Handle execution errors
	if execErr != nil {
		cfg.Logger.Error("Execution failed: %v", execErr)
		os.Exit(1)
	}

	cfg.Logger.Info("✅ Katana scan completed successfully")
}

// runSimpleMode executes the scanner in simple mode
func runSimpleMode(cfg *config.Config) error {
	cfg.Logger.Info("=== Simple Mode Execution ===")
	cfg.Logger.Info("Target URLs: %d", len(cfg.TargetURLs))

	// 1. Initialize database client and repository
	dbClient := database.NewSupabaseClient(cfg.SupabaseURL, cfg.SupabaseKey)
	repo := database.NewRepository(dbClient, cfg.Logger)

	// 2. Update scan job status to "running"
	if err := repo.UpdateScanJobStatus(cfg.ScanJobID, "running", map[string]interface{}{
		"started_at": time.Now(),
		"mode":       "simple",
		"url_count":  len(cfg.TargetURLs),
	}); err != nil {
		cfg.Logger.Warn("Failed to update scan job status: %v", err)
	}

	// 3. Initialize scanner
	scanner, err := scanner.NewScanner(cfg, cfg.Logger)
	if err != nil {
		_ = repo.UpdateScanJobStatus(cfg.ScanJobID, "failed", map[string]interface{}{
			"error":     err.Error(),
			"failed_at": time.Now(),
		})
		return fmt.Errorf("failed to initialize scanner: %w", err)
	}
	defer scanner.Close()

	// 4. Perform crawl
	ctx := context.Background()
	cfg.Logger.Info("Starting crawl for %d URLs", len(cfg.TargetURLs))

	endpoints, err := scanner.Crawl(ctx, cfg.TargetURLs)
	if err != nil {
		_ = repo.UpdateScanJobStatus(cfg.ScanJobID, "failed", map[string]interface{}{
			"error":     err.Error(),
			"failed_at": time.Now(),
		})
		return fmt.Errorf("crawl failed: %w", err)
	}

	cfg.Logger.Info("Crawl completed, found %d endpoints", len(endpoints))

	// 5. Store results in database
	if err := repo.BatchUpsertEndpoints(endpoints); err != nil {
		_ = repo.UpdateScanJobStatus(cfg.ScanJobID, "failed", map[string]interface{}{
			"error":     err.Error(),
			"failed_at": time.Now(),
		})
		return fmt.Errorf("failed to store results: %w", err)
	}

	// 6. Update scan job status to "completed"
	if err := repo.UpdateScanJobStatus(cfg.ScanJobID, "completed", map[string]interface{}{
		"completed_at":    time.Now(),
		"endpoints_found": len(endpoints),
	}); err != nil {
		cfg.Logger.Warn("Failed to update scan job status: %v", err)
	}

	cfg.Logger.Info("✅ Simple mode completed: %d endpoints stored", len(endpoints))
	return nil
}

// runBatchMode executes the scanner in batch mode
func runBatchMode(cfg *config.Config) error {
	cfg.Logger.Info("=== Batch Mode Execution ===")
	cfg.Logger.Info("Batch ID: %s", cfg.BatchID)
	cfg.Logger.Info("Batch Range: offset=%d, limit=%d", cfg.BatchOffset, cfg.BatchLimit)

	// 1. Initialize database client and repository
	dbClient := database.NewSupabaseClient(cfg.SupabaseURL, cfg.SupabaseKey)
	repo := database.NewRepository(dbClient, cfg.Logger)

	// 2. Update scan job status to "running"
	if err := repo.UpdateScanJobStatus(cfg.ScanJobID, "running", map[string]interface{}{
		"started_at": time.Now(),
		"mode":       "batch",
		"batch_id":   cfg.BatchID,
	}); err != nil {
		cfg.Logger.Warn("Failed to update scan job status: %v", err)
	}

	// 3. Fetch seed URLs from http_probes table
	cfg.Logger.Info("Fetching seed URLs from database for asset %s", cfg.AssetID)
	seedURLs, err := repo.GetSeedURLsForAsset(cfg.AssetID, cfg.BatchOffset, cfg.BatchLimit)
	if err != nil {
		_ = repo.UpdateScanJobStatus(cfg.ScanJobID, "failed", map[string]interface{}{
			"error":     err.Error(),
			"failed_at": time.Now(),
		})
		return fmt.Errorf("failed to fetch seed URLs: %w", err)
	}

	if len(seedURLs) == 0 {
		cfg.Logger.Warn("No seed URLs found for asset %s", cfg.AssetID)
		_ = repo.UpdateScanJobStatus(cfg.ScanJobID, "completed", map[string]interface{}{
			"completed_at":    time.Now(),
			"endpoints_found": 0,
			"note":            "no seed URLs available",
		})
		return nil
	}

	cfg.Logger.Info("Retrieved %d seed URLs", len(seedURLs))

	// 4. Initialize scanner
	scanner, err := scanner.NewScanner(cfg, cfg.Logger)
	if err != nil {
		_ = repo.UpdateScanJobStatus(cfg.ScanJobID, "failed", map[string]interface{}{
			"error":     err.Error(),
			"failed_at": time.Now(),
		})
		return fmt.Errorf("failed to initialize scanner: %w", err)
	}
	defer scanner.Close()

	// 5. Perform crawl
	ctx := context.Background()
	cfg.Logger.Info("Starting batch crawl for %d seed URLs", len(seedURLs))

	endpoints, err := scanner.Crawl(ctx, seedURLs)
	if err != nil {
		_ = repo.UpdateScanJobStatus(cfg.ScanJobID, "failed", map[string]interface{}{
			"error":     err.Error(),
			"failed_at": time.Now(),
		})
		return fmt.Errorf("batch crawl failed: %w", err)
	}

	cfg.Logger.Info("Crawl completed, found %d endpoints", len(endpoints))

	// 6. Store results in database
	if err := repo.BatchUpsertEndpoints(endpoints); err != nil {
		_ = repo.UpdateScanJobStatus(cfg.ScanJobID, "failed", map[string]interface{}{
			"error":     err.Error(),
			"failed_at": time.Now(),
		})
		return fmt.Errorf("failed to store results: %w", err)
	}

	// 7. Update scan job status to "completed"
	if err := repo.UpdateScanJobStatus(cfg.ScanJobID, "completed", map[string]interface{}{
		"completed_at":    time.Now(),
		"endpoints_found": len(endpoints),
		"seed_urls":       len(seedURLs),
	}); err != nil {
		cfg.Logger.Warn("Failed to update scan job status: %v", err)
	}

	cfg.Logger.Info("✅ Batch mode completed: %d endpoints stored from %d seed URLs", len(endpoints), len(seedURLs))
	return nil
}

// runStreamingMode executes the scanner in streaming mode
func runStreamingMode(cfg *config.Config) error {
	cfg.Logger.Info("=== Streaming Mode Execution ===")
	cfg.Logger.Info("Input Stream: %s", cfg.StreamInputKey)
	cfg.Logger.Info("Consumer Group: %s", cfg.ConsumerGroup)

	// TODO: Phase 5 - Implement Redis Streams integration
	// For MVP, we'll implement Redis Streams in Phase 5
	// For now, fall back to batch mode

	cfg.Logger.Warn("Streaming mode not yet implemented (Phase 5), falling back to batch mode")
	return runBatchMode(cfg)
}

// setupGracefulShutdown handles interrupt signals
func setupGracefulShutdown(cfg *config.Config) {
	sigChan := make(chan os.Signal, 1)
	signal.Notify(sigChan, os.Interrupt, syscall.SIGTERM)

	go func() {
		sig := <-sigChan
		cfg.Logger.Warn("Received signal: %v", sig)
		cfg.Logger.Info("Initiating graceful shutdown...")

		// TODO: Add cleanup logic here
		// - Close database connections
		// - Close Redis connections
		// - Flush pending data
		// - Update batch job status

		cfg.Logger.Info("Shutdown complete")
		os.Exit(0)
	}()
}

// printBanner displays the module banner
func printBanner(cfg *config.Config) {
	banner := fmt.Sprintf(`
╔════════════════════════════════════════════════════════════╗
║              KATANA WEB CRAWLER MODULE                     ║
║                  NeoBot-Net v2                             ║
╠════════════════════════════════════════════════════════════╣
║  Version: %-49s ║
║  Mode: %-52s ║
╚════════════════════════════════════════════════════════════╝
`, Version, cfg.Mode)

	fmt.Println(banner)
}


package main

import (
	"encoding/json"
	"fmt"
	"log"
	"os"
	"strings"
)

// validateRequiredEnvVars validates that all required environment variables are set
func validateRequiredEnvVars(batchMode, streamingMode bool) error {
	// Required for all modes
	required := []string{
		"SCAN_JOB_ID",
		"USER_ID",
		"SUPABASE_URL",
		"SUPABASE_SERVICE_ROLE_KEY",
	}

	// Mode-specific requirements
	if streamingMode {
		required = append(required, "STREAM_OUTPUT_KEY", "REDIS_HOST", "REDIS_PORT")
	}

	if batchMode {
		required = append(required, "BATCH_ID", "ASSET_ID")
	} else if !streamingMode {
		// Simple mode requires DOMAINS
		required = append(required, "DOMAINS")
	}

	// Check for missing variables
	var missing []string
	for _, key := range required {
		if os.Getenv(key) == "" {
			missing = append(missing, key)
		}
	}

	if len(missing) > 0 {
		return fmt.Errorf("missing required environment variables: %v", missing)
	}

	return nil
}

func main() {
	// ============================================================
	// 1. DETERMINE EXECUTION MODE
	// ============================================================

	batchMode := os.Getenv("BATCH_MODE") == "true"
	streamingMode := os.Getenv("STREAMING_MODE") == "true"

	log.Println("🔍 Waymore Historical URL Discovery Container starting...")
	log.Println(strings.Repeat("=", 70))

	// Determine and log execution mode
	var executionMode string
	if streamingMode && batchMode {
		executionMode = "BATCH + STREAMING (Producer)"
	} else if streamingMode {
		executionMode = "STREAMING (Producer)"
	} else if batchMode {
		executionMode = "BATCH"
	} else {
		executionMode = "SIMPLE"
	}
	log.Printf("📋 Execution mode: %s", executionMode)

	// ============================================================
	// 2. VALIDATE ENVIRONMENT VARIABLES
	// ============================================================

	if err := validateRequiredEnvVars(batchMode, streamingMode); err != nil {
		log.Fatalf("❌ Environment validation failed: %v", err)
	}

	log.Println("✅ Environment validation passed")

	// Log configuration
	log.Println("\n📋 Configuration:")
	log.Printf("   SCAN_JOB_ID: %s", os.Getenv("SCAN_JOB_ID"))
	log.Printf("   USER_ID: %s", os.Getenv("USER_ID"))
	if assetID := os.Getenv("ASSET_ID"); assetID != "" {
		log.Printf("   ASSET_ID: %s", assetID)
	}
	if streamingMode {
		log.Printf("   STREAM_OUTPUT_KEY: %s", os.Getenv("STREAM_OUTPUT_KEY"))
		log.Printf("   REDIS: %s:%s", os.Getenv("REDIS_HOST"), os.Getenv("REDIS_PORT"))
	}

	// ============================================================
	// 3. ROUTE TO APPROPRIATE HANDLER
	// ============================================================

	var err error

	if batchMode {
		log.Println("\n🔄 Starting BATCH mode execution...")
		err = runBatchMode(streamingMode)
	} else if streamingMode {
		log.Println("\n🌊 Starting STREAMING mode execution...")
		err = runStreamingMode()
	} else {
		log.Println("\n🔧 Starting SIMPLE mode execution...")
		err = runSimpleMode()
	}

	if err != nil {
		log.Fatalf("❌ Execution failed: %v", err)
	}

	log.Println("\n" + strings.Repeat("=", 70))
	log.Println("✅ Waymore scan completed successfully!")
}

// runSimpleMode runs Waymore in simple mode with domains from environment
func runSimpleMode() error {
	log.Println("📋 Simple Mode: Historical URL Discovery")

	// Parse domains from JSON array
	domainsJSON := os.Getenv("DOMAINS")
	var domains []string
	if err := json.Unmarshal([]byte(domainsJSON), &domains); err != nil {
		return fmt.Errorf("failed to parse DOMAINS JSON: %w (value: %s)", err, domainsJSON)
	}

	// Filter out empty domains
	var validDomains []string
	for _, domain := range domains {
		trimmed := strings.TrimSpace(domain)
		if trimmed != "" {
			validDomains = append(validDomains, trimmed)
		}
	}

	if len(validDomains) == 0 {
		return fmt.Errorf("no valid domains found in DOMAINS array")
	}

	log.Printf("📊 Processing %d domains", len(validDomains))

	// Initialize scanner
	scanner := NewWaymoreScanner(
		os.Getenv("SCAN_JOB_ID"),
		os.Getenv("ASSET_ID"),
	)

	// Initialize Supabase client
	supabaseClient, err := NewSupabaseClient()
	if err != nil {
		return fmt.Errorf("failed to initialize Supabase client: %w", err)
	}

	// Process each domain
	var allURLs []DiscoveredURL
	for _, domain := range validDomains {
		log.Printf("\n🔍 Scanning: %s", domain)

		urls, err := scanner.ScanDomain(domain)
		if err != nil {
			log.Printf("   ⚠️  Error scanning %s: %v", domain, err)
			continue
		}

		allURLs = append(allURLs, urls...)
		log.Printf("   ✅ Found %d URLs", len(urls))
	}

	// Store to database
	if len(allURLs) > 0 {
		log.Printf("\n💾 Storing %d URLs to database...", len(allURLs))
		result, err := supabaseClient.BulkInsertHistoricalURLs(allURLs)
		if err != nil {
			log.Printf("⚠️  Database storage error: %v", err)
		} else {
			log.Printf("✅ Database storage complete:")
			log.Printf("   • Inserted: %d", result.InsertedCount)
			log.Printf("   • Updated: %d", result.UpdatedCount)
			log.Printf("   • Skipped: %d", result.SkippedCount)
		}
	}

	log.Printf("\n📊 SUMMARY: Discovered %d total URLs from %d domains", len(allURLs), len(validDomains))

	return nil
}

// runBatchMode runs Waymore in batch mode with domains from database
func runBatchMode(streamingEnabled bool) error {
	log.Println("📦 Batch Mode: Historical URL Discovery")

	// Load batch configuration
	batchConfig, err := loadBatchConfig()
	if err != nil {
		return fmt.Errorf("failed to load batch configuration: %w", err)
	}

	log.Printf("\n📋 Batch Configuration:")
	log.Printf("   Batch ID: %s", batchConfig.BatchID)
	log.Printf("   Asset ID: %s", batchConfig.AssetID)
	log.Printf("   Domains: %d", len(batchConfig.BatchDomains))

	// Initialize clients
	supabaseClient, err := NewSupabaseClient()
	if err != nil {
		return fmt.Errorf("failed to initialize Supabase client: %w", err)
	}

	// Update batch status to running
	if err := supabaseClient.UpdateBatchScanStatus(batchConfig.BatchID, "running", nil); err != nil {
		log.Printf("⚠️  Warning: Could not update batch status: %v", err)
	}

	// Initialize scanner
	scanner := NewWaymoreScanner(batchConfig.ScanJobID, batchConfig.AssetID)

	// Initialize streaming if enabled
	var streamProducer *RedisStreamProducer
	if streamingEnabled {
		streamProducer, err = NewRedisStreamProducer()
		if err != nil {
			return fmt.Errorf("failed to initialize Redis stream producer: %w", err)
		}
		defer streamProducer.Close()
		log.Printf("📤 Streaming enabled: %s", os.Getenv("STREAM_OUTPUT_KEY"))
	}

	// Process each domain
	var allURLs []DiscoveredURL
	var totalStreamed int

	for i, domain := range batchConfig.BatchDomains {
		log.Printf("\n🔍 [%d/%d] Scanning: %s", i+1, len(batchConfig.BatchDomains), domain)

		urls, err := scanner.ScanDomain(domain)
		if err != nil {
			log.Printf("   ⚠️  Error: %v", err)
			continue
		}

		allURLs = append(allURLs, urls...)
		log.Printf("   ✅ Found %d URLs", len(urls))

		// Stream URLs if enabled
		if streamProducer != nil && len(urls) > 0 {
			streamed, err := streamProducer.StreamURLs(urls)
			if err != nil {
				log.Printf("   ⚠️  Streaming error: %v", err)
			} else {
				totalStreamed += streamed
				log.Printf("   📤 Streamed %d URLs", streamed)
			}
		}
	}

	// Store to database
	if len(allURLs) > 0 {
		log.Printf("\n💾 Storing %d URLs to database...", len(allURLs))
		result, err := supabaseClient.BulkInsertHistoricalURLs(allURLs)
		if err != nil {
			log.Printf("⚠️  Database storage error: %v", err)
		} else {
			log.Printf("✅ Database storage complete:")
			log.Printf("   • Inserted: %d", result.InsertedCount)
			log.Printf("   • Updated: %d", result.UpdatedCount)
		}
	}

	// Send completion marker if streaming
	if streamProducer != nil {
		if err := streamProducer.SendCompletionMarker(len(allURLs)); err != nil {
			log.Printf("⚠️  Failed to send completion marker: %v", err)
		} else {
			log.Println("📤 Sent completion marker")
		}
	}

	// Update batch status to completed
	if err := supabaseClient.UpdateBatchScanStatus(batchConfig.BatchID, "completed", map[string]interface{}{
		"total_urls":      len(allURLs),
		"domains_scanned": len(batchConfig.BatchDomains),
		"urls_streamed":   totalStreamed,
	}); err != nil {
		log.Printf("⚠️  Warning: Could not update batch status: %v", err)
	}

	log.Printf("\n📊 BATCH SUMMARY:")
	log.Printf("   • Domains scanned: %d", len(batchConfig.BatchDomains))
	log.Printf("   • URLs discovered: %d", len(allURLs))
	if streamProducer != nil {
		log.Printf("   • URLs streamed: %d", totalStreamed)
	}

	return nil
}

// runStreamingMode runs Waymore in streaming-only mode
func runStreamingMode() error {
	log.Println("🌊 Streaming Mode: Historical URL Discovery")

	// Parse domains from environment
	domainsJSON := os.Getenv("DOMAINS")
	var domains []string
	if err := json.Unmarshal([]byte(domainsJSON), &domains); err != nil {
		return fmt.Errorf("failed to parse DOMAINS JSON: %w", err)
	}

	// Filter empty domains
	var validDomains []string
	for _, d := range domains {
		if trimmed := strings.TrimSpace(d); trimmed != "" {
			validDomains = append(validDomains, trimmed)
		}
	}

	if len(validDomains) == 0 {
		return fmt.Errorf("no valid domains found")
	}

	log.Printf("📊 Processing %d domains", len(validDomains))

	// Initialize scanner
	scanner := NewWaymoreScanner(
		os.Getenv("SCAN_JOB_ID"),
		os.Getenv("ASSET_ID"),
	)

	// Initialize Supabase client
	supabaseClient, err := NewSupabaseClient()
	if err != nil {
		return fmt.Errorf("failed to initialize Supabase client: %w", err)
	}

	// Initialize streaming producer
	streamProducer, err := NewRedisStreamProducer()
	if err != nil {
		return fmt.Errorf("failed to initialize Redis stream producer: %w", err)
	}
	defer streamProducer.Close()

	log.Printf("📤 Streaming to: %s", os.Getenv("STREAM_OUTPUT_KEY"))

	// Process each domain
	var allURLs []DiscoveredURL
	var totalStreamed int

	for i, domain := range validDomains {
		log.Printf("\n🔍 [%d/%d] Scanning: %s", i+1, len(validDomains), domain)

		urls, err := scanner.ScanDomain(domain)
		if err != nil {
			log.Printf("   ⚠️  Error: %v", err)
			continue
		}

		allURLs = append(allURLs, urls...)
		log.Printf("   ✅ Found %d URLs", len(urls))

		// Stream URLs
		if len(urls) > 0 {
			streamed, err := streamProducer.StreamURLs(urls)
			if err != nil {
				log.Printf("   ⚠️  Streaming error: %v", err)
			} else {
				totalStreamed += streamed
				log.Printf("   📤 Streamed %d URLs", streamed)
			}
		}
	}

	// Store to database
	if len(allURLs) > 0 {
		log.Printf("\n💾 Storing %d URLs to database...", len(allURLs))
		result, err := supabaseClient.BulkInsertHistoricalURLs(allURLs)
		if err != nil {
			log.Printf("⚠️  Database storage error: %v", err)
		} else {
			log.Printf("✅ Inserted: %d, Updated: %d", result.InsertedCount, result.UpdatedCount)
		}
	}

	// Send completion marker
	if err := streamProducer.SendCompletionMarker(len(allURLs)); err != nil {
		log.Printf("⚠️  Failed to send completion marker: %v", err)
	} else {
		log.Println("📤 Sent completion marker")
	}

	log.Printf("\n📊 STREAMING SUMMARY:")
	log.Printf("   • Domains: %d", len(validDomains))
	log.Printf("   • URLs discovered: %d", len(allURLs))
	log.Printf("   • URLs streamed: %d", totalStreamed)

	return nil
}

// loadBatchConfig loads batch configuration from environment and database
func loadBatchConfig() (*BatchConfig, error) {
	config := &BatchConfig{
		BatchID:   os.Getenv("BATCH_ID"),
		AssetID:   os.Getenv("ASSET_ID"),
		ScanJobID: os.Getenv("SCAN_JOB_ID"),
		UserID:    os.Getenv("USER_ID"),
	}

	// Parse batch domains from environment (if provided)
	if domainsJSON := os.Getenv("BATCH_DOMAINS"); domainsJSON != "" {
		if err := json.Unmarshal([]byte(domainsJSON), &config.BatchDomains); err != nil {
			return nil, fmt.Errorf("failed to parse BATCH_DOMAINS: %w", err)
		}
	}

	// Parse asset scan mapping (if provided)
	if mappingJSON := os.Getenv("ASSET_SCAN_MAPPING"); mappingJSON != "" {
		if err := json.Unmarshal([]byte(mappingJSON), &config.AssetScanMapping); err != nil {
			log.Printf("⚠️  Warning: Failed to parse ASSET_SCAN_MAPPING: %v", err)
		}
	}

	// If no domains provided, fetch from database
	if len(config.BatchDomains) == 0 {
		log.Println("📥 Fetching domains from database...")

		supabaseClient, err := NewSupabaseClient()
		if err != nil {
			return nil, fmt.Errorf("failed to initialize Supabase client: %w", err)
		}

		domains, err := supabaseClient.FetchApexDomains(config.AssetID)
		if err != nil {
			return nil, fmt.Errorf("failed to fetch domains: %w", err)
		}

		config.BatchDomains = domains
		log.Printf("📊 Fetched %d domains from database", len(domains))
	}

	config.TotalDomains = len(config.BatchDomains)

	return config, nil
}


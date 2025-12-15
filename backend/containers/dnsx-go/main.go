package main

import (
	"encoding/json"
	"fmt"
	"log"
	"os"
	"strings"
)

// validateRequiredEnvVars validates that all required environment variables are set
func validateRequiredEnvVars(batchMode bool) error {
	// Required for all modes
	required := []string{
		"SCAN_JOB_ID",
		"USER_ID",
		"SUPABASE_URL",
		"SUPABASE_SERVICE_ROLE_KEY",
	}

	// Mode-specific requirements
	if batchMode {
		required = append(required, "BATCH_ID", "ASSET_ID", "BATCH_OFFSET", "BATCH_LIMIT")
	} else {
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

	log.Printf("🚀 DNSX DNS Resolver Container starting...")
	
	// Determine and log execution mode
	var executionMode string
	if streamingMode {
		executionMode = "STREAMING (Consumer)"
	} else if batchMode {
		executionMode = "BATCH"
	} else {
		executionMode = "SIMPLE"
	}
	log.Printf("📋 Execution mode: %s", executionMode)

	// ============================================================
	// 2. VALIDATE ENVIRONMENT VARIABLES
	// ============================================================

	if err := validateRequiredEnvVars(batchMode); err != nil {
		log.Fatalf("❌ Environment validation failed: %v", err)
	}

	log.Println("✅ Environment validation passed")

	// ============================================================
	// 3. ROUTE TO APPROPRIATE HANDLER
	// ============================================================

	// Streaming mode has priority (modern producer-consumer pattern)
	if streamingMode {
		log.Println("🌊 Starting STREAMING mode execution (Consumer)...")
		if err := runStreamingMode(); err != nil {
			log.Fatalf("❌ Streaming mode failed: %v", err)
		}
		log.Println("✅ DNSX streaming consumer completed successfully")
		return
	}

	if batchMode {
		log.Println("🔄 Starting BATCH mode execution...")
		if err := runBatchMode(); err != nil {
			log.Fatalf("❌ Batch mode failed: %v", err)
		}
		log.Println("✅ DNSX batch scan completed successfully")
		return
	}

	log.Println("🔄 Starting SIMPLE mode execution...")
	if err := runSimpleMode(); err != nil {
		log.Fatalf("❌ Simple mode failed: %v", err)
	}
	log.Println("✅ DNSX simple scan completed successfully")
}

// runSimpleMode runs DNS resolution in simple mode (for testing)
func runSimpleMode() error {
	log.Println("📋 Simple Mode: DNS Resolution")

	// Parse domains from JSON array (not CSV)
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

	// Use validDomains for processing
	domains = validDomains

	// Initialize DNSX client
	dnsxClient, err := initializeDNSXClient()
	if err != nil {
		return fmt.Errorf("failed to initialize DNSX client: %v", err)
	}

	// Resolve DNS for all domains
	allRecords, err := resolveDomains(domains, dnsxClient)
	if err != nil {
		return fmt.Errorf("DNS resolution failed: %v", err)
	}

	log.Printf("\n" + strings.Repeat("=", 70))
	log.Printf("📊 SUMMARY: Found %d total DNS records", len(allRecords))
	log.Printf(strings.Repeat("=", 70))

	// Check if we should store to database
	supabaseURL := os.Getenv("SUPABASE_URL")
	if supabaseURL != "" {
		log.Println("\n💾 Storing results to database...")

		// Initialize Supabase client
		supabaseClient, err := NewSupabaseClient()
		if err != nil {
			log.Printf("⚠️  Warning: Could not initialize Supabase client: %v", err)
			log.Println("  Results will not be stored in database")
		} else {
			// Store results
			result, err := supabaseClient.BulkInsertDNSRecords(allRecords)
			if err != nil {
				log.Printf("⚠️  Warning: Failed to store results: %v", err)
			} else {
				log.Printf("✅ Database storage complete:")
				log.Printf("  • Inserted: %d", result.InsertedCount)
				log.Printf("  • Updated: %d", result.UpdatedCount)
				log.Printf("  • Skipped: %d", result.SkippedCount)
				log.Printf("  • Errors: %d", result.ErrorCount)
			}
		}
	} else {
		log.Println("\n💡 No SUPABASE_URL provided - skipping database storage")
	}

	log.Printf("\n✅ DNSX Simple Mode completed successfully!")
	return nil
}

// runBatchMode runs DNS resolution in batch mode with progress tracking
func runBatchMode() error {
	log.Println("📦 Batch Mode: DNS Resolution")
	log.Println(strings.Repeat("=", 70))

	// Load batch configuration
	batchConfig, err := loadBatchConfig()
	if err != nil {
		return fmt.Errorf("failed to load batch configuration: %v", err)
	}

	// Print configuration for debugging
	printBatchConfig(batchConfig)

	// Initialize clients
	log.Println("\n🔧 Initializing clients...")

	// Initialize DNSX client
	dnsxClient, err := initializeDNSXClient()
	if err != nil {
		return fmt.Errorf("failed to initialize DNSX client: %v", err)
	}

	// Initialize Supabase client
	supabaseClient, err := NewSupabaseClient()
	if err != nil {
		return fmt.Errorf("failed to initialize Supabase client: %v", err)
	}

	// Update batch status to "running"
	log.Println("\n🏁 Starting batch scan...")
	if err := supabaseClient.UpdateBatchScanStatus(batchConfig.BatchID, "running", map[string]interface{}{
		"started_at": fmt.Sprintf("%v", os.Getenv("TIMESTAMP")),
	}); err != nil {
		log.Printf("⚠️  Warning: Could not update batch status: %v", err)
	}

	// Resolve DNS for all domains
	allRecords, err := resolveDomains(batchConfig.BatchDomains, dnsxClient)
	if err != nil {
		// Mark batch as failed
		supabaseClient.UpdateBatchScanStatus(batchConfig.BatchID, "failed", map[string]interface{}{
			"error_message": err.Error(),
		})
		return fmt.Errorf("DNS resolution failed: %v", err)
	}

	// Assign scan job IDs, batch IDs, and asset IDs to records
	log.Println("\n📝 Assigning scan job IDs and asset IDs to DNS records...")

	// 🔍 DEBUG LOG: Checkpoint 2 - Track lookup success/failure
	lookupSuccessCount := 0
	lookupFailureCount := 0
	uniqueParentDomains := make(map[string]bool)
	var firstFailedLookup string
	var firstSuccessLookup string

	log.Printf("🔍 DEBUG [Checkpoint 2]: Starting scan_job_id assignment loop")
	log.Printf("   Total records to process: %d", len(allRecords))
	log.Printf("   Mapping size: %d", len(batchConfig.AssetScanMapping))

	for i := range allRecords {
		allRecords[i].BatchScanID = batchConfig.BatchID
		allRecords[i].AssetID = batchConfig.AssetID // Assign asset_id for direct queries

		// Track unique parent domains
		uniqueParentDomains[allRecords[i].ParentDomain] = true

		// Look up scan job ID from mapping (parent_domain -> scan_job_id)
		// Note: Mapping keys are parent domains (e.g., "epicgames.com"), not subdomains
		if scanJobID, ok := batchConfig.AssetScanMapping[allRecords[i].ParentDomain]; ok {
			allRecords[i].ScanJobID = scanJobID
			lookupSuccessCount++

			// Log first successful lookup
			if firstSuccessLookup == "" {
				firstSuccessLookup = allRecords[i].ParentDomain
				log.Printf("   ✅ First SUCCESS: ParentDomain='%s' → ScanJobID='%s'",
					allRecords[i].ParentDomain, scanJobID)
			}
		} else {
			lookupFailureCount++

			// Log first 3 failed lookups with details
			if lookupFailureCount <= 3 {
				log.Printf("   ❌ FAILED lookup #%d: ParentDomain='%s' NOT found in mapping",
					lookupFailureCount, allRecords[i].ParentDomain)
			}

			if firstFailedLookup == "" {
				firstFailedLookup = allRecords[i].ParentDomain
			}
		}
	}

	// 🔍 DEBUG LOG: Checkpoint 3 - Summary
	log.Printf("\n🔍 DEBUG [Checkpoint 3]: Assignment Summary")
	log.Printf("   ✅ Successful lookups: %d / %d (%.1f%%)",
		lookupSuccessCount, len(allRecords),
		float64(lookupSuccessCount)/float64(len(allRecords))*100)
	log.Printf("   ❌ Failed lookups: %d / %d (%.1f%%)",
		lookupFailureCount, len(allRecords),
		float64(lookupFailureCount)/float64(len(allRecords))*100)
	log.Printf("   📊 Unique ParentDomain values in records: %d", len(uniqueParentDomains))
	log.Printf("   📊 Unique keys in mapping: %d", len(batchConfig.AssetScanMapping))

	// Show all unique parent domains found in records
	log.Printf("   🔍 All unique ParentDomain values in DNS records:")
	for pd := range uniqueParentDomains {
		_, existsInMapping := batchConfig.AssetScanMapping[pd]
		if existsInMapping {
			log.Printf("     - '%s' ✅ (EXISTS in mapping)", pd)
		} else {
			log.Printf("     - '%s' ❌ (NOT in mapping)", pd)
		}
	}

	log.Printf("✅ Assigned asset_id=%s to %d DNS records", batchConfig.AssetID, len(allRecords))

	// Store results in database
	log.Println("\n💾 Storing results to database...")
	result, err := supabaseClient.BulkInsertDNSRecords(allRecords)
	if err != nil {
		// Mark batch as failed
		supabaseClient.UpdateBatchScanStatus(batchConfig.BatchID, "failed", map[string]interface{}{
			"error_message": fmt.Sprintf("Database storage failed: %v", err),
		})
		return fmt.Errorf("failed to store results: %v", err)
	}

	// Update batch status to "completed"
	log.Println("\n✅ Updating batch status to completed...")
	if err := supabaseClient.UpdateBatchScanStatus(batchConfig.BatchID, "completed", map[string]interface{}{
		"completed_domains": len(batchConfig.BatchDomains),
		"total_records":     len(allRecords),
	}); err != nil {
		log.Printf("⚠️  Warning: Could not update batch status: %v", err)
	}

	// Update individual scan job statuses
	log.Println("\n📊 Updating scan job statuses...")
	// Group records by scan job ID
	recordsByScanJob := make(map[string]int)
	for _, record := range allRecords {
		if record.ScanJobID != "" {
			recordsByScanJob[record.ScanJobID]++
		}
	}

	// Update each scan job
	for scanJobID, recordCount := range recordsByScanJob {
		if err := supabaseClient.UpdateScanJobStatus(scanJobID, "completed", map[string]interface{}{
			"dns_records_found": recordCount,
		}); err != nil {
			log.Printf("⚠️  Warning: Could not update scan job %s: %v", scanJobID, err)
		}
	}

	// Print final summary
	log.Println("\n" + strings.Repeat("=", 70))
	log.Println("📊 BATCH SCAN SUMMARY")
	log.Println(strings.Repeat("=", 70))
	log.Printf("Batch ID:         %s", batchConfig.BatchID)
	log.Printf("Domains Scanned:  %d", len(batchConfig.BatchDomains))
	log.Printf("DNS Records Found: %d", len(allRecords))
	log.Println()
	log.Println("Database Storage:")
	log.Printf("  • Inserted: %d", result.InsertedCount)
	log.Printf("  • Updated:  %d", result.UpdatedCount)
	log.Printf("  • Skipped:  %d", result.SkippedCount)
	log.Printf("  • Errors:   %d", result.ErrorCount)
	log.Println(strings.Repeat("=", 70))

	log.Printf("\n✅ DNSX Batch Mode completed successfully!")
	return nil
}

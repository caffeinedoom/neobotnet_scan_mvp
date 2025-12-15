package main

// HTTPx Scanner Container - v1.0.0
// Change detection test: Verifying GitHub Actions conditional build

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

	log.Printf("🚀 HTTPx HTTP Probe Container starting...")

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
	log.Println("📋 Simple Mode: HTTP Probing")

	// Parse subdomains from JSON array (not CSV)
	subdomainsJSON := os.Getenv("DOMAINS")
	var subdomains []string
	if err := json.Unmarshal([]byte(subdomainsJSON), &subdomains); err != nil {
		return fmt.Errorf("failed to parse DOMAINS JSON: %w (value: %s)", err, subdomainsJSON)
	}

	// Filter out empty subdomains
	var validSubdomains []string
	for _, subdomain := range subdomains {
		trimmed := strings.TrimSpace(subdomain)
		if trimmed != "" {
			validSubdomains = append(validSubdomains, trimmed)
		}
	}

	if len(validSubdomains) == 0 {
		return fmt.Errorf("no valid subdomains found in DOMAINS array")
	}

	log.Printf("📊 Processing %d subdomains", len(validSubdomains))

	// Get scan context (optional in simple mode)
	scanJobID := os.Getenv("SCAN_JOB_ID")
	if scanJobID == "" {
		scanJobID = "simple-mode"
	}
	assetID := os.Getenv("ASSET_ID")
	if assetID == "" {
		assetID = "simple-mode"
	}

	// Probe HTTP for all subdomains
	allProbes, err := probeHTTP(validSubdomains, scanJobID, assetID)
	if err != nil {
		return fmt.Errorf("HTTP probing failed: %v", err)
	}

	log.Printf("\n" + strings.Repeat("=", 70))
	log.Printf("📊 SUMMARY: Found %d total HTTP probes", len(allProbes))
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
			result, err := supabaseClient.BulkInsertHTTPProbes(allProbes)
			if err != nil {
				log.Printf("⚠️  Warning: Failed to store results: %v", err)
			} else {
				log.Printf("✅ Database storage complete:")
				log.Printf("  • Inserted: %d", result.InsertedCount)
				log.Printf("  • Skipped: %d", result.SkippedCount)
				log.Printf("  • Errors: %d", result.ErrorCount)
			}
		}
	} else {
		log.Println("\n💡 No SUPABASE_URL provided - skipping database storage")
	}

	log.Printf("\n✅ HTTPx Simple Mode completed successfully!")
	return nil
}

// runBatchMode runs HTTP probing in batch mode with progress tracking
// NOTE: Currently focused on streaming mode. Batch mode needs full implementation.
func runBatchMode() error {
	// TODO: Implement batch mode for HTTPx
	// For now, HTTPx module uses streaming mode exclusively
	return fmt.Errorf("batch mode not yet implemented for HTTPx - please use streaming mode with STREAMING_MODE=true")
}

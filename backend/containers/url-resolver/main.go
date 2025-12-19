package main

// URL Resolver Container - v1.0.0
// Resolves discovered URLs and stores enriched metadata in the urls table

import (
	"fmt"
	"log"
	"os"
)

// validateRequiredEnvVars validates that all required environment variables are set
func validateRequiredEnvVars(streamingMode bool) error {
	// Required for all modes
	required := []string{
		"SCAN_JOB_ID",
		"SUPABASE_URL",
		"SUPABASE_SERVICE_ROLE_KEY",
	}

	// Mode-specific requirements
	if streamingMode {
		required = append(required,
			"STREAM_INPUT_KEY",
			"REDIS_HOST",
			"REDIS_PORT",
		)
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

	streamingMode := os.Getenv("STREAMING_MODE") == "true"

	log.Printf("🔗 URL Resolver Container starting...")

	// Determine and log execution mode
	var executionMode string
	if streamingMode {
		executionMode = "STREAMING (Consumer)"
	} else {
		executionMode = "SIMPLE (Testing)"
	}
	log.Printf("📋 Execution mode: %s", executionMode)

	// ============================================================
	// 2. VALIDATE ENVIRONMENT VARIABLES
	// ============================================================

	if err := validateRequiredEnvVars(streamingMode); err != nil {
		log.Fatalf("❌ Environment validation failed: %v", err)
	}

	log.Println("✅ Environment validation passed")

	// ============================================================
	// 3. ROUTE TO APPROPRIATE HANDLER
	// ============================================================

	if streamingMode {
		log.Println("🌊 Starting STREAMING mode execution (Consumer)...")
		if err := runStreamingMode(); err != nil {
			log.Fatalf("❌ Streaming mode failed: %v", err)
		}
		log.Println("✅ URL Resolver streaming consumer completed successfully")
		return
	}

	// Simple mode for testing
	log.Println("🔄 Starting SIMPLE mode execution...")
	if err := runSimpleMode(); err != nil {
		log.Fatalf("❌ Simple mode failed: %v", err)
	}
	log.Println("✅ URL Resolver simple mode completed successfully")
}

// runSimpleMode runs URL resolution in simple mode (for testing)
func runSimpleMode() error {
	log.Println("📋 Simple Mode: URL Resolution Testing")

	// Get test URL from environment or use default
	testURL := os.Getenv("TEST_URL")
	if testURL == "" {
		testURL = "https://example.com"
	}

	log.Printf("🔍 Testing URL resolution for: %s", testURL)

	// Normalize and hash
	normalized, hash, err := NormalizeAndHash(testURL)
	if err != nil {
		return fmt.Errorf("failed to normalize URL: %w", err)
	}

	log.Printf("  • Normalized: %s", normalized)
	log.Printf("  • Hash: %s", hash)

	// Extract components
	domain, path, queryParams, fileExt, err := ParseURLComponents(testURL)
	if err != nil {
		return fmt.Errorf("failed to parse URL components: %w", err)
	}

	log.Printf("  • Domain: %s", domain)
	log.Printf("  • Path: %s", path)
	log.Printf("  • Query Params: %v", queryParams)
	if fileExt != nil {
		log.Printf("  • File Extension: %s", *fileExt)
	}

	// Probe the URL
	log.Println("\n🔍 Probing URL...")
	result := ProbeURL(testURL)

	if result.Error != nil {
		log.Printf("❌ Probe error: %v", result.Error)
	} else if result.IsAlive {
		log.Printf("✅ URL is alive!")
		log.Printf("  • Status Code: %d", result.StatusCode)
		log.Printf("  • Content Type: %s", result.ContentType)
		log.Printf("  • Content Length: %d", result.ContentLength)
		log.Printf("  • Response Time: %dms", result.ResponseTimeMs)
		log.Printf("  • Title: %s", result.Title)
		log.Printf("  • Webserver: %s", result.Webserver)
		log.Printf("  • Technologies: %v", result.Technologies)
		if result.FinalURL != "" && result.FinalURL != testURL {
			log.Printf("  • Final URL: %s", result.FinalURL)
		}
		if len(result.RedirectChain) > 0 {
			log.Printf("  • Redirect Chain: %v", result.RedirectChain)
		}
	} else {
		log.Printf("⚠️ URL did not respond")
	}

	log.Printf("\n✅ Simple mode completed successfully!")
	return nil
}


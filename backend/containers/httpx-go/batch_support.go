package main

import (
	"encoding/json"
	"fmt"
	"log"
	"os"
	"strconv"
	"strings"
	"time"
)

// BatchConfig represents batch processing configuration for DNS resolution
type BatchConfig struct {
	BatchID          string            `json:"batch_id"`
	ModuleType       string            `json:"module_type"` // "dnsx"
	AssetID          string            `json:"asset_id"`    // Asset ID for all records in this batch
	BatchDomains     []string          `json:"batch_domains"`
	AssetScanMapping map[string]string `json:"asset_scan_mapping"` // domain -> asset_scan_id
	TotalDomains     int               `json:"total_domains"`
	AllocatedCPU     int               `json:"allocated_cpu"`
	AllocatedMemory  int               `json:"allocated_memory"`
	// Batch pagination fields (for database-fetch mode)
	BatchOffset     int `json:"batch_offset"`     // Starting index for this batch
	BatchLimit      int `json:"batch_limit"`      // Number of domains to fetch
	TotalSubdomains int `json:"total_subdomains"` // Total subdomains available
}

// BatchDomainProgress tracks individual domain DNS resolution progress within a batch
type BatchDomainProgress struct {
	BatchID      string     `json:"batch_id"`
	Domain       string     `json:"domain"`
	AssetScanID  string     `json:"asset_scan_id"`
	Status       string     `json:"status"` // pending, running, completed, failed
	RecordsFound int        `json:"records_found"`
	StartedAt    time.Time  `json:"started_at"`
	CompletedAt  *time.Time `json:"completed_at,omitempty"`
	ErrorMessage string     `json:"error_message,omitempty"`
}

// BatchScanProgress tracks overall batch DNS resolution progress
type BatchScanProgress struct {
	BatchID          string                          `json:"batch_id"`
	Status           string                          `json:"status"` // pending, running, completed, failed
	TotalDomains     int                             `json:"total_domains"`
	CompletedDomains int                             `json:"completed_domains"`
	FailedDomains    int                             `json:"failed_domains"`
	TotalRecords     int                             `json:"total_records"` // Total DNS records found
	StartedAt        time.Time                       `json:"started_at"`
	CompletedAt      *time.Time                      `json:"completed_at,omitempty"`
	DomainProgress   map[string]*BatchDomainProgress `json:"domain_progress"`
	ErrorMessage     string                          `json:"error_message,omitempty"`
	ModuleType       string                          `json:"module_type"` // "dnsx"
}

// loadBatchConfig loads batch configuration from environment variables
func loadBatchConfig() (*BatchConfig, error) {
	// Get batch configuration from environment
	batchID := getEnvOrDefault("BATCH_ID", "")
	if batchID == "" {
		return nil, fmt.Errorf("BATCH_ID environment variable is required in batch mode")
	}

	moduleType := getEnvOrDefault("MODULE_TYPE", "dnsx")
	totalDomainsStr := getEnvOrDefault("TOTAL_DOMAINS", "0")
	domainsStr := getEnvOrDefault("DOMAINS", "")
	assetScanMappingStr := getEnvOrDefault("ASSET_SCAN_MAPPING", "{}")
	allocatedCPUStr := getEnvOrDefault("ALLOCATED_CPU", "256")
	allocatedMemoryStr := getEnvOrDefault("ALLOCATED_MEMORY", "512")

	// NEW: Check if we should fetch subdomains from database
	fetchSubdomains := getEnvOrDefault("FETCH_SUBDOMAINS", "false")
	assetID := getEnvOrDefault("ASSET_ID", "")

	// NEW: Batch pagination parameters (for database-fetch mode)
	batchOffsetStr := getEnvOrDefault("BATCH_OFFSET", "0")
	batchLimitStr := getEnvOrDefault("BATCH_LIMIT", "0")
	totalSubdomainsStr := getEnvOrDefault("TOTAL_SUBDOMAINS", "0")

	// Parse total domains
	totalDomains, err := strconv.Atoi(totalDomainsStr)
	if err != nil {
		totalDomains = 0 // Will be calculated from domains list
	}

	// Parse batch pagination parameters
	batchOffset, err := strconv.Atoi(batchOffsetStr)
	if err != nil {
		batchOffset = 0
	}
	batchLimit, err := strconv.Atoi(batchLimitStr)
	if err != nil {
		batchLimit = 0
	}
	totalSubdomains, err := strconv.Atoi(totalSubdomainsStr)
	if err != nil {
		totalSubdomains = 0
	}

	// Parse domains list - NEW: Priority-based loading
	var domains []string

	// Priority 1: Fetch from database (for DNSX scans on discovered subdomains)
	if fetchSubdomains == "true" {
		if assetID == "" {
			return nil, fmt.Errorf("ASSET_ID is required when FETCH_SUBDOMAINS=true")
		}

		log.Printf("🔍 FETCH_SUBDOMAINS enabled, querying database for asset: %s (offset=%d, limit=%d, total=%d)",
			assetID, batchOffset, batchLimit, totalSubdomains)

		// Initialize Supabase client
		supabaseClient, err := NewSupabaseClient()
		if err != nil {
			return nil, fmt.Errorf("failed to initialize Supabase client: %w", err)
		}

		// Fetch subdomains from database with pagination
		domains, err = supabaseClient.GetSubdomainsForAsset(assetID, batchOffset, batchLimit)
		if err != nil {
			return nil, fmt.Errorf("failed to fetch subdomains: %w", err)
		}

		if len(domains) == 0 {
			return nil, fmt.Errorf("no subdomains found for asset %s (offset=%d, limit=%d). Run subfinder first or check pagination",
				assetID, batchOffset, batchLimit)
		}

		log.Printf("✅ Fetched %d subdomains from database (batch range: %d-%d of %d total)",
			len(domains), batchOffset, batchOffset+len(domains), totalSubdomains)
	} else if domainsStr != "" {
		// Priority 2: Parse from DOMAINS env var (JSON array, Phase 5 standard)
		if err := json.Unmarshal([]byte(domainsStr), &domains); err != nil {
			return nil, fmt.Errorf("failed to parse DOMAINS JSON: %v (value: %s)", err, domainsStr)
		}

		// Trim whitespace from each domain
		for i := range domains {
			domains[i] = strings.TrimSpace(domains[i])
		}
		// Filter out empty domains
		var filteredDomains []string
		for _, d := range domains {
			if d != "" {
				filteredDomains = append(filteredDomains, d)
			}
		}
		domains = filteredDomains

		log.Printf("✅ Parsed %d domains from DOMAINS JSON array", len(domains))
	} else {
		return nil, fmt.Errorf("no domains provided. Set FETCH_SUBDOMAINS=true with ASSET_ID, or provide DOMAINS")
	}

	// Use actual domain count if total_domains not provided
	if totalDomains == 0 {
		totalDomains = len(domains)
	}

	// Parse asset scan mapping
	var assetScanMapping map[string]string

	// 🔍 DEBUG LOG: Raw mapping before parsing
	log.Printf("🔍 DEBUG [Checkpoint 1]: ASSET_SCAN_MAPPING env var (raw):")
	log.Printf("   Length: %d characters", len(assetScanMappingStr))
	log.Printf("   Content: %s", assetScanMappingStr)

	if err := json.Unmarshal([]byte(assetScanMappingStr), &assetScanMapping); err != nil {
		log.Printf("❌ DEBUG [Checkpoint 1]: JSON parsing FAILED: %v", err)
		return nil, fmt.Errorf("failed to parse ASSET_SCAN_MAPPING: %v", err)
	}

	// 🔍 DEBUG LOG: Parsed mapping structure
	log.Printf("✅ DEBUG [Checkpoint 1]: ASSET_SCAN_MAPPING parsed successfully")
	log.Printf("   Map size: %d entries", len(assetScanMapping))
	log.Printf("   Map keys (parent domains):")
	for key, value := range assetScanMapping {
		log.Printf("     - '%s' → '%s'", key, value)
	}

	if len(assetScanMapping) == 0 {
		log.Printf("⚠️  DEBUG [Checkpoint 1]: WARNING - Mapping is EMPTY!")
	}

	// Parse allocated resources
	allocatedCPU, err := strconv.Atoi(allocatedCPUStr)
	if err != nil {
		allocatedCPU = 256 // Default
	}

	allocatedMemory, err := strconv.Atoi(allocatedMemoryStr)
	if err != nil {
		allocatedMemory = 512 // Default
	}

	config := &BatchConfig{
		BatchID:          batchID,
		ModuleType:       moduleType,
		AssetID:          assetID, // Pass asset_id to populate DNS records
		BatchDomains:     domains,
		AssetScanMapping: assetScanMapping,
		TotalDomains:     totalDomains,
		AllocatedCPU:     allocatedCPU,
		AllocatedMemory:  allocatedMemory,
		BatchOffset:      batchOffset,
		BatchLimit:       batchLimit,
		TotalSubdomains:  totalSubdomains,
	}

	// Validate configuration
	if err := validateBatchConfig(config); err != nil {
		return nil, fmt.Errorf("invalid batch configuration: %v", err)
	}

	return config, nil
}

// validateBatchConfig validates the batch configuration
func validateBatchConfig(config *BatchConfig) error {
	if config.BatchID == "" {
		return fmt.Errorf("batch_id is required")
	}

	if len(config.BatchDomains) == 0 {
		return fmt.Errorf("no domains provided for batch processing")
	}

	if config.TotalDomains != len(config.BatchDomains) {
		fmt.Printf("⚠️  Warning: TOTAL_DOMAINS (%d) does not match actual domain count (%d)\n",
			config.TotalDomains, len(config.BatchDomains))
		config.TotalDomains = len(config.BatchDomains)
	}

	return nil
}

// printBatchConfig logs the batch configuration for debugging
func printBatchConfig(config *BatchConfig) {
	fmt.Println(strings.Repeat("=", 70))
	fmt.Println("📦 BATCH CONFIGURATION")
	fmt.Println(strings.Repeat("=", 70))
	fmt.Printf("Batch ID:        %s\n", config.BatchID)
	fmt.Printf("Module Type:     %s\n", config.ModuleType)
	fmt.Printf("Total Domains:   %d\n", config.TotalDomains)
	fmt.Printf("Allocated CPU:   %d\n", config.AllocatedCPU)
	fmt.Printf("Allocated Memory: %d MB\n", config.AllocatedMemory)
	fmt.Println()
	fmt.Printf("Domains to scan (%d):\n", len(config.BatchDomains))
	for i, domain := range config.BatchDomains {
		scanJobID := config.AssetScanMapping[domain]
		if scanJobID != "" {
			fmt.Printf("  %d. %s → %s\n", i+1, domain, scanJobID[:8]+"...")
		} else {
			fmt.Printf("  %d. %s (no scan job mapping)\n", i+1, domain)
		}
	}
	fmt.Println(strings.Repeat("=", 70))
}

// getEnvOrDefault gets an environment variable or returns a default value
func getEnvOrDefault(key, defaultValue string) string {
	if value := os.Getenv(key); value != "" {
		return value
	}
	return defaultValue
}

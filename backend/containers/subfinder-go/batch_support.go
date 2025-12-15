package main

import (
	"context"
	"encoding/json"
	"fmt"
	"io"
	"log"
	"net/http"
	"os"
	"strconv"
	"strings"
	"sync"
	"time"

	"github.com/projectdiscovery/goflags"
	"github.com/projectdiscovery/subfinder/v2/pkg/resolve"
	"github.com/projectdiscovery/subfinder/v2/pkg/runner"
	"golang.org/x/time/rate"
)

// BatchConfig represents batch processing configuration
type BatchConfig struct {
	BatchID          string            `json:"batch_id"`
	ModuleType       string            `json:"module_type"`
	AssetID          string            `json:"asset_id"` // ✅ FIX: Asset ID for all subdomains in this batch
	BatchDomains     []string          `json:"batch_domains"`
	AssetScanMapping map[string]string `json:"asset_scan_mapping"` // domain -> asset_scan_id
	TotalDomains     int               `json:"total_domains"`
	AllocatedCPU     int               `json:"allocated_cpu"`
	AllocatedMemory  int               `json:"allocated_memory"`
	OptimizedSources []string          `json:"optimized_sources,omitempty"` // Optional: sources to prioritize
}

// BatchDomainProgress tracks individual domain progress within a batch
type BatchDomainProgress struct {
	BatchID         string     `json:"batch_id"`
	Domain          string     `json:"domain"`
	AssetScanID     string     `json:"asset_scan_id"`
	Status          string     `json:"status"` // pending, running, completed, failed
	SubdomainsFound int        `json:"subdomains_found"`
	StartedAt       time.Time  `json:"started_at"`
	CompletedAt     *time.Time `json:"completed_at,omitempty"`
	ErrorMessage    string     `json:"error_message,omitempty"`
}

// BatchScanProgress tracks overall batch scan progress
type BatchScanProgress struct {
	BatchID          string                          `json:"batch_id"`
	Status           string                          `json:"status"` // pending, running, completed, failed
	TotalDomains     int                             `json:"total_domains"`
	CompletedDomains int                             `json:"completed_domains"`
	FailedDomains    int                             `json:"failed_domains"`
	TotalSubdomains  int                             `json:"total_subdomains"`
	StartedAt        time.Time                       `json:"started_at"`
	CompletedAt      *time.Time                      `json:"completed_at,omitempty"`
	DomainProgress   map[string]*BatchDomainProgress `json:"domain_progress"`
	ErrorMessage     string                          `json:"error_message,omitempty"`
	ModuleType       string                          `json:"module_type"`
}

// BatchDomainResult represents the result of scanning a domain in batch mode
type BatchDomainResult struct {
	Domain       string                 `json:"domain"`
	Status       string                 `json:"status"`
	Subdomains   []*ScanResult          `json:"subdomains"`
	ErrorMessage string                 `json:"error_message,omitempty"`
	SourcesUsed  []string               `json:"sources_used,omitempty"`
	RetryCount   int                    `json:"retry_count,omitempty"`
	StartedAt    time.Time              `json:"started_at"`
	CompletedAt  *time.Time             `json:"completed_at,omitempty"`
	Metadata     map[string]interface{} `json:"metadata,omitempty"`
}

// Enhanced batch mode detection
func (s *Scanner) isBatchMode() bool {
	batchMode := strings.ToLower(getEnvWithDefault("BATCH_MODE", "false"))
	return batchMode == "true" || batchMode == "1"
}

// loadBatchConfig loads enhanced batch configuration from environment variables
func (s *Scanner) loadBatchConfig() (*BatchConfig, error) {
	if !s.isBatchMode() {
		return nil, fmt.Errorf("not in batch mode")
	}

	// Get batch configuration from environment
	batchID := getEnvWithDefault("BATCH_ID", "")
	if batchID == "" {
		return nil, fmt.Errorf("BATCH_ID environment variable is required in batch mode")
	}

	// ✅ FIX: Read ASSET_ID for propagating to DNSx via Redis stream
	assetID := getEnvWithDefault("ASSET_ID", "")
	if assetID == "" {
		return nil, fmt.Errorf("ASSET_ID environment variable is required in batch mode")
	}

	moduleType := getEnvWithDefault("MODULE_TYPE", "subfinder")
	totalDomainsStr := getEnvWithDefault("TOTAL_DOMAINS", "0")
	domainsStr := getEnvWithDefault("DOMAINS", "")
	assetScanMappingStr := getEnvWithDefault("ASSET_SCAN_MAPPING", "{}")
	allocatedCPUStr := getEnvWithDefault("ALLOCATED_CPU", "256")
	allocatedMemoryStr := getEnvWithDefault("ALLOCATED_MEMORY", "512")
	optimizedSourcesStr := getEnvWithDefault("OPTIMIZED_SOURCES", "")

	// Parse configurations
	totalDomains, err := strconv.Atoi(totalDomainsStr)
	if err != nil {
		return nil, fmt.Errorf("invalid TOTAL_DOMAINS: %v", err)
	}

	allocatedCPU, err := strconv.Atoi(allocatedCPUStr)
	if err != nil {
		return nil, fmt.Errorf("invalid ALLOCATED_CPU: %v", err)
	}

	allocatedMemory, err := strconv.Atoi(allocatedMemoryStr)
	if err != nil {
		return nil, fmt.Errorf("invalid ALLOCATED_MEMORY: %v", err)
	}

	// Parse domains from JSON array (Phase 5 standard)
	var batchDomains []string
	if domainsStr != "" {
		// Use JSON parsing (consistent with simple mode)
		if err := json.Unmarshal([]byte(domainsStr), &batchDomains); err != nil {
			return nil, fmt.Errorf("failed to parse DOMAINS JSON: %v (value: %s)", err, domainsStr)
		}

		// Trim whitespace and validate
		var validDomains []string
		for _, domain := range batchDomains {
			domain = strings.TrimSpace(domain)
			if domain != "" && isValidDomainFormat(domain) {
				validDomains = append(validDomains, domain)
			}
		}
		batchDomains = validDomains
	}

	// Parse asset scan mapping
	var assetScanMapping map[string]string
	if assetScanMappingStr != "" && assetScanMappingStr != "{}" {
		err := json.Unmarshal([]byte(assetScanMappingStr), &assetScanMapping)
		if err != nil {
			return nil, fmt.Errorf("invalid ASSET_SCAN_MAPPING JSON: %v", err)
		}
	} else {
		assetScanMapping = make(map[string]string)
	}

	// Parse optimized sources
	var optimizedSources []string
	if optimizedSourcesStr != "" {
		optimizedSources = strings.Split(optimizedSourcesStr, ",")
		for i, source := range optimizedSources {
			optimizedSources[i] = strings.TrimSpace(source)
		}
	}

	config := &BatchConfig{
		BatchID:          batchID,
		ModuleType:       moduleType,
		AssetID:          assetID, // ✅ FIX: Include asset_id for DNSx
		BatchDomains:     batchDomains,
		AssetScanMapping: assetScanMapping,
		TotalDomains:     totalDomains,
		AllocatedCPU:     allocatedCPU,
		AllocatedMemory:  allocatedMemory,
		OptimizedSources: optimizedSources,
	}

	// Validate configuration
	if len(batchDomains) == 0 {
		return nil, fmt.Errorf("no valid domains found in batch configuration")
	}

	if len(batchDomains) != totalDomains {
		s.logger.Warnf("Domain count mismatch: expected %d, got %d domains", totalDomains, len(batchDomains))
		config.TotalDomains = len(batchDomains) // Use actual count
	}

	return config, nil
}

// runBatchScan executes enhanced batch scanning with improved SDK integration
func (s *Scanner) runBatchScan(config *BatchConfig) error {
	startTime := time.Now()

	// Initialize enhanced batch progress tracking
	batchProgress := &BatchScanProgress{
		BatchID:          config.BatchID,
		Status:           "running",
		TotalDomains:     config.TotalDomains,
		CompletedDomains: 0,
		FailedDomains:    0,
		TotalSubdomains:  0,
		StartedAt:        startTime,
		DomainProgress:   make(map[string]*BatchDomainProgress),
		ModuleType:       config.ModuleType,
	}

	// Initialize domain progress tracking
	for _, domain := range config.BatchDomains {
		assetScanID := config.AssetScanMapping[domain]
		if assetScanID == "" {
			assetScanID = "unknown" // Fallback
		}

		batchProgress.DomainProgress[domain] = &BatchDomainProgress{
			BatchID:     config.BatchID,
			Domain:      domain,
			AssetScanID: assetScanID,
			Status:      "pending",
			StartedAt:   startTime,
		}
	}

	// Update initial batch progress
	if err := s.updateBatchProgress(batchProgress); err != nil {
		s.logger.Errorf("Failed to update initial batch progress: %v", err)
	}

	s.logger.Infof("🚀 Starting enhanced batch scan for %d domains in batch %s",
		len(config.BatchDomains), config.BatchID)

	// Enhanced rate limiting based on allocated resources
	rateLimit := s.calculateOptimalRateLimit(config.AllocatedCPU, config.AllocatedMemory)
	limiter := rate.NewLimiter(rate.Limit(rateLimit), rateLimit*2)

	// Determine optimal worker count based on resources
	workerCount := s.calculateOptimalWorkers(config.AllocatedCPU, len(config.BatchDomains))
	s.logger.Infof("📊 Using %d workers with rate limit %d req/s for batch processing", workerCount, rateLimit)

	// Channel for collecting batch results
	resultsChan := make(chan *BatchDomainResult, len(config.BatchDomains))
	var wg sync.WaitGroup
	semaphore := make(chan struct{}, workerCount)

	// Track sources used across the batch
	var sourcesUsed sync.Map

	// Process domains in parallel
	for _, domain := range config.BatchDomains {
		wg.Add(1)
		go func(domain string) {
			defer wg.Done()

			// Acquire semaphore
			semaphore <- struct{}{}
			defer func() { <-semaphore }()

			// Check for context cancellation
			select {
			case <-s.ctx.Done():
				s.logger.Warnf("Context cancelled, skipping domain: %s", domain)
				return
			default:
			}

			// Scan domain with batch-optimized configuration
			result := s.scanDomainBatch(domain, config, limiter, &sourcesUsed)
			resultsChan <- result

			// Update batch progress
			domainProgress := batchProgress.DomainProgress[domain]
			domainProgress.Status = result.Status
			domainProgress.SubdomainsFound = len(result.Subdomains)
			domainProgress.ErrorMessage = result.ErrorMessage

			if result.CompletedAt != nil {
				domainProgress.CompletedAt = result.CompletedAt
			}

			// Update batch totals
			if result.Status == "completed" || result.Status == "partial_success" {
				batchProgress.CompletedDomains++
				batchProgress.TotalSubdomains += len(result.Subdomains)
			} else if result.Status == "failed" {
				batchProgress.FailedDomains++
			}

			// Update progress in Redis
			if err := s.updateBatchProgress(batchProgress); err != nil {
				s.logger.Errorf("Failed to update batch progress for domain %s: %v", domain, err)
			}

		}(domain)
	}

	// Wait for all scans to complete
	go func() {
		wg.Wait()
		close(resultsChan)
	}()

	// Collect and store all results
	var allResults []*BatchDomainResult
	for result := range resultsChan {
		allResults = append(allResults, result)

		// Store subdomains for this domain
		if len(result.Subdomains) > 0 {
			if err := s.storeBatchSubdomains(result, config); err != nil {
				s.logger.Errorf("Failed to store subdomains for domain %s: %v", result.Domain, err)
			}
		}
	}

	// Finalize batch progress
	completedTime := time.Now()
	batchProgress.CompletedAt = &completedTime

	// Determine final status
	if batchProgress.FailedDomains == 0 {
		batchProgress.Status = "completed"
	} else if batchProgress.CompletedDomains > 0 {
		batchProgress.Status = "completed" // 🔧 FIX: Use "completed" instead of "partial_success" for database compatibility
	} else {
		batchProgress.Status = "failed"
	}

	// Final progress update
	if err := s.updateBatchProgress(batchProgress); err != nil {
		s.logger.Errorf("Failed to update final batch progress: %v", err)
	}

	duration := completedTime.Sub(startTime)
	s.logger.Infof("✅ Batch scan completed: %d/%d domains successful, %d total subdomains found in %.2f seconds",
		batchProgress.CompletedDomains, batchProgress.TotalDomains, batchProgress.TotalSubdomains, duration.Seconds())

	// PHASE 5 FIX: Send completion marker if streaming mode enabled
	if s.config.StreamingMode {
		s.logger.Infof("📤 Sending completion marker to Redis Stream...")
		if err := s.sendCompletionMarker(batchProgress.TotalSubdomains); err != nil {
			s.logger.Errorf("❌ Failed to send completion marker: %v", err)
			// Don't fail the entire scan for this - just log the error
		} else {
			s.logger.Infof("✅ Completion marker sent: %d total subdomains", batchProgress.TotalSubdomains)
		}
	}

	// 🔬 DIAGNOSTIC: Check if we should update database
	s.logger.Infof("🔬 DIAGNOSTIC: Batch scan finished, about to update database tables")
	s.logger.Infof("🔬 DIAGNOSTIC: Batch ID: %s, Status: %s, Completed: %d/%d",
		batchProgress.BatchID, batchProgress.Status, batchProgress.CompletedDomains, batchProgress.TotalDomains)

	// 🔬 DIAGNOSTIC: Update batch_scan_jobs table
	s.logger.Infof("🔬 DIAGNOSTIC: Step 1 - Calling updateBatchProgressInDatabase()...")
	if err := s.updateBatchProgressInDatabase(batchProgress); err != nil {
		s.logger.Errorf("❌ DIAGNOSTIC: Failed to update batch progress in database: %v", err)
		return fmt.Errorf("failed to update batch progress: %v", err)
	}
	s.logger.Infof("✅ DIAGNOSTIC: Successfully updated batch_scan_jobs table")

	// 🔬 DIAGNOSTIC: Aggregate results to asset_scan_jobs
	s.logger.Infof("🔬 DIAGNOSTIC: Step 2 - Calling aggregateResultsToAssetScans()...")
	if err := s.aggregateResultsToAssetScans(config, batchProgress); err != nil {
		s.logger.Errorf("❌ DIAGNOSTIC: Failed to aggregate results to asset scans: %v", err)
		return fmt.Errorf("failed to aggregate results: %v", err)
	}
	s.logger.Infof("✅ DIAGNOSTIC: Successfully updated asset_scan_jobs table")

	s.logger.Infof("🎉 DIAGNOSTIC: All database updates completed successfully!")

	return nil
}

// Helper functions for batch processing

// isValidDomainFormat validates domain format
func isValidDomainFormat(domain string) bool {
	// Basic domain validation
	if domain == "" || len(domain) > 253 {
		return false
	}

	// Must contain at least one dot
	if !strings.Contains(domain, ".") {
		return false
	}

	// Must not start or end with dot or hyphen
	if strings.HasPrefix(domain, ".") || strings.HasSuffix(domain, ".") ||
		strings.HasPrefix(domain, "-") || strings.HasSuffix(domain, "-") {
		return false
	}

	// Must not contain spaces or invalid characters
	if strings.Contains(domain, " ") || strings.Contains(domain, "_") {
		return false
	}

	return true
}

// calculateOptimalRateLimit determines optimal rate limit based on allocated resources
func (s *Scanner) calculateOptimalRateLimit(allocatedCPU, allocatedMemory int) int {
	// Base rate limit calculation
	baseRate := 10

	// Increase rate based on CPU allocation
	cpuMultiplier := allocatedCPU / 256 // 256 CPU units = 0.25 vCPU
	if cpuMultiplier < 1 {
		cpuMultiplier = 1
	}

	// Increase rate based on memory allocation
	memoryMultiplier := allocatedMemory / 512 // 512MB base
	if memoryMultiplier < 1 {
		memoryMultiplier = 1
	}

	// Conservative calculation to avoid overwhelming sources
	optimalRate := baseRate + (cpuMultiplier * 5) + (memoryMultiplier * 3)

	// Cap at reasonable maximum
	if optimalRate > 50 {
		optimalRate = 50
	}

	return optimalRate
}

// calculateOptimalWorkers determines optimal worker count based on resources and domain count
func (s *Scanner) calculateOptimalWorkers(allocatedCPU, domainCount int) int {
	// Base worker count
	baseWorkers := 5

	// Scale with CPU allocation
	cpuWorkers := allocatedCPU / 128 // 128 CPU units per worker
	if cpuWorkers < baseWorkers {
		cpuWorkers = baseWorkers
	}

	// Don't exceed domain count (no point having more workers than domains)
	if cpuWorkers > domainCount {
		cpuWorkers = domainCount
	}

	// Cap at reasonable maximum
	if cpuWorkers > 20 {
		cpuWorkers = 20
	}

	return cpuWorkers
}

// scanDomainBatch scans a domain in batch mode with optimized configuration
func (s *Scanner) scanDomainBatch(domain string, config *BatchConfig, limiter *rate.Limiter, sourcesUsed *sync.Map) *BatchDomainResult {
	startTime := time.Now()

	result := &BatchDomainResult{
		Domain:    domain,
		Status:    "running",
		StartedAt: startTime,
		Metadata:  make(map[string]interface{}),
	}

	// 🔬 DEBUG POINT 5: Network connectivity test
	log.Printf("🔬 DEBUG: Testing network connectivity to crt.sh...")
	if resp, err := http.Get("https://crt.sh"); err != nil {
		log.Printf("🔬 DEBUG: Network test FAILED: %v", err)
	} else {
		log.Printf("🔬 DEBUG: Network test OK: HTTP %d", resp.StatusCode)
		resp.Body.Close()
	}

	// Wait for rate limiter
	if err := limiter.Wait(s.ctx); err != nil {
		result.Status = "failed"
		result.ErrorMessage = fmt.Sprintf("Rate limiter error: %v", err)
		completedTime := time.Now()
		result.CompletedAt = &completedTime
		return result
	}

	// Configure sources - use optimized sources if provided, otherwise use defaults
	var sources []string
	if len(config.OptimizedSources) > 0 {
		sources = config.OptimizedSources
	} else {
		// 🔧 UPDATED: Now including authenticated sources with API keys
		// - crtsh, alienvault: Free sources (no API key required)
		// - shodan: API key configured in provider-config.yaml
		sources = []string{"crtsh", "alienvault", "shodan"}
	}

	// 🔬 DEBUG POINT 1: Enumeration entry
	log.Printf("🔬 DEBUG: About to enumerate domain: %s | Sources: %v | Streaming: %v",
		domain, sources, s.config.StreamingMode)

	// Thread-safe result collection
	var subdomains []*ScanResult
	var resultMutex sync.Mutex

	// 🔬 Track subdomains per source for detailed logging
	sourceSubdomainCount := make(map[string]int)
	var sourceCountMutex sync.Mutex

	// 🔬 CRITICAL DEBUG: Verify provider config file exists
	providerConfigPath := "/app/provider-config.yaml"
	if _, err := os.Stat(providerConfigPath); os.IsNotExist(err) {
		log.Printf("❌ CRITICAL: Provider config file NOT FOUND at %s", providerConfigPath)
		log.Printf("❌ This will cause 0 subdomains to be returned!")
	} else {
		log.Printf("✅ Provider config file EXISTS at %s", providerConfigPath)
		// Read and log the config content
		if content, err := os.ReadFile(providerConfigPath); err == nil {
			log.Printf("📄 Config content:\n%s", string(content))
		}
	}

	// Enhanced subfinder configuration for batch processing
	runnerOptions := &runner.Options{
		Domain:             goflags.StringSlice{domain},
		Sources:            goflags.StringSlice(sources),
		ExcludeSources:     goflags.StringSlice{}, // 🔧 FIX: Required field for proper source initialization
		ProviderConfig:     providerConfigPath,    // 🔧 CRITICAL: Required even for free sources, or SDK returns 0 results
		MaxEnumerationTime: 6,                     // Slightly reduced for batch efficiency
		Timeout:            30,
		Threads:            10,
		Silent:             true,
		JSON:               false,
		RemoveWildcard:     true,
		All:                false,
		Output:             io.Discard, // 🔧 FIX: Provide output writer to prevent nil pointer dereference

		ResultCallback: func(hostEntry *resolve.HostEntry) {
			// 🔬 DEBUG POINT 3: ResultCallback triggered
			log.Printf("🔬 DEBUG: ResultCallback TRIGGERED | Host: %s | Source: %s",
				hostEntry.Host, hostEntry.Source)

			resultMutex.Lock()
			defer resultMutex.Unlock()

			// Track source usage
			if hostEntry.Source != "" {
				sourcesUsed.Store(hostEntry.Source, true)

				// 🔬 Track subdomain count per source
				sourceCountMutex.Lock()
				sourceSubdomainCount[hostEntry.Source]++
				sourceCountMutex.Unlock()
			}

			// Create scan result
			scanResult := &ScanResult{
				Subdomain:    strings.ToLower(strings.TrimSpace(hostEntry.Host)),
				IPAddresses:  []string{},
				Source:       "subfinder",
				DiscoveredAt: time.Now().UTC().Format(time.RFC3339),
				ParentDomain: domain,
				Metadata: map[string]string{
					"source_details": hostEntry.Source,
					"domain":         hostEntry.Domain,
					"batch_id":       config.BatchID,
					"scan_mode":      "batch",
				},
			}

			// Validate and add subdomain
			if s.isValidSubdomain(scanResult.Subdomain, domain) {
				subdomains = append(subdomains, scanResult)
			}
		},
	}

	// Create subfinder runner
	subfinderRunner, err := runner.NewRunner(runnerOptions)
	if err != nil {
		result.Status = "failed"
		result.ErrorMessage = fmt.Sprintf("Failed to create subfinder runner: %v", err)
		completedTime := time.Now()
		result.CompletedAt = &completedTime
		return result
	}

	// Create domain-specific context with timeout
	domainCtx, cancel := context.WithTimeout(s.ctx, time.Duration(runnerOptions.MaxEnumerationTime)*time.Minute)
	defer cancel()

	// 🔬 DEBUG POINT 2: Before enumeration execution
	log.Printf("🔬 DEBUG: Calling RunEnumerationWithCtx for domain: %s", domain)

	// Run enumeration
	err = subfinderRunner.RunEnumerationWithCtx(domainCtx)
	completedTime := time.Now()
	result.CompletedAt = &completedTime

	// 🔬 DEBUG POINT 2: After enumeration execution
	log.Printf("🔬 DEBUG: RunEnumerationWithCtx completed | Domain: %s | Error: %v | Subdomains collected: %d",
		domain, err, len(subdomains))

	// 🔬 Log detailed breakdown per source
	if len(sourceSubdomainCount) > 0 {
		log.Printf("📊 SUBDOMAIN BREAKDOWN for %s:", domain)
		for source, count := range sourceSubdomainCount {
			log.Printf("   └─ %s: %d subdomains", source, count)
		}
	} else {
		log.Printf("⚠️  NO SUBDOMAINS from ANY source for %s", domain)
	}

	// Collect sources used for this domain
	var domainSources []string
	sourcesUsed.Range(func(key, value interface{}) bool {
		if source, ok := key.(string); ok {
			domainSources = append(domainSources, source)
		}
		return true
	})
	result.SourcesUsed = domainSources

	// Handle results and errors
	if err != nil {
		if domainCtx.Err() == context.DeadlineExceeded {
			result.Status = "partial_success"
			result.ErrorMessage = "Scan timeout, partial results returned"
		} else if s.ctx.Err() != nil {
			result.Status = "cancelled"
			result.ErrorMessage = "Scan cancelled"
		} else {
			result.Status = "failed"
			result.ErrorMessage = fmt.Sprintf("Enumeration failed: %v", err)
		}
	} else {
		result.Status = "completed"
	}

	result.Subdomains = subdomains
	result.Metadata["subdomains_found"] = len(subdomains)
	result.Metadata["scan_duration_seconds"] = completedTime.Sub(startTime).Seconds()

	s.logger.Infof("�� Batch domain %s: %d subdomains found (status: %s)",
		domain, len(subdomains), result.Status)

	return result
}

// storeBatchSubdomains stores discovered subdomains for a batch domain result
func (s *Scanner) storeBatchSubdomains(result *BatchDomainResult, config *BatchConfig) error {
	// 🔬 DEBUG POINT 4: Storage path
	log.Printf("🔬 DEBUG: storeBatchSubdomains called | Domain: %s | Subdomain count: %d | Streaming mode: %v",
		result.Domain, len(result.Subdomains), s.config.StreamingMode)

	if len(result.Subdomains) == 0 {
		log.Printf("🔬 DEBUG: Skipping storage - 0 subdomains to store")
		return nil
	}

	s.logger.Infof("📤 Storing %d subdomains for batch domain: %s", len(result.Subdomains), result.Domain)

	// PHASE 4 FIX: Subfinder ONLY streams - DNSx handles all database writes
	// Rationale: Clean separation of concerns (discovery vs. persistence)
	if !s.config.StreamingMode {
		return fmt.Errorf("CRITICAL: Batch mode requires streaming to be enabled. " +
			"DNSx (persistence layer) must be running to consume and persist data")
	}

	s.logger.Infof("🌊 Streaming %d subdomains to Redis for DNSx consumption", len(result.Subdomains))

	// Convert BatchDomainResult to DomainScanResult for streaming compatibility
	domainResult := &DomainScanResult{
		Domain:     result.Domain,
		Subdomains: result.Subdomains,
	}

	// Stream subdomains to Redis - this is CRITICAL for data persistence
	if err := s.streamSubdomainsToRedis(domainResult); err != nil {
		return fmt.Errorf("CRITICAL: Failed to stream subdomains to Redis: %w. "+
			"Data will be lost without successful streaming", err)
	}

	s.logger.Infof("✅ Successfully streamed %d subdomains for domain: %s (DNSx will persist)",
		len(result.Subdomains), result.Domain)

	// ARCHITECTURE: DNSx (consumer) is responsible for:
	// 1. Consuming subdomains from Redis Stream
	// 2. Performing DNS resolution
	// 3. Writing to database (subdomains + dns_records tables)
	return nil
}

// updateBatchProgress updates batch progress in Redis
func (s *Scanner) updateBatchProgress(progress *BatchScanProgress) error {
	// Convert progress to JSON for Redis storage
	progressJSON, err := json.Marshal(progress)
	if err != nil {
		return fmt.Errorf("failed to marshal batch progress: %v", err)
	}

	// Store in Redis with batch-specific key
	progressKey := fmt.Sprintf("batch_progress:%s", progress.BatchID)
	if err := s.redisClient.Set(s.ctx, progressKey, string(progressJSON), 24*time.Hour).Err(); err != nil {
		return fmt.Errorf("failed to store batch progress: %v", err)
	}

	// Also update a simplified status for quick queries
	statusKey := fmt.Sprintf("batch_status:%s", progress.BatchID)
	statusData := map[string]interface{}{
		"status":            progress.Status,
		"completed_domains": progress.CompletedDomains,
		"total_domains":     progress.TotalDomains,
		"total_subdomains":  progress.TotalSubdomains,
		"percentage":        float64(progress.CompletedDomains) / float64(progress.TotalDomains) * 100,
	}

	if err := s.redisClient.HMSet(s.ctx, statusKey, statusData).Err(); err != nil {
		s.logger.Warnf("Failed to update batch status hash: %v", err)
	}

	// Set expiration
	s.redisClient.Expire(s.ctx, statusKey, 24*time.Hour)

	return nil
}

// updateBatchProgressInDatabase updates batch progress in Supabase database
func (s *Scanner) updateBatchProgressInDatabase(progress *BatchScanProgress) error {
	// Update batch_scan_jobs table (note: total_subdomains tracked at asset_scan_jobs level, not batch level)
	batchUpdate := map[string]interface{}{
		"status":            progress.Status,
		"completed_domains": progress.CompletedDomains,
		"failed_domains":    progress.FailedDomains,
		// total_subdomains removed - not a column in batch_scan_jobs table
	}

	if progress.CompletedAt != nil {
		batchUpdate["completed_at"] = progress.CompletedAt.Format(time.RFC3339)
	}

	if progress.ErrorMessage != "" {
		batchUpdate["error_message"] = progress.ErrorMessage
	}

	// Update batch scan job
	if err := s.supabaseClient.UpdateBatchScanJob(progress.BatchID, batchUpdate); err != nil {
		return fmt.Errorf("failed to update batch scan job: %v", err)
	}

	// Update individual domain assignments
	for domain, domainProgress := range progress.DomainProgress {
		domainUpdate := map[string]interface{}{
			"status":           domainProgress.Status,
			"subdomains_found": domainProgress.SubdomainsFound,
		}

		if domainProgress.CompletedAt != nil {
			domainUpdate["completed_at"] = domainProgress.CompletedAt.Format(time.RFC3339)
		}

		if domainProgress.ErrorMessage != "" {
			domainUpdate["error_message"] = domainProgress.ErrorMessage
		}

		if err := s.supabaseClient.UpdateBatchDomainAssignment(progress.BatchID, domain, domainUpdate); err != nil {
			s.logger.Errorf("Failed to update domain assignment for %s: %v", domain, err)
		}
	}

	return nil
}

// aggregateResultsToAssetScans aggregates batch results back to individual asset scans
func (s *Scanner) aggregateResultsToAssetScans(batchConfig *BatchConfig, batchProgress *BatchScanProgress) error {
	s.logger.Infof("📊 Aggregating batch results to asset scans...")
	s.logger.Infof("🔬 DIAGNOSTIC: AssetScanMapping has %d entries", len(batchConfig.AssetScanMapping))

	// Group results by asset scan ID
	assetScanResults := make(map[string]struct {
		domains          []string
		totalSubdomains  int
		completedDomains int
		failedDomains    int
	})

	// Aggregate domain results by asset scan
	for domain, domainProgress := range batchProgress.DomainProgress {
		assetScanID := domainProgress.AssetScanID
		if assetScanID == "" {
			s.logger.Warnf("No asset scan ID for domain %s, skipping aggregation", domain)
			continue
		}

		s.logger.Infof("🔬 DIAGNOSTIC: Aggregating domain '%s' to asset_scan_id '%s'", domain, assetScanID)

		result := assetScanResults[assetScanID]
		result.domains = append(result.domains, domain)
		result.totalSubdomains += domainProgress.SubdomainsFound

		if domainProgress.Status == "completed" {
			result.completedDomains++
		} else if domainProgress.Status == "failed" {
			result.failedDomains++
		}

		assetScanResults[assetScanID] = result
	}

	s.logger.Infof("🔬 DIAGNOSTIC: Grouped into %d unique asset scan jobs", len(assetScanResults))

	// Update each asset scan job with aggregated results
	for assetScanID, result := range assetScanResults {
		s.logger.Infof("🔬 DIAGNOSTIC: Processing asset_scan_id '%s': %d domains, %d subdomains",
			assetScanID, len(result.domains), result.totalSubdomains)

		// Determine overall status for this asset scan
		status := "running"
		if result.completedDomains+result.failedDomains == len(result.domains) {
			if result.failedDomains == 0 {
				status = "completed"
			} else if result.completedDomains == 0 {
				status = "failed"
			} else {
				status = "completed_with_errors"
			}
		}

		s.logger.Infof("🔬 DIAGNOSTIC: Determined status '%s' for asset_scan_id '%s'", status, assetScanID)

		assetUpdate := map[string]interface{}{
			"completed_domains": result.completedDomains,
			"status":            status,
		}

		if status == "completed" || status == "completed_with_errors" || status == "failed" {
			assetUpdate["completed_at"] = time.Now().UTC().Format(time.RFC3339)
		}

		s.logger.Infof("🔬 DIAGNOSTIC: About to call UpdateAssetScanJob for '%s' with updates: %+v", assetScanID, assetUpdate)

		if err := s.supabaseClient.UpdateAssetScanJob(assetScanID, assetUpdate); err != nil {
			s.logger.Errorf("❌ Failed to update asset scan %s: %v", assetScanID, err)
		} else {
			s.logger.Infof("✅ Successfully updated asset scan %s: %d domains, %d subdomains, status: %s",
				assetScanID, len(result.domains), result.totalSubdomains, status)
		}
	}

	return nil
}

// runBatchDomainScans runs the actual domain scanning with batch tracking
func (s *Scanner) runBatchDomainScans(batchConfig *BatchConfig, batchProgress *BatchScanProgress) error {
	// Update config to use batch domains
	s.config.Domains = batchConfig.BatchDomains
	s.config.JobID = batchConfig.BatchID

	// Use the existing Run() method but with batch progress tracking
	// The existing Run() method will scan all domains in s.config.Domains
	// We'll override the progress tracking to use batch progress instead
	originalRun := s.Run

	// For now, use the existing Run method
	// TODO: In a full implementation, we'd want to modify Run() to use batch progress
	s.logger.Infof("🔬 DIAGNOSTIC: About to call originalRun() for batch processing")

	if err := originalRun(); err != nil {
		s.logger.Errorf("🔬 DIAGNOSTIC: originalRun() FAILED with error: %v", err)
		batchProgress.Status = "failed"
		batchProgress.ErrorMessage = err.Error()
		completedAt := time.Now()
		batchProgress.CompletedAt = &completedAt

		// Update final progress
		s.updateBatchProgress(batchProgress)
		s.updateBatchProgressInDatabase(batchProgress)
		return err
	}

	// 🔬 DIAGNOSTIC: originalRun() succeeded
	s.logger.Infof("🔬 DIAGNOSTIC: originalRun() completed successfully, proceeding to batch status updates")

	// Mark batch as completed
	batchProgress.Status = "completed"
	completedAt := time.Now()
	batchProgress.CompletedAt = &completedAt

	// 🔬 DIAGNOSTIC: Mark batch completion reached
	s.logger.Infof("🔬 DIAGNOSTIC: Batch marked as completed, about to update progress")

	// Update final progress
	s.updateBatchProgress(batchProgress)

	// 🔬 DIAGNOSTIC: About to update batch status
	s.logger.Infof("🔬 DIAGNOSTIC: About to update batch status to '%s' for batch %s", batchProgress.Status, batchProgress.BatchID)

	if err := s.updateBatchProgressInDatabase(batchProgress); err != nil {
		s.logger.Errorf("❌ Failed to update batch progress: %v", err)
		return err
	}

	s.logger.Infof("✅ Successfully updated batch status to '%s'", batchProgress.Status)

	// 🔬 DIAGNOSTIC: About to aggregate results to asset scans
	s.logger.Infof("🔬 DIAGNOSTIC: About to aggregate results to asset scans")

	// Aggregate results back to asset scans
	return s.aggregateResultsToAssetScans(batchConfig, batchProgress)
}

// getEnvWithDefault gets environment variable with default value
func getEnvWithDefault(key, defaultValue string) string {
	if value := os.Getenv(key); value != "" {
		return value
	}
	return defaultValue
}

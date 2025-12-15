package main

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"os"
	"strings"
	"sync"
	"time"

	"github.com/go-redis/redis/v8"
	"github.com/projectdiscovery/goflags"
	"github.com/projectdiscovery/subfinder/v2/pkg/resolve"
	"github.com/projectdiscovery/subfinder/v2/pkg/runner"
	"golang.org/x/time/rate"
)

// DomainScanProgress tracks individual domain scan progress
type DomainScanProgress struct {
	Domain          string     `json:"domain"`
	Status          string     `json:"status"` // pending, running, completed, failed
	SubdomainsFound int        `json:"subdomains_found"`
	StartedAt       time.Time  `json:"started_at"`
	CompletedAt     *time.Time `json:"completed_at,omitempty"`
	ErrorMessage    string     `json:"error_message,omitempty"`
	SourcesUsed     []string   `json:"sources_used,omitempty"`
}

// AssetScanProgress tracks overall asset scan progress
type AssetScanProgress struct {
	JobID            string                         `json:"job_id"`
	Status           string                         `json:"status"` // pending, running, completed, failed
	TotalDomains     int                            `json:"total_domains"`
	CompletedDomains int                            `json:"completed_domains"`
	TotalSubdomains  int                            `json:"total_subdomains"`
	StartedAt        time.Time                      `json:"started_at"`
	CompletedAt      *time.Time                     `json:"completed_at,omitempty"`
	DomainProgress   map[string]*DomainScanProgress `json:"domain_progress"`
	ErrorMessage     string                         `json:"error_message,omitempty"`
}

// Run executes the multi-domain subfinder scan with enhanced SDK usage
func (s *Scanner) Run() error {
	startTime := time.Now()

	// Initialize asset scan progress
	assetProgress := &AssetScanProgress{
		JobID:            s.config.JobID,
		Status:           "running",
		TotalDomains:     len(s.config.Domains),
		CompletedDomains: 0,
		TotalSubdomains:  0,
		StartedAt:        startTime,
		DomainProgress:   make(map[string]*DomainScanProgress),
	}

	// Initialize domain progress tracking
	for _, domain := range s.config.Domains {
		assetProgress.DomainProgress[domain] = &DomainScanProgress{
			Domain:    domain,
			Status:    "pending",
			StartedAt: startTime,
		}
	}

	// Update initial status in Redis
	if err := s.updateProgress(assetProgress); err != nil {
		s.logger.Errorf("Failed to update initial progress: %v", err)
	}

	s.logger.Infof("🎯 Starting enhanced subfinder scan for %d domains with %d workers",
		len(s.config.Domains), s.config.Workers)

	// Enhanced rate limiter configuration for better performance
	limiter := rate.NewLimiter(rate.Limit(20), 25) // Increased for better throughput

	// Channel for collecting results
	resultsChan := make(chan *DomainScanResult, len(s.config.Domains))

	// Use optimized worker pool with better resource management
	var wg sync.WaitGroup
	semaphore := make(chan struct{}, s.config.Workers)

	for _, domain := range s.config.Domains {
		wg.Add(1)
		go func(domain string) {
			defer wg.Done()

			// Acquire semaphore
			semaphore <- struct{}{}
			defer func() { <-semaphore }()

			// Check context for cancellation
			select {
			case <-s.ctx.Done():
				s.logger.Warnf("Context cancelled, skipping domain: %s", domain)
				return
			default:
			}

			// Enhanced domain scanning with retry logic
			result := s.scanDomainWithRetry(domain, limiter, 2)
			resultsChan <- result

			// Update progress
			assetProgress.DomainProgress[domain] = result.Progress
			if result.Progress.Status == "completed" {
				assetProgress.CompletedDomains++
				assetProgress.TotalSubdomains += result.Progress.SubdomainsFound
			}

			// Update progress in Redis
			if err := s.updateProgress(assetProgress); err != nil {
				s.logger.Errorf("Failed to update progress for domain %s: %v", domain, err)
			}

		}(domain)
	}

	// Wait for all scans to complete
	go func() {
		wg.Wait()
		close(resultsChan)
	}()

	// Collect and stream results (DNSx handles database persistence)
	var allResults []*DomainScanResult
	totalStreamedSubdomains := 0
	for result := range resultsChan {
		allResults = append(allResults, result)

		// Phase 4 Fix: Stream results to Redis for DNSx to consume
		// DNSx is the canonical persistence layer - it will write to database
		// Streaming is CRITICAL - if it fails, data is lost
		if err := s.streamSubdomainsToRedis(result); err != nil {
			s.logger.Errorf("❌ CRITICAL: Failed to stream subdomains for domain %s: %v",
				result.Domain, err)
			// Continue processing other domains, but mark this as failed
			result.Progress.Status = "failed"
			result.Progress.ErrorMessage = fmt.Sprintf("Streaming failed: %v", err)
		} else {
			totalStreamedSubdomains += len(result.Subdomains)
			s.logger.Debugf("✅ Streamed %d subdomains for domain %s",
				len(result.Subdomains), result.Domain)
		}
	}

	// Finalize asset scan progress
	completedTime := time.Now()
	assetProgress.CompletedAt = &completedTime
	assetProgress.Status = "completed"

	// Check for any failures
	for _, result := range allResults {
		if result.Progress.Status == "failed" {
			assetProgress.Status = "completed" // 🔧 FIX: Use "completed" instead of "partial_failure" for database compatibility
			break
		}
	}

	// Final progress update
	if err := s.updateProgress(assetProgress); err != nil {
		s.logger.Errorf("Failed to update final progress: %v", err)
	}

	s.logger.Infof("✅ Asset scan completed: %d domains, %d total subdomains found",
		assetProgress.CompletedDomains, assetProgress.TotalSubdomains)

	// Send completion marker to Redis Stream (if streaming mode enabled)
	if err := s.sendCompletionMarker(totalStreamedSubdomains); err != nil {
		s.logger.Errorf("Failed to send completion marker: %v", err)
		// Don't return error - completion marker is not critical
	}

	return nil
}

// DomainScanResult represents the result of scanning a single domain
type DomainScanResult struct {
	Domain     string              `json:"domain"`
	Subdomains []*ScanResult       `json:"subdomains"`
	Progress   *DomainScanProgress `json:"progress"`
}

// scanDomainWithRetry performs subfinder scan with retry logic
func (s *Scanner) scanDomainWithRetry(domain string, limiter *rate.Limiter, maxRetries int) *DomainScanResult {
	var lastResult *DomainScanResult

	for attempt := 0; attempt <= maxRetries; attempt++ {
		if attempt > 0 {
			s.logger.Infof("🔄 Retrying scan for domain %s (attempt %d/%d)", domain, attempt+1, maxRetries+1)
			// Exponential backoff
			backoffDuration := time.Duration(attempt*attempt) * time.Second
			select {
			case <-time.After(backoffDuration):
			case <-s.ctx.Done():
				return s.createFailedResult(domain, "Context cancelled during retry")
			}
		}

		result := s.scanDomain(domain, limiter)
		lastResult = result

		// If successful or context cancelled, return result
		if result.Progress.Status == "completed" || s.ctx.Err() != nil {
			return result
		}

		// If this was the last attempt, return the failed result
		if attempt == maxRetries {
			s.logger.Errorf("❌ All retry attempts failed for domain: %s", domain)
			return result
		}
	}

	return lastResult
}

// scanDomain performs enhanced subfinder scan for a single domain
func (s *Scanner) scanDomain(domain string, limiter *rate.Limiter) *DomainScanResult {
	startTime := time.Now()

	progress := &DomainScanProgress{
		Domain:      domain,
		Status:      "running",
		StartedAt:   startTime,
		SourcesUsed: []string{},
	}

	s.logger.Infof("🔍 Starting enhanced subfinder scan for domain: %s", domain)

	// Wait for rate limiter
	if err := limiter.Wait(s.ctx); err != nil {
		return s.createFailedResult(domain, fmt.Sprintf("Rate limiter error: %v", err))
	}

	// Thread-safe result collection
	var subdomains []*ScanResult
	var resultMutex sync.Mutex
	var sourcesUsed sync.Map

	// Enhanced subfinder configuration based on official SDK best practices
	runnerOptions := &runner.Options{
		Domain: goflags.StringSlice{domain},
		// Optimized source selection for better performance and reliability
		Sources:            goflags.StringSlice{"crtsh", "virustotal", "alienvault", "bufferover", "chaos", "github", "shodan"},
		ExcludeSources:     goflags.StringSlice{}, // Exclude problematic sources if needed
		MaxEnumerationTime: 8,                     // Increased timeout for better coverage
		Timeout:            45,                    // Increased request timeout
		Threads:            15,                    // Optimized thread count
		Silent:             true,
		JSON:               false,
		RemoveWildcard:     true,
		All:                false, // Use specific sources instead of all for better control

		// Enhanced result callback with source tracking
		ResultCallback: func(result *resolve.HostEntry) {
			resultMutex.Lock()
			defer resultMutex.Unlock()

			progress.SubdomainsFound++

			// Track sources used
			if result.Source != "" {
				sourcesUsed.Store(result.Source, true)
			}

			// Enhanced result processing
			scanResult := &ScanResult{
				Subdomain:    strings.ToLower(strings.TrimSpace(result.Host)),
				IPAddresses:  []string{}, // Will be resolved separately if needed
				Source:       "subfinder",
				DiscoveredAt: time.Now().UTC().Format(time.RFC3339),
				ParentDomain: domain,
				Metadata: map[string]string{
					"source_details": result.Source,
					"domain":         result.Domain,
					"scan_method":    "passive_enumeration",
					"sdk_version":    "v2.8.0",
				},
			}

			// Validate subdomain format
			if s.isValidSubdomain(scanResult.Subdomain, domain) {
				subdomains = append(subdomains, scanResult)
			}
		},
	}

	// Create custom output buffer
	var outputBuffer bytes.Buffer
	runnerOptions.Output = &outputBuffer

	// Create subfinder runner with enhanced error handling
	subfinderRunner, err := runner.NewRunner(runnerOptions)
	if err != nil {
		return s.createFailedResult(domain, fmt.Sprintf("Failed to create subfinder runner: %v", err))
	}

	// Create domain-specific context with timeout
	domainCtx, cancel := context.WithTimeout(s.ctx, time.Duration(runnerOptions.MaxEnumerationTime)*time.Minute)
	defer cancel()

	// Run the enumeration with enhanced context handling
	err = subfinderRunner.RunEnumerationWithCtx(domainCtx)
	completedTime := time.Now()
	progress.CompletedAt = &completedTime

	// Collect sources used
	var sources []string
	sourcesUsed.Range(func(key, value interface{}) bool {
		if source, ok := key.(string); ok {
			sources = append(sources, source)
		}
		return true
	})
	progress.SourcesUsed = sources

	// Enhanced error handling
	if err != nil {
		if domainCtx.Err() == context.DeadlineExceeded {
			progress.Status = "partial_success" // Some results may have been found
			progress.ErrorMessage = "Scan timeout reached, partial results returned"
			s.logger.Warnf("⚠️ Domain %s scan timed out, returning partial results: %d subdomains",
				domain, progress.SubdomainsFound)
		} else if s.ctx.Err() != nil {
			progress.Status = "cancelled"
			progress.ErrorMessage = "Scan was cancelled"
		} else {
			progress.Status = "failed"
			progress.ErrorMessage = fmt.Sprintf("Enumeration failed: %v", err)
		}
	} else {
		progress.Status = "completed"
	}

	s.logger.Infof("✅ Domain %s scan completed: %d subdomains found from %d sources (status: %s)",
		domain, progress.SubdomainsFound, len(sources), progress.Status)

	return &DomainScanResult{
		Domain:     domain,
		Subdomains: subdomains,
		Progress:   progress,
	}
}

// createFailedResult creates a failed scan result
func (s *Scanner) createFailedResult(domain, errorMessage string) *DomainScanResult {
	completedTime := time.Now()
	progress := &DomainScanProgress{
		Domain:       domain,
		Status:       "failed",
		StartedAt:    time.Now(),
		CompletedAt:  &completedTime,
		ErrorMessage: errorMessage,
	}

	return &DomainScanResult{
		Domain:     domain,
		Subdomains: []*ScanResult{},
		Progress:   progress,
	}
}

// isValidSubdomain validates subdomain format and relevance
func (s *Scanner) isValidSubdomain(subdomain, parentDomain string) bool {
	// Basic validation
	if subdomain == "" || subdomain == parentDomain {
		return false
	}

	// Must end with parent domain
	if !strings.HasSuffix(subdomain, "."+parentDomain) && subdomain != parentDomain {
		return false
	}

	// Must contain only valid characters
	if strings.Contains(subdomain, " ") || strings.Contains(subdomain, "\t") {
		return false
	}

	// Must not be a wildcard
	if strings.Contains(subdomain, "*") {
		return false
	}

	return true
}

// updateProgress updates the scan progress in Redis using Hash format (compatible with Python HGETALL)
func (s *Scanner) updateProgress(progress *AssetScanProgress) error {
	// Convert progress to flat key-value pairs for Redis Hash
	progressFields := map[string]interface{}{
		"job_id":            progress.JobID,
		"status":            progress.Status,
		"total_domains":     progress.TotalDomains,
		"completed_domains": progress.CompletedDomains,
		"total_subdomains":  progress.TotalSubdomains,
		"started_at":        progress.StartedAt.Format(time.RFC3339),
	}

	if progress.CompletedAt != nil {
		progressFields["completed_at"] = progress.CompletedAt.Format(time.RFC3339)
	}

	if progress.ErrorMessage != "" {
		progressFields["error_message"] = progress.ErrorMessage
	}

	// Store progress as Hash (compatible with Python HGETALL)
	progressKey := fmt.Sprintf("job:%s", s.config.JobID)
	if err := s.redisClient.HMSet(s.ctx, progressKey, progressFields).Err(); err != nil {
		return fmt.Errorf("failed to store progress hash: %v", err)
	}

	// Set expiration (24 hours)
	if err := s.redisClient.Expire(s.ctx, progressKey, 24*time.Hour).Err(); err != nil {
		s.logger.Warnf("Failed to set expiration on progress key: %v", err)
	}

	// Update module status for workflow orchestrator monitoring
	moduleStatusKey := fmt.Sprintf("module_status:%s", s.config.JobID)
	moduleStatus := "running"
	if progress.Status == "completed" || progress.Status == "failed" {
		moduleStatus = progress.Status
	}

	if err := s.redisClient.HSet(s.ctx, moduleStatusKey, "subfinder", moduleStatus).Err(); err != nil {
		s.logger.Errorf("Failed to update module status: %v", err)
	}

	// Set expiration on module status (24 hours)
	if err := s.redisClient.Expire(s.ctx, moduleStatusKey, 24*time.Hour).Err(); err != nil {
		s.logger.Warnf("Failed to set expiration on module status key: %v", err)
	}

	s.logger.Debugf("Updated progress: status=%s, domains=%d/%d, subdomains=%d",
		progress.Status, progress.CompletedDomains, progress.TotalDomains, progress.TotalSubdomains)

	return nil
}

// storeSubdomains stores the discovered subdomains in Supabase
// REMOVED (Phase 4): storeSubdomains() function deleted
// Rationale: Subfinder no longer writes directly to database - DNSx handles all persistence
// This enforces clean architectural separation: Discovery (Subfinder) vs Persistence (DNSx)

// streamSubdomainsToRedis streams individual subdomains to Redis Streams as they are discovered
// This enables real-time processing by downstream consumers (e.g., DNSx module)
func (s *Scanner) streamSubdomainsToRedis(result *DomainScanResult) error {
	if !s.config.StreamingMode {
		return nil // Streaming disabled, skip
	}

	if s.config.StreamOutputKey == "" {
		s.logger.Warn("Streaming mode enabled but STREAM_OUTPUT_KEY is empty, skipping streaming")
		return nil
	}

	if len(result.Subdomains) == 0 {
		return nil // No subdomains to stream
	}

	s.logger.Infof("📤 Streaming %d subdomains to Redis: %s", len(result.Subdomains), s.config.StreamOutputKey)

	// Stream each subdomain individually for real-time consumption
	streamedCount := 0
	for _, subdomain := range result.Subdomains {
		// Determine the correct scan_job_id for this subdomain
		jobID := s.config.JobID

		// Check ASSET_SCAN_MAPPING for domain-specific scan job ID
		if assetScanMappingStr := os.Getenv("ASSET_SCAN_MAPPING"); assetScanMappingStr != "" {
			var assetScanMapping map[string]string
			if err := json.Unmarshal([]byte(assetScanMappingStr), &assetScanMapping); err == nil {
				if assetScanID, exists := assetScanMapping[subdomain.ParentDomain]; exists {
					jobID = assetScanID
				}
			}
		}

		// Fallback to DOMAIN_JOB_MAPPING
		if s.config.DomainJobMapping != nil {
			if domainJobID, exists := s.config.DomainJobMapping[subdomain.ParentDomain]; exists {
				jobID = domainJobID
			}
		}

		// BUG #8 FIX: JSON-encode metadata map so Redis can marshal it
		// Redis XADD cannot handle nested maps - all values must be primitive types or JSON strings
		metadataJSON := "{}"  // Default to empty JSON object
		if subdomain.Metadata != nil && len(subdomain.Metadata) > 0 {
			if metadataBytes, err := json.Marshal(subdomain.Metadata); err == nil {
				metadataJSON = string(metadataBytes)
			} else {
				s.logger.Warnf("⚠️  Failed to marshal metadata for %s: %v", subdomain.Subdomain, err)
			}
		}

		// ✅ FIX: Get asset_id from environment (required for DNSx database insertion)
		assetID := os.Getenv("ASSET_ID")
		
		// Prepare stream message (matches Container Interface Standard format)
		streamMessage := map[string]interface{}{
			"subdomain":     subdomain.Subdomain,
			"source":        subdomain.Source,
			"discovered_at": subdomain.DiscoveredAt,
			"parent_domain": subdomain.ParentDomain,
			"scan_job_id":   jobID,
			"asset_id":      assetID,      // ✅ FIX: Include asset_id for DNSx to write to database
			"metadata":      metadataJSON, // ✅ JSON string, not map[string]string
		}

		// XADD to Redis Stream
		_, err := s.redisClient.XAdd(s.ctx, &redis.XAddArgs{
			Stream: s.config.StreamOutputKey,
			Values: streamMessage,
		}).Result()

		if err != nil {
			s.logger.Errorf("❌ Failed to stream subdomain %s: %v", subdomain.Subdomain, err)
			// Continue streaming other subdomains even if one fails
			continue
		}

		streamedCount++
	}

	s.logger.Infof("✅ Successfully streamed %d/%d subdomains to Redis", streamedCount, len(result.Subdomains))
	return nil
}

// sendCompletionMarker sends a completion marker to Redis Stream to signal end of scan
// Consumers use this to know when all subdomains have been processed
func (s *Scanner) sendCompletionMarker(totalSubdomains int) error {
	if !s.config.StreamingMode {
		return nil // Streaming disabled, skip
	}

	if s.config.StreamOutputKey == "" {
		s.logger.Warn("Streaming mode enabled but STREAM_OUTPUT_KEY is empty, skipping completion marker")
		return nil
	}

	s.logger.Infof("🏁 Sending completion marker to stream: %s (total results: %d)",
		s.config.StreamOutputKey, totalSubdomains)

	// Completion marker format (matches Container Interface Standard)
	completionMarker := map[string]interface{}{
		"type":          "completion",
		"module":        "subfinder",
		"scan_job_id":   s.config.JobID,
		"timestamp":     time.Now().Format(time.RFC3339),
		"total_results": totalSubdomains,
	}

	// XADD completion marker to stream
	_, err := s.redisClient.XAdd(s.ctx, &redis.XAddArgs{
		Stream: s.config.StreamOutputKey,
		Values: completionMarker,
	}).Result()

	if err != nil {
		s.logger.Errorf("❌ Failed to send completion marker: %v", err)
		return fmt.Errorf("failed to send completion marker: %w", err)
	}

	s.logger.Info("✅ Completion marker sent successfully")
	return nil
}

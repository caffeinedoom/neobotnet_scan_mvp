package main

import (
	"encoding/json"
	"fmt"
	"io"
	"log"
	"net/http"
	"net/url"
	"os"
	"strconv"
	"strings"
	"sync"
	"time"
)

// BackfillConfig holds configuration for backfill mode
type BackfillConfig struct {
	AssetID      string        // Required: asset to backfill
	BatchSize    int           // URLs per batch (default: 100)
	Concurrency  int           // Parallel probes per batch (default: 10)
	MaxURLs      int           // Max URLs to process (0 = unlimited)
	DelayBetween time.Duration // Delay between batches
	DryRun       bool          // If true, don't write to database
}

// HistoricalURL represents a row from historical_urls table
type HistoricalURL struct {
	ID           string  `json:"id"`
	URL          string  `json:"url"`
	AssetID      string  `json:"asset_id"`
	ParentDomain string  `json:"parent_domain"`
	Source       string  `json:"source"`
	ScanJobID    *string `json:"scan_job_id"`
	DiscoveredAt string  `json:"discovered_at"`
}

// BackfillResult holds statistics from backfill operation
type BackfillResult struct {
	TotalFetched   int
	URLsProbed     int
	URLsInserted   int
	URLsUpdated    int
	URLsSkipped    int // Already exist with fresh resolution
	URLsErrored    int
	ProcessingTime time.Duration
}

// runBackfillMode executes URL resolution in backfill mode
// Reads unprocessed URLs from historical_urls table and probes them
func runBackfillMode() error {
	log.Println("=" + strings.Repeat("=", 69))
	log.Println("🔄 URL Resolver Backfill Mode")
	log.Println("=" + strings.Repeat("=", 69))

	// Load configuration
	config, err := loadBackfillConfig()
	if err != nil {
		return fmt.Errorf("failed to load backfill config: %w", err)
	}

	printBackfillConfig(config)

	// Initialize Supabase client
	supabaseClient, err := NewSupabaseClient()
	if err != nil {
		return fmt.Errorf("failed to initialize Supabase client: %w", err)
	}

	log.Println("✅ Database connection established")

	// Start backfill process
	startTime := time.Now()
	result, err := executeBackfill(supabaseClient, config)
	if err != nil {
		return fmt.Errorf("backfill failed: %w", err)
	}

	result.ProcessingTime = time.Since(startTime)

	// Print summary
	printBackfillSummary(result)

	return nil
}

// loadBackfillConfig loads backfill configuration from environment
func loadBackfillConfig() (*BackfillConfig, error) {
	config := &BackfillConfig{
		AssetID:      os.Getenv("ASSET_ID"),
		BatchSize:    100,
		Concurrency:  10,
		MaxURLs:      0,
		DelayBetween: 1 * time.Second,
		DryRun:       os.Getenv("DRY_RUN") == "true",
	}

	if config.AssetID == "" {
		return nil, fmt.Errorf("ASSET_ID environment variable is required for backfill mode")
	}

	// Parse optional overrides
	if batchSize := os.Getenv("BATCH_SIZE"); batchSize != "" {
		if val, err := strconv.Atoi(batchSize); err == nil && val > 0 {
			config.BatchSize = val
		}
	}

	if concurrency := os.Getenv("CONCURRENCY"); concurrency != "" {
		if val, err := strconv.Atoi(concurrency); err == nil && val > 0 {
			config.Concurrency = val
		}
	}

	if maxURLs := os.Getenv("MAX_URLS"); maxURLs != "" {
		if val, err := strconv.Atoi(maxURLs); err == nil && val > 0 {
			config.MaxURLs = val
		}
	}

	return config, nil
}

// printBackfillConfig logs the backfill configuration
func printBackfillConfig(config *BackfillConfig) {
	log.Println("\n📋 Backfill Configuration:")
	log.Printf("  • Asset ID: %s", config.AssetID)
	log.Printf("  • Batch Size: %d URLs", config.BatchSize)
	log.Printf("  • Concurrency: %d parallel probes", config.Concurrency)
	if config.MaxURLs > 0 {
		log.Printf("  • Max URLs: %d", config.MaxURLs)
	} else {
		log.Printf("  • Max URLs: unlimited")
	}
	if config.DryRun {
		log.Printf("  • Mode: DRY RUN (no database writes)")
	}
	log.Println()
}

// executeBackfill performs the actual backfill operation
func executeBackfill(client *SupabaseClient, config *BackfillConfig) (*BackfillResult, error) {
	result := &BackfillResult{}

	offset := 0
	batchNum := 0

	for {
		batchNum++
		log.Printf("\n📦 Processing batch #%d (offset: %d)", batchNum, offset)

		// Fetch unprocessed URLs
		urls, err := getUnprocessedHistoricalURLs(client, config.AssetID, config.BatchSize, offset)
		if err != nil {
			return result, fmt.Errorf("failed to fetch URLs: %w", err)
		}

		if len(urls) == 0 {
			log.Println("✅ No more unprocessed URLs found")
			break
		}

		result.TotalFetched += len(urls)
		log.Printf("  📥 Fetched %d URLs to process", len(urls))

		// Process batch with concurrency
		batchResult := processBatchConcurrent(client, urls, config)

		result.URLsProbed += batchResult.Probed
		result.URLsInserted += batchResult.Inserted
		result.URLsUpdated += batchResult.Updated
		result.URLsSkipped += batchResult.Skipped
		result.URLsErrored += batchResult.Errored

		log.Printf("  ✅ Batch complete: %d probed, %d inserted, %d updated, %d skipped, %d errors",
			batchResult.Probed, batchResult.Inserted, batchResult.Updated, batchResult.Skipped, batchResult.Errored)

		// Check if we've hit max URLs limit
		if config.MaxURLs > 0 && result.TotalFetched >= config.MaxURLs {
			log.Printf("  🛑 Reached max URLs limit (%d)", config.MaxURLs)
			break
		}

		// Move to next batch
		offset += config.BatchSize

		// Delay between batches to avoid overwhelming target servers
		if config.DelayBetween > 0 {
			time.Sleep(config.DelayBetween)
		}
	}

	return result, nil
}

// BatchProcessResult holds results from processing a single batch
type BatchProcessResult struct {
	Probed   int
	Inserted int
	Updated  int
	Skipped  int
	Errored  int
}

// processBatchConcurrent processes a batch of URLs with concurrent probing
func processBatchConcurrent(client *SupabaseClient, urls []HistoricalURL, config *BackfillConfig) *BatchProcessResult {
	result := &BatchProcessResult{}

	// Create semaphore for concurrency control
	sem := make(chan struct{}, config.Concurrency)
	var wg sync.WaitGroup
	var mu sync.Mutex

	for i, histURL := range urls {
		wg.Add(1)
		sem <- struct{}{} // Acquire semaphore

		go func(idx int, hu HistoricalURL) {
			defer wg.Done()
			defer func() { <-sem }() // Release semaphore

			// Process single URL
			probeResult, action, err := processHistoricalURL(client, hu, config.DryRun)

			mu.Lock()
			defer mu.Unlock()

			if err != nil {
				log.Printf("    ❌ [%d] Error processing %s: %v", idx+1, truncateURL(hu.URL, 60), err)
				result.Errored++
				return
			}

			result.Probed++

			switch action {
			case "inserted":
				result.Inserted++
				if probeResult.IsAlive {
					log.Printf("    ✅ [%d] %d %s → %s", idx+1, probeResult.StatusCode, probeResult.ContentType, truncateURL(hu.URL, 50))
				} else {
					log.Printf("    ⚠️  [%d] No response → %s", idx+1, truncateURL(hu.URL, 50))
				}
			case "updated":
				result.Updated++
			case "skipped":
				result.Skipped++
			}
		}(i, histURL)
	}

	wg.Wait()
	return result
}

// processHistoricalURL probes a single historical URL and stores result
// Returns the probe result, action taken (inserted/updated/skipped), and any error
func processHistoricalURL(client *SupabaseClient, histURL HistoricalURL, dryRun bool) (*ProbeResult, string, error) {
	// Normalize URL and generate hash
	normalizedURL, urlHash, err := NormalizeAndHash(histURL.URL)
	if err != nil {
		return nil, "", fmt.Errorf("failed to normalize URL: %w", err)
	}

	// Check if URL already exists in urls table
	existing, err := client.GetURLByHash(histURL.AssetID, urlHash)
	if err != nil {
		return nil, "", fmt.Errorf("failed to check existing URL: %w", err)
	}

	// If exists and recently resolved (within 24h), skip
	if existing != nil && existing.ResolvedAt != nil {
		age := time.Since(*existing.ResolvedAt)
		if age < 24*time.Hour {
			return nil, "skipped", nil
		}
	}

	// Probe the URL
	probeResult := ProbeURL(histURL.URL)

	if dryRun {
		return probeResult, "skipped", nil
	}

	// Parse URL components
	domain, path, queryParams, fileExt, _ := ParseURLComponents(histURL.URL)

	// Prepare URL record
	now := time.Now().UTC()
	isAlive := probeResult.IsAlive
	statusCode := probeResult.StatusCode
	responseTime := probeResult.ResponseTimeMs

	if existing != nil {
		// Update existing record with new resolution data
		err = client.UpdateURLResolution(histURL.AssetID, urlHash, probeResult, &histURL.Source)
		if err != nil {
			return probeResult, "", fmt.Errorf("failed to update URL: %w", err)
		}
		return probeResult, "updated", nil
	}

	// Insert new record
	pathPtr := &path
	if path == "" || path == "/" {
		pathPtr = nil
	}

	record := &URLRecord{
		AssetID:           histURL.AssetID,
		URL:               normalizedURL,
		URLHash:           urlHash,
		Domain:            domain,
		Path:              pathPtr,
		QueryParams:       queryParams,
		Sources:           []string{histURL.Source},
		FirstDiscoveredBy: histURL.Source,
		FirstDiscoveredAt: now,
		ResolvedAt:        &now,
		IsAlive:           &isAlive,
		StatusCode:        &statusCode,
		ResponseTimeMs:    &responseTime,
		Technologies:      probeResult.Technologies,
		RedirectChain:     probeResult.RedirectChain,
		CreatedAt:         now,
		UpdatedAt:         now,
	}

	// Set optional fields
	if probeResult.ContentType != "" {
		record.ContentType = &probeResult.ContentType
	}
	if probeResult.ContentLength > 0 {
		record.ContentLength = &probeResult.ContentLength
	}
	if probeResult.Title != "" {
		record.Title = &probeResult.Title
	}
	if probeResult.FinalURL != "" {
		record.FinalURL = &probeResult.FinalURL
	}
	if probeResult.Webserver != "" {
		record.Webserver = &probeResult.Webserver
	}
	if fileExt != nil {
		record.FileExtension = fileExt
	}

	err = client.InsertURL(record)
	if err != nil {
		return probeResult, "", fmt.Errorf("failed to insert URL: %w", err)
	}

	return probeResult, "inserted", nil
}

// getUnprocessedHistoricalURLs fetches historical URLs that haven't been resolved yet
// Scans through historical_urls and filters out those already in urls table
func getUnprocessedHistoricalURLs(client *SupabaseClient, assetID string, limit, offset int) ([]HistoricalURL, error) {
	unprocessed := make([]HistoricalURL, 0, limit)
	currentOffset := offset
	maxIterations := 50 // Prevent infinite loops
	pageSize := 100     // Fetch in batches of 100

	for iteration := 0; iteration < maxIterations && len(unprocessed) < limit; iteration++ {
		// Fetch a page of historical URLs
		apiURL := fmt.Sprintf("%s/rest/v1/historical_urls?asset_id=eq.%s&order=discovered_at.asc&limit=%d&offset=%d",
			client.url, url.QueryEscape(assetID), pageSize, currentOffset)

		req, err := http.NewRequest("GET", apiURL, nil)
		if err != nil {
			return nil, fmt.Errorf("failed to create request: %w", err)
		}

		req.Header.Set("apikey", client.serviceKey)
		req.Header.Set("Authorization", fmt.Sprintf("Bearer %s", client.serviceKey))
		req.Header.Set("Content-Type", "application/json")

		resp, err := client.httpClient.Do(req)
		if err != nil {
			return nil, fmt.Errorf("failed to execute request: %w", err)
		}

		body, err := io.ReadAll(resp.Body)
		resp.Body.Close()

		if err != nil {
			return nil, fmt.Errorf("failed to read response: %w", err)
		}

		if resp.StatusCode != http.StatusOK {
			return nil, fmt.Errorf("HTTP %d: %s", resp.StatusCode, string(body))
		}

		var pageURLs []HistoricalURL
		if err := json.Unmarshal(body, &pageURLs); err != nil {
			return nil, fmt.Errorf("failed to parse response: %w", err)
		}

		// No more URLs to process
		if len(pageURLs) == 0 {
			break
		}

		// Filter to only unprocessed URLs (not in urls table)
		for _, hu := range pageURLs {
			// Normalize and hash to check
			_, urlHash, err := NormalizeAndHash(hu.URL)
			if err != nil {
				continue // Skip invalid URLs
			}

			// Check if exists in urls table
			existing, err := client.GetURLByHash(assetID, urlHash)
			if err != nil {
				continue // Skip on error
			}

			if existing == nil {
				unprocessed = append(unprocessed, hu)
				if len(unprocessed) >= limit {
					break
				}
			}
		}

		// Move to next page
		currentOffset += pageSize
	}

	return unprocessed, nil
}

// printBackfillSummary logs the final backfill summary
func printBackfillSummary(result *BackfillResult) {
	log.Println("\n" + strings.Repeat("=", 70))
	log.Println("📊 BACKFILL SUMMARY")
	log.Println(strings.Repeat("=", 70))
	log.Printf("  • Total URLs fetched: %d", result.TotalFetched)
	log.Printf("  • URLs probed: %d", result.URLsProbed)
	log.Printf("  • URLs inserted (new): %d", result.URLsInserted)
	log.Printf("  • URLs updated: %d", result.URLsUpdated)
	log.Printf("  • URLs skipped (fresh): %d", result.URLsSkipped)
	log.Printf("  • URLs errored: %d", result.URLsErrored)
	log.Printf("  • Processing time: %s", result.ProcessingTime.Round(time.Second))
	log.Println(strings.Repeat("=", 70))
}

// truncateURL shortens a URL for display
func truncateURL(u string, maxLen int) string {
	if len(u) <= maxLen {
		return u
	}
	return u[:maxLen-3] + "..."
}

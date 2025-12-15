package main

import (
	"crypto/sha256"
	"encoding/csv"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"log"
	"math"
	"net/url"
	"os"
	"os/signal"
	"sort"
	"strconv"
	"strings"
	"sync"
	"syscall"
	"time"

	"github.com/projectdiscovery/katana/pkg/engine/hybrid"
	"github.com/projectdiscovery/katana/pkg/output"
	"github.com/projectdiscovery/katana/pkg/types"
)

// ResultCapture stores all crawled results for analysis
type ResultCapture struct {
	Results []output.Result `json:"results"`
	Stats   Stats           `json:"stats"`
}

// Stats tracks crawl statistics
type Stats struct {
	TotalURLs       int     `json:"total_urls"`
	UniqueEndpoints int     `json:"unique_endpoints"`
	FormCount       int     `json:"form_count"`
	DepthMax        int     `json:"depth_max"`
	StartTime       string  `json:"start_time"`
	EndTime         string  `json:"end_time"`
	DurationSeconds float64 `json:"duration_seconds"`
}

// DeduplicatedResult represents a unique endpoint with metadata
type DeduplicatedResult struct {
	URL             string    `json:"url"`
	URLHash         string    `json:"url_hash"`
	Method          string    `json:"method"`
	SourceURL       string    `json:"source_url"`        // Which page linked to this endpoint
	StatusCode      *int      `json:"status_code"`
	ContentType     string    `json:"content_type"`
	ContentLength   *int64    `json:"content_length"`
	FirstSeenAt     time.Time `json:"first_seen_at"`
	LastSeenAt      time.Time `json:"last_seen_at"`
	TimesDiscovered int       `json:"times_discovered"`
	StatusCodes     []int     `json:"status_codes"`
	SourceURLs      []string  `json:"source_urls"`       // All sources that linked to this endpoint
}

// AnalysisReport provides insights into the crawl data
type AnalysisReport struct {
	Summary            Summary                  `json:"summary"`
	Duplicates         map[string]DuplicateInfo `json:"duplicates"`
	StatusDistribution map[string]int           `json:"status_distribution"`
	ContentTypeDistrib map[string]int           `json:"content_type_distribution"`
	FilteringRecommend FilteringRecommendations `json:"filtering_recommendations"`
}

type Summary struct {
	TotalDiscoveries int    `json:"total_discoveries"`
	UniqueURLs       int    `json:"unique_urls"`
	DuplicationRate  string `json:"duplication_rate"`
	CrawlDuration    string `json:"crawl_duration"`
}

type DuplicateInfo struct {
	TimesFound  int       `json:"times_found"`
	FirstSeen   time.Time `json:"first_seen"`
	LastSeen    time.Time `json:"last_seen"`
	StatusCodes []int     `json:"status_codes"`
	Reason      string    `json:"reason"`
}

type FilteringRecommendations struct {
	SelfReferentialCandidates int      `json:"self_referential_candidates"`
	FailedRequests            int      `json:"failed_requests"`
	SuggestedFilters          []string `json:"suggested_filters"`
}

// Global variables for signal handling
var (
	captureData  *ResultCapture
	captureMutex sync.Mutex
)

// normalizeURL normalizes a URL for consistent hashing
func normalizeURL(rawURL string) (string, error) {
	u, err := url.Parse(rawURL)
	if err != nil {
		return "", err
	}

	// Normalize hostname to lowercase
	u.Host = strings.ToLower(u.Host)
	u.Scheme = strings.ToLower(u.Scheme)

	// Remove fragment
	u.Fragment = ""

	// Sort query parameters for consistency
	if u.RawQuery != "" {
		q := u.Query()
		u.RawQuery = q.Encode()
	}

	// Remove trailing slash from path (unless it's just "/")
	if len(u.Path) > 1 && strings.HasSuffix(u.Path, "/") {
		u.Path = strings.TrimSuffix(u.Path, "/")
	}

	return u.String(), nil
}

// hashURL creates a SHA256 hash of a normalized URL
func hashURL(rawURL string) string {
	normalized, err := normalizeURL(rawURL)
	if err != nil {
		normalized = rawURL
	}
	h := sha256.Sum256([]byte(normalized))
	return hex.EncodeToString(h[:])
}

// deduplicateResults performs in-memory deduplication and analysis
func deduplicateResults(results []output.Result) map[string]*DeduplicatedResult {
	dedupMap := make(map[string]*DeduplicatedResult)

	for _, result := range results {
		urlHash := hashURL(result.Request.URL)

		if existing, exists := dedupMap[urlHash]; exists {
			// Update existing entry
			existing.LastSeenAt = result.Timestamp
			existing.TimesDiscovered++
			if result.Response != nil && result.Response.StatusCode > 0 {
				existing.StatusCodes = append(existing.StatusCodes, result.Response.StatusCode)
			}
			// Track additional source URLs
			if result.Request.Source != "" && result.Request.Source != existing.SourceURL {
				existing.SourceURLs = append(existing.SourceURLs, result.Request.Source)
			}
		} else {
			// Create new entry
			sourceURL := result.Request.Source
			if sourceURL == "" {
				sourceURL = "[seed]" // Mark seed URLs that weren't discovered from another page
			}
			
			dedup := &DeduplicatedResult{
				URL:             result.Request.URL,
				URLHash:         urlHash,
				Method:          result.Request.Method,
				SourceURL:       sourceURL,
				FirstSeenAt:     result.Timestamp,
				LastSeenAt:      result.Timestamp,
				TimesDiscovered: 1,
				StatusCodes:     []int{},
				SourceURLs:      []string{},
			}

			if result.Response != nil {
				if result.Response.StatusCode > 0 {
					dedup.StatusCode = &result.Response.StatusCode
					dedup.StatusCodes = append(dedup.StatusCodes, result.Response.StatusCode)
				}
				if result.Response.Headers != nil {
					if ct, ok := result.Response.Headers["content-type"]; ok {
						dedup.ContentType = ct
					} else if ct, ok := result.Response.Headers["Content-Type"]; ok {
						dedup.ContentType = ct
					}
				}
				if result.Response.ContentLength != 0 {
					cl := result.Response.ContentLength
					dedup.ContentLength = &cl
				}
			}

			dedupMap[urlHash] = dedup
		}
	}

	return dedupMap
}

// generateAnalysisReport creates a comprehensive analysis of the crawl data
func generateAnalysisReport(rawResults []output.Result, dedupResults map[string]*DeduplicatedResult, duration time.Duration) AnalysisReport {
	report := AnalysisReport{
		Duplicates:         make(map[string]DuplicateInfo),
		StatusDistribution: make(map[string]int),
		ContentTypeDistrib: make(map[string]int),
	}

	// Summary
	totalDiscoveries := len(rawResults)
	uniqueURLs := len(dedupResults)
	dupRate := 0.0
	if totalDiscoveries > 0 {
		dupRate = float64(totalDiscoveries-uniqueURLs) / float64(totalDiscoveries) * 100
	}

	report.Summary = Summary{
		TotalDiscoveries: totalDiscoveries,
		UniqueURLs:       uniqueURLs,
		DuplicationRate:  fmt.Sprintf("%.1f%%", dupRate),
		CrawlDuration:    duration.Round(time.Second).String(),
	}

	// Analyze duplicates and distributions
	failedRequests := 0
	selfRefCandidates := 0

	for _, dedup := range dedupResults {
		// Status distribution
		if dedup.StatusCode != nil {
			statusKey := fmt.Sprintf("%d", *dedup.StatusCode)
			report.StatusDistribution[statusKey]++
		} else {
			report.StatusDistribution["null"]++
			failedRequests++
		}

		// Content type distribution
		if dedup.ContentType != "" {
			// Simplify content type (remove charset, etc.)
			ct := strings.Split(dedup.ContentType, ";")[0]
			report.ContentTypeDistrib[ct]++
		}

		// Identify duplicates
		if dedup.TimesDiscovered > 1 {
			report.Duplicates[dedup.URL] = DuplicateInfo{
				TimesFound:  dedup.TimesDiscovered,
				FirstSeen:   dedup.FirstSeenAt,
				LastSeen:    dedup.LastSeenAt,
				StatusCodes: dedup.StatusCodes,
				Reason:      "Discovered multiple times (likely self-referential or common navigation)",
			}
			selfRefCandidates++
		}
	}

	// Generate filtering recommendations
	suggestions := []string{}
	if selfRefCandidates > 0 {
		suggestions = append(suggestions, fmt.Sprintf("Deduplicate within scan (%d URLs found multiple times, %.1f%% reduction)", selfRefCandidates, dupRate))
	}
	if failedRequests > 0 {
		suggestions = append(suggestions, fmt.Sprintf("Consider filtering failed requests (%d URLs with null status)", failedRequests))
	}
	if len(dedupResults) > 0 {
		suggestions = append(suggestions, "Store metadata only (no response bodies) to keep database lean")
	}

	report.FilteringRecommend = FilteringRecommendations{
		SelfReferentialCandidates: selfRefCandidates,
		FailedRequests:            failedRequests,
		SuggestedFilters:          suggestions,
	}

	return report
}

// saveDeduplicatedJSON saves deduplicated results to JSON file
func saveDeduplicatedJSON(dedupMap map[string]*DeduplicatedResult, filename string) error {
	// Convert map to slice for JSON output
	dedupSlice := make([]*DeduplicatedResult, 0, len(dedupMap))
	for _, result := range dedupMap {
		dedupSlice = append(dedupSlice, result)
	}

	// Sort by first seen time
	sort.Slice(dedupSlice, func(i, j int) bool {
		return dedupSlice[i].FirstSeenAt.Before(dedupSlice[j].FirstSeenAt)
	})

	output := map[string]interface{}{
		"results": dedupSlice,
		"summary": map[string]interface{}{
			"total_unique_urls": len(dedupSlice),
		},
	}

	file, err := os.Create(filename)
	if err != nil {
		return fmt.Errorf("failed to create deduplicated JSON: %w", err)
	}
	defer file.Close()

	encoder := json.NewEncoder(file)
	encoder.SetIndent("", "  ")
	if err := encoder.Encode(output); err != nil {
		return fmt.Errorf("failed to encode deduplicated JSON: %w", err)
	}

	return nil
}

// saveCSVMock saves a CSV representation of how data would be stored in database
func saveCSVMock(dedupMap map[string]*DeduplicatedResult, filename string) error {
	file, err := os.Create(filename)
	if err != nil {
		return fmt.Errorf("failed to create CSV file: %w", err)
	}
	defer file.Close()

	writer := csv.NewWriter(file)
	defer writer.Flush()

	// Header
	header := []string{
		"asset_id",
		"url",
		"url_hash",
		"method",
		"source_url",
		"status_code",
		"content_type",
		"content_length",
		"first_seen_at",
		"last_seen_at",
		"times_discovered",
	}
	if err := writer.Write(header); err != nil {
		return fmt.Errorf("failed to write CSV header: %w", err)
	}

	// Convert map to slice and sort
	dedupSlice := make([]*DeduplicatedResult, 0, len(dedupMap))
	for _, result := range dedupMap {
		dedupSlice = append(dedupSlice, result)
	}
	sort.Slice(dedupSlice, func(i, j int) bool {
		return dedupSlice[i].FirstSeenAt.Before(dedupSlice[j].FirstSeenAt)
	})

	// Write rows
	for _, result := range dedupSlice {
		statusCode := "NULL"
		if result.StatusCode != nil {
			statusCode = fmt.Sprintf("%d", *result.StatusCode)
		}

		contentLength := "NULL"
		if result.ContentLength != nil {
			contentLength = fmt.Sprintf("%d", *result.ContentLength)
		}

		row := []string{
			"1", // Mock asset_id
			result.URL,
			result.URLHash[:16] + "...", // Truncate hash for readability
			result.Method,
			result.SourceURL,
			statusCode,
			result.ContentType,
			contentLength,
			result.FirstSeenAt.Format(time.RFC3339),
			result.LastSeenAt.Format(time.RFC3339),
			fmt.Sprintf("%d", result.TimesDiscovered),
		}

		if err := writer.Write(row); err != nil {
			return fmt.Errorf("failed to write CSV row: %w", err)
		}
	}

	return nil
}

// saveAnalysisReport saves the analysis report to JSON
func saveAnalysisReport(report AnalysisReport, filename string) error {
	file, err := os.Create(filename)
	if err != nil {
		return fmt.Errorf("failed to create analysis report: %w", err)
	}
	defer file.Close()

	encoder := json.NewEncoder(file)
	encoder.SetIndent("", "  ")
	if err := encoder.Encode(report); err != nil {
		return fmt.Errorf("failed to encode analysis report: %w", err)
	}

	return nil
}

// saveResults saves all output formats
func saveResults(capture *ResultCapture, startTime time.Time) error {
	captureMutex.Lock()
	defer captureMutex.Unlock()

	endTime := time.Now()
	duration := endTime.Sub(startTime)
	capture.Stats.EndTime = endTime.Format(time.RFC3339)
	capture.Stats.DurationSeconds = duration.Seconds()
	capture.Stats.UniqueEndpoints = len(capture.Results)

	// Calculate actual unique count
	uniqueURLs := make(map[string]bool)
	for _, result := range capture.Results {
		urlHash := hashURL(result.Request.URL)
		uniqueURLs[urlHash] = true
	}
	capture.Stats.TotalURLs = len(capture.Results)
	capture.Stats.UniqueEndpoints = len(uniqueURLs)

	// Ensure output directory exists
	outputDir := "./output"
	if err := os.MkdirAll(outputDir, 0755); err != nil {
		return fmt.Errorf("failed to create output directory: %w", err)
	}

	// 1. Save raw results (everything Katana found)
	log.Println("💾 Saving raw results...")
	rawFile, err := os.Create(outputDir + "/results_raw.json")
	if err != nil {
		return fmt.Errorf("failed to create raw results file: %w", err)
	}
	defer rawFile.Close()

	encoder := json.NewEncoder(rawFile)
	encoder.SetIndent("", "  ")
	if err := encoder.Encode(capture); err != nil {
		return fmt.Errorf("failed to encode raw results: %w", err)
	}
	log.Printf("✅ Raw results saved: %d total discoveries", len(capture.Results))

	// 2. Perform deduplication
	log.Println("🔄 Deduplicating results...")
	dedupMap := deduplicateResults(capture.Results)
	log.Printf("✅ Deduplication complete: %d unique URLs", len(dedupMap))

	// 3. Save deduplicated JSON
	log.Println("💾 Saving deduplicated results...")
	if err := saveDeduplicatedJSON(dedupMap, outputDir+"/results_deduplicated.json"); err != nil {
		return err
	}
	log.Println("✅ Deduplicated results saved")

	// 4. Save CSV mock
	log.Println("💾 Saving database mock CSV...")
	if err := saveCSVMock(dedupMap, outputDir+"/database_mock.csv"); err != nil {
		return err
	}
	log.Println("✅ Database mock CSV saved")

	// 5. Generate and save analysis report
	log.Println("📊 Generating analysis report...")
	report := generateAnalysisReport(capture.Results, dedupMap, duration)
	if err := saveAnalysisReport(report, outputDir+"/analysis_report.json"); err != nil {
		return err
	}
	log.Println("✅ Analysis report saved")

	// Print summary
	log.Println("\n" + strings.Repeat("=", 60))
	log.Println("📊 CRAWL ANALYSIS SUMMARY")
	log.Println(strings.Repeat("=", 60))
	log.Printf("Total Discoveries:   %d", report.Summary.TotalDiscoveries)
	log.Printf("Unique URLs:         %d", report.Summary.UniqueURLs)
	log.Printf("Duplication Rate:    %s", report.Summary.DuplicationRate)
	log.Printf("Crawl Duration:      %s", report.Summary.CrawlDuration)
	log.Println(strings.Repeat("-", 60))
	log.Printf("Failed Requests:     %d", report.FilteringRecommend.FailedRequests)
	log.Printf("Duplicate URLs:      %d", report.FilteringRecommend.SelfReferentialCandidates)
	log.Println(strings.Repeat("=", 60))

	if len(report.FilteringRecommend.SuggestedFilters) > 0 {
		log.Println("\n💡 FILTERING RECOMMENDATIONS:")
		for i, suggestion := range report.FilteringRecommend.SuggestedFilters {
			log.Printf("  %d. %s", i+1, suggestion)
		}
	}

	log.Println("\n📁 Output files generated in ./output/:")
	log.Println("  - results_raw.json          (all discoveries)")
	log.Println("  - results_deduplicated.json (unique URLs only)")
	log.Println("  - database_mock.csv         (PostgreSQL preview)")
	log.Println("  - analysis_report.json      (detailed analysis)")

	return nil
}

func main() {
	log.Println("🕷️  Katana Test Container - v0.1")
	log.Println("=" + strings.Repeat("=", 69))

	startTime := time.Now()

	// ============================================================
	// 0. SETUP DURATION-BASED EXIT AND SIGNAL HANDLING
	// ============================================================
	// Get test duration from environment (default: 120 seconds)
	testDuration := 120
	if durationStr := os.Getenv("TEST_DURATION_SECONDS"); durationStr != "" {
		if parsed, err := strconv.Atoi(durationStr); err == nil && parsed > 0 {
			testDuration = parsed
		}
	}
	log.Printf("⏱️  Test will run for %d seconds", testDuration)

	// Setup timer for automatic shutdown
	shutdownTimer := time.NewTimer(time.Duration(testDuration) * time.Second)

	// Setup signal handling for external interrupts
	signalChan := make(chan os.Signal, 1)
	signal.Notify(signalChan, os.Interrupt, syscall.SIGTERM)

	// ============================================================
	// 1. LOAD TEST URLS FROM ENVIRONMENT
	// ============================================================
	urlsEnv := os.Getenv("TEST_URLS")
	if urlsEnv == "" {
		// Default to Nubank test URLs
		urlsEnv = "https://blog.nubank.com.br/,https://clojure-south.nubank.com.br/,https://keygen.share.nubank.com.br/"
		log.Println("ℹ️  No TEST_URLS provided, using default Nubank URLs")
	}

	var urls []string

	// Try parsing as comma-separated list first (new format)
	if strings.Contains(urlsEnv, ",") {
		for _, url := range strings.Split(urlsEnv, ",") {
			trimmed := strings.TrimSpace(url)
			if trimmed != "" {
				urls = append(urls, trimmed)
			}
		}
	} else if strings.HasPrefix(urlsEnv, "[") {
		// Fallback: Try parsing as JSON array (old format)
		if err := json.Unmarshal([]byte(urlsEnv), &urls); err != nil {
			// If not JSON, treat as single URL
			urls = []string{strings.TrimSpace(urlsEnv)}
		}
	} else {
		// Single URL
		urls = []string{strings.TrimSpace(urlsEnv)}
	}

	if len(urls) == 0 {
		log.Fatal("❌ No valid URLs found in TEST_URLS")
	}

	log.Printf("📋 Testing with %d URLs:", len(urls))
	for i, url := range urls {
		log.Printf("   [%d] %s", i+1, url)
	}
	log.Println()

	// ============================================================
	// 2. INITIALIZE RESULT COLLECTOR
	// ============================================================
	capture := &ResultCapture{
		Results: []output.Result{},
		Stats: Stats{
			StartTime: startTime.Format(time.RFC3339),
		},
	}
	captureData = capture // Set global for signal handler

	// Setup graceful shutdown handler (for both timer and signals)
	go func() {
		select {
		case <-shutdownTimer.C:
			log.Printf("\n⏱️  Test duration reached (%d seconds)", testDuration)
			log.Println("💾 Saving results before shutdown...")

			if err := saveResults(capture, startTime); err != nil {
				log.Printf("❌ Failed to save results: %v", err)
				os.Exit(1)
			}

			log.Println("✅ Test complete")
			os.Exit(0)

		case sig := <-signalChan:
			log.Printf("\n⏸️  Received signal: %v", sig)
			log.Println("💾 Saving partial results before shutdown...")

			if err := saveResults(capture, startTime); err != nil {
				log.Printf("❌ Failed to save results: %v", err)
				os.Exit(1)
			}

			log.Println("✅ Graceful shutdown complete")
			os.Exit(0)
		}
	}()

	// ============================================================
	// 3. CONFIGURE KATANA OPTIONS
	// ============================================================
	log.Println("⚙️  Configuring Katana crawler...")

	options := &types.Options{
		// Crawling Strategy
		MaxDepth:   1, // Depth-1 for testing
		Strategy:   "depth-first",
		FieldScope: "rdn", // Registered Domain Name

		// Performance (conservative for testing)
		Concurrency: 2,  // 2 concurrent crawlers
		Parallelism: 2,  // 2 URL processors
		Timeout:     30, // 30 seconds per request
		Delay:       0,  // No delay between requests
		RateLimit:   50, // 50 requests/second
		TimeStable:  5,  // 5 seconds to wait for DOM stability

		// Headless Configuration
		Headless:           true, // Enable headless mode
		UseInstalledChrome: true, // Use system Chromium
		SystemChromePath:   "/usr/bin/chromium-browser",
		HeadlessNoSandbox:  true,  // REQUIRED for containers
		ShowBrowser:        false, // Don't show browser window

		// JavaScript Parsing
		ScrapeJSResponses: true, // Parse JS files for endpoints

		// Extension Filtering (match your command)
		ExtensionFilter: []string{
			".css", ".jpg", ".jpeg", ".png", ".svg", ".gif",
			".mp4", ".flv", ".ogv", ".webm", ".webp", ".mov",
			".mp3", ".m4a", ".m4p", ".scss", ".tif", ".tiff",
			".ttf", ".otf", ".woff", ".woff2", ".bmp", ".ico",
			".eot", ".htc", ".rtf", ".swf",
		},

		// Output Configuration
		JSON:     true,  // JSON output format
		NoColors: true,  // No ANSI colors
		Silent:   false, // Show progress
		Verbose:  true,  // Verbose logging for debugging

		// Body read size
		BodyReadSize: math.MaxInt, // Read full response bodies

		// Callback for each discovered endpoint
		OnResult: func(result output.Result) {
			// Store result for analysis (thread-safe)
			captureMutex.Lock()
			capture.Results = append(capture.Results, result)
			captureMutex.Unlock()

			// Log to console
			if result.Request != nil {
				log.Printf("🔗 Found: %s (Depth: %d, Method: %s)",
					result.Request.URL,
					result.Request.Depth,
					result.Request.Method)

				// Log source if available
				if result.Request.Source != "" {
					log.Printf("   └─ Source: %s", result.Request.Source)
				}
			}

			// Log response info if available
			if result.Response != nil {
				log.Printf("   └─ Status: %d, Length: %d bytes",
					result.Response.StatusCode,
					result.Response.ContentLength)

				// Log forms if found
				if len(result.Response.Forms) > 0 {
					log.Printf("   └─ Forms: %d", len(result.Response.Forms))
				}

				// Log technologies if detected
				if len(result.Response.Technologies) > 0 {
					log.Printf("   └─ Tech: %v", result.Response.Technologies)
				}
			}

			// Update stats
			capture.Stats.TotalURLs++
			if result.Request != nil && result.Request.Depth > capture.Stats.DepthMax {
				capture.Stats.DepthMax = result.Request.Depth
			}
			if result.Response != nil && len(result.Response.Forms) > 0 {
				capture.Stats.FormCount += len(result.Response.Forms)
			}
		},
	}

	log.Println("✅ Configuration complete")
	log.Printf("   • Max Depth: %d", options.MaxDepth)
	log.Printf("   • Headless: %v", options.Headless)
	log.Printf("   • Concurrency: %d", options.Concurrency)
	log.Printf("   • Chrome Path: %s", options.SystemChromePath)
	log.Println()

	// ============================================================
	// 4. CREATE CRAWLER
	// ============================================================
	log.Println("🔧 Initializing Katana crawler...")

	crawlerOptions, err := types.NewCrawlerOptions(options)
	if err != nil {
		log.Fatalf("❌ Failed to create crawler options: %v", err)
	}
	defer crawlerOptions.Close()

	// Use hybrid crawler (headless mode with Chromium)
	crawler, err := hybrid.New(crawlerOptions)
	if err != nil {
		log.Fatalf("❌ Failed to create hybrid crawler: %v\n"+
			"   This usually means Chromium is not properly installed or configured.\n"+
			"   Check that /usr/bin/chromium-browser exists.", err)
	}
	defer crawler.Close()

	log.Println("✅ Crawler initialized successfully")
	log.Println()

	// ============================================================
	// 5. CRAWL EACH URL
	// ============================================================
	log.Println("🌊 Starting crawl...")
	log.Println(strings.Repeat("-", 70))

	for i, url := range urls {
		log.Printf("\n📍 Crawling [%d/%d]: %s", i+1, len(urls), url)
		log.Println(strings.Repeat("-", 70))

		urlStartTime := time.Now()

		if err := crawler.Crawl(url); err != nil {
			log.Printf("⚠️  Crawl failed for %s: %v", url, err)
			continue
		}

		urlDuration := time.Since(urlStartTime)
		log.Printf("✅ Completed %s in %.2f seconds", url, urlDuration.Seconds())
	}

	log.Println()
	log.Println(strings.Repeat("=", 70))

	// ============================================================
	// 6. SAVE RESULTS TO FILE
	// ============================================================
	log.Println("💾 Saving results to file...")

	if err := saveResults(capture, startTime); err != nil {
		log.Fatalf("❌ Failed to save results: %v", err)
	}
	log.Println()

	// ============================================================
	// 7. PRINT SUMMARY
	// ============================================================
	log.Println(strings.Repeat("=", 70))
	log.Println("📊 CRAWL SUMMARY")
	log.Println(strings.Repeat("=", 70))
	log.Printf("Start Time:         %s", capture.Stats.StartTime)
	log.Printf("End Time:           %s", capture.Stats.EndTime)
	log.Printf("Duration:           %.2f seconds", capture.Stats.DurationSeconds)
	log.Printf("Total URLs Found:   %d", capture.Stats.TotalURLs)
	log.Printf("Unique Endpoints:   %d", capture.Stats.UniqueEndpoints)
	log.Printf("Forms Discovered:   %d", capture.Stats.FormCount)
	log.Printf("Max Depth Reached:  %d", capture.Stats.DepthMax)
	log.Println(strings.Repeat("=", 70))
	log.Println()
	log.Println("✅ Test completed successfully!")
	log.Println("📝 Next step: Analyze output/results.json to design database schema")
}

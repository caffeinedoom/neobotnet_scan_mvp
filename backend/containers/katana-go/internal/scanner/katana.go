package scanner

import (
	"context"
	"fmt"
	"strings"
	"sync"
	"time"

	"katana-go/internal/config"
	"katana-go/internal/dedup"
	"katana-go/internal/models"

	"github.com/projectdiscovery/katana/pkg/engine/hybrid"
	"github.com/projectdiscovery/katana/pkg/engine/standard"
	"github.com/projectdiscovery/katana/pkg/output"
	"github.com/projectdiscovery/katana/pkg/types"
)

// Crawler is an interface that both hybrid and standard crawlers implement
type Crawler interface {
	Crawl(string) error
	Close() error
}

// Scanner wraps Katana crawler functionality
type Scanner struct {
	cfg     *config.Config
	logger  *config.Logger
	engine  Crawler
	results []*models.CrawledEndpoint
	mu      sync.Mutex
}

// NewScanner creates a new Katana scanner instance
func NewScanner(cfg *config.Config, logger *config.Logger) (*Scanner, error) {
	scanner := &Scanner{
		cfg:     cfg,
		logger:  logger,
		results: make([]*models.CrawledEndpoint, 0),
	}

	// Initialize Katana options with result callback
	options := &types.Options{
		MaxDepth:         cfg.CrawlDepth,
		RateLimit:        cfg.RateLimit,
		Concurrency:      cfg.Concurrency,
		Parallelism:      cfg.Parallelism,
		Timeout:          cfg.Timeout,
		Headless:         cfg.HeadlessMode,
		SystemChromePath: "/usr/bin/chromium-browser", // CRITICAL: Use system Chromium instead of auto-download
		Strategy:         cfg.Strategy,
		DisplayOutScope:  false, // Don't display out-of-scope URLs
		FieldScope:       "rdn",  // Restrict to registered domain name
		NoScope:          false,  // Enable scope restrictions
		Silent:           true,   // Suppress Katana's built-in output
		Verbose:          false,
		
		// Callback to collect results
		OnResult: func(result output.Result) {
			endpoint := scanner.resultToEndpoint(result)
			if endpoint != nil {
				scanner.mu.Lock()
				scanner.results = append(scanner.results, endpoint)
				scanner.mu.Unlock()
			}
		},
	}

	// Create crawler options
	crawlerOptions, err := types.NewCrawlerOptions(options)
	if err != nil {
		return nil, fmt.Errorf("failed to create crawler options: %w", err)
	}

	// Choose crawler based on headless mode
	// - Headless=true: Use hybrid crawler (requires Chromium for JavaScript rendering)
	// - Headless=false: Use standard crawler (pure HTTP, faster, no browser needed)
	var crawler Crawler
	if cfg.HeadlessMode {
		logger.Info("Using HYBRID crawler (headless Chrome for JS rendering)")
		hybridCrawler, err := hybrid.New(crawlerOptions)
		if err != nil {
			crawlerOptions.Close()
			return nil, fmt.Errorf("failed to initialize Katana hybrid crawler: %w", err)
		}
		crawler = hybridCrawler
	} else {
		logger.Info("Using STANDARD crawler (pure HTTP, no browser)")
		standardCrawler, err := standard.New(crawlerOptions)
		if err != nil {
			crawlerOptions.Close()
			return nil, fmt.Errorf("failed to initialize Katana standard crawler: %w", err)
		}
		crawler = standardCrawler
	}

	scanner.engine = crawler

	logger.Info("Initialized Katana scanner: depth=%d, headless=%v, rate=%d, concurrency=%d",
		cfg.CrawlDepth, cfg.HeadlessMode, cfg.RateLimit, cfg.Concurrency)

	return scanner, nil
}

// Crawl performs web crawling on the given seed URLs and returns discovered endpoints
func (s *Scanner) Crawl(ctx context.Context, seedURLs []string) ([]*models.CrawledEndpoint, error) {
	if len(seedURLs) == 0 {
		return nil, fmt.Errorf("no seed URLs provided for crawling")
	}

	s.logger.Info("Starting crawl: seed_count=%d, depth=%d", len(seedURLs), s.cfg.CrawlDepth)

	// Clear previous results
	s.mu.Lock()
	s.results = make([]*models.CrawledEndpoint, 0)
	s.mu.Unlock()

	// Process each seed URL
	for i, seedURL := range seedURLs {
		select {
		case <-ctx.Done():
			s.logger.Warn("Crawl cancelled by context: processed=%d/%d", i, len(seedURLs))
			return s.getResults(), ctx.Err()
		default:
			s.logger.Debug("Crawling [%d/%d]: %s", i+1, len(seedURLs), seedURL)

			// Add seed URL itself as an endpoint
			seedEndpoint := s.createSeedEndpoint(seedURL)
			s.mu.Lock()
			s.results = append(s.results, seedEndpoint)
			s.mu.Unlock()

			// Execute crawl (results come through the OnResult callback)
			if err := s.engine.Crawl(seedURL); err != nil {
				s.logger.Error("Failed to crawl URL %s: %v", seedURL, err)
				// Continue with other URLs even if one fails
				continue
			}
		}
	}

	results := s.getResults()
	s.logger.Info("Crawl completed: seed_urls=%d, endpoints_found=%d",
		len(seedURLs), len(results))

	return results, nil
}

// getResults returns a copy of collected results
func (s *Scanner) getResults() []*models.CrawledEndpoint {
	s.mu.Lock()
	defer s.mu.Unlock()
	results := make([]*models.CrawledEndpoint, len(s.results))
	copy(results, s.results)
	return results
}

// resultToEndpoint converts a Katana output result to our CrawledEndpoint model
func (s *Scanner) resultToEndpoint(result output.Result) *models.CrawledEndpoint {
	if result.Request == nil {
		return nil
	}

	rawURL := result.Request.URL
	if rawURL == "" {
		return nil
	}
	
	// Normalize and hash the URL
	normalized, hash, err := dedup.NormalizeAndHash(rawURL)
	if err != nil {
		s.logger.Warn("Failed to normalize URL %s: %v", rawURL, err)
		return nil
	}

	// Extract method (default to GET)
	method := strings.ToUpper(result.Request.Method)
	if method == "" {
		method = "GET"
	}

	// Extract source URL
	var sourceURL *string
	if result.Request.Source != "" {
		sourceURL = &result.Request.Source
	}

	// Extract status code
	var statusCode *int
	if result.Response != nil && result.Response.StatusCode > 0 {
		sc := result.Response.StatusCode
		statusCode = &sc
	}

	// Extract content type
	var contentType *string
	if result.Response != nil {
		if ct, ok := result.Response.Headers["Content-Type"]; ok && ct != "" {
			contentType = &ct
		}
	}

	// Extract content length
	var contentLength *int64
	if result.Response != nil && result.Response.ContentLength > 0 {
		cl := int64(result.Response.ContentLength)
		contentLength = &cl
	}

	now := time.Now()

	endpoint := &models.CrawledEndpoint{
		AssetID:         s.cfg.AssetID,
		ScanJobID:       &s.cfg.ScanJobID,
		URL:             normalized,
		URLHash:         hash,
		Method:          method,
		SourceURL:       sourceURL,
		IsSeedURL:       false,
		StatusCode:      statusCode,
		ContentType:     contentType,
		ContentLength:   contentLength,
		FirstSeenAt:     now,
		LastSeenAt:      now,
		TimesDiscovered: 1,
	}

	return endpoint
}

// createSeedEndpoint creates an endpoint entry for a seed URL
func (s *Scanner) createSeedEndpoint(seedURL string) *models.CrawledEndpoint {
	// Normalize and hash
	normalized, hash, err := dedup.NormalizeAndHash(seedURL)
	if err != nil {
		s.logger.Warn("Failed to normalize seed URL %s: %v", seedURL, err)
		// Use original URL if normalization fails
		normalized = seedURL
		hash = dedup.HashURL(seedURL)
	}

	now := time.Now()

	endpoint := &models.CrawledEndpoint{
		AssetID:         s.cfg.AssetID,
		ScanJobID:       &s.cfg.ScanJobID,
		URL:             normalized,
		URLHash:         hash,
		Method:          "GET",
		SourceURL:       nil, // Seed URLs have no source
		IsSeedURL:       true,
		StatusCode:      nil, // Will be filled by HTTPx data if available
		ContentType:     nil,
		ContentLength:   nil,
		FirstSeenAt:     now,
		LastSeenAt:      now,
		TimesDiscovered: 1,
	}

	return endpoint
}

// Close cleans up scanner resources
func (s *Scanner) Close() error {
	if s.engine != nil {
		if err := s.engine.Close(); err != nil {
			s.logger.Warn("Error closing scanner engine: %v", err)
			return err
		}
	}
	s.logger.Debug("Scanner closed")
	return nil
}


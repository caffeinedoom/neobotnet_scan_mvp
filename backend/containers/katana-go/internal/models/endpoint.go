package models

import (
	"time"
)

// CrawledEndpoint represents a discovered web endpoint
type CrawledEndpoint struct {
	ID              string    `json:"id"`
	AssetID         string    `json:"asset_id"`
	ScanJobID       *string   `json:"scan_job_id"`
	URL             string    `json:"url"`
	URLHash         string    `json:"url_hash"`
	Method          string    `json:"method"`
	SourceURL       *string   `json:"source_url"`
	IsSeedURL       bool      `json:"is_seed_url"`
	StatusCode      *int      `json:"status_code"`
	ContentType     *string   `json:"content_type"`
	ContentLength   *int64    `json:"content_length"`
	FirstSeenAt     time.Time `json:"first_seen_at"`
	LastSeenAt      time.Time `json:"last_seen_at"`
	TimesDiscovered int       `json:"times_discovered"`
	CreatedAt       time.Time `json:"created_at"`
}

// NewCrawledEndpoint creates a new endpoint with defaults
func NewCrawledEndpoint(assetID, url, urlHash string, isSeedURL bool) *CrawledEndpoint {
	now := time.Now()
	method := "GET"

	return &CrawledEndpoint{
		AssetID:         assetID,
		URL:             url,
		URLHash:         urlHash,
		Method:          method,
		IsSeedURL:       isSeedURL,
		FirstSeenAt:     now,
		LastSeenAt:      now,
		TimesDiscovered: 1,
		CreatedAt:       now,
	}
}

// WithSourceURL sets the source URL
func (e *CrawledEndpoint) WithSourceURL(sourceURL string) *CrawledEndpoint {
	e.SourceURL = &sourceURL
	return e
}

// WithScanJobID sets the scan job ID
func (e *CrawledEndpoint) WithScanJobID(scanJobID string) *CrawledEndpoint {
	e.ScanJobID = &scanJobID
	return e
}

// WithStatusCode sets the HTTP status code
func (e *CrawledEndpoint) WithStatusCode(statusCode int) *CrawledEndpoint {
	e.StatusCode = &statusCode
	return e
}

// WithContentType sets the content type
func (e *CrawledEndpoint) WithContentType(contentType string) *CrawledEndpoint {
	e.ContentType = &contentType
	return e
}

// WithContentLength sets the content length
func (e *CrawledEndpoint) WithContentLength(contentLength int64) *CrawledEndpoint {
	e.ContentLength = &contentLength
	return e
}

// HTTPProbe represents an HTTP probe from the database (seed URL source)
type HTTPProbe struct {
	ID           string  `json:"id"`
	ScanJobID    string  `json:"scan_job_id"`
	AssetID      string  `json:"asset_id"`
	URL          string  `json:"url"`
	FinalURL     *string `json:"final_url"` // URL after redirects (nullable)
	StatusCode   int     `json:"status_code"`
	Subdomain    string  `json:"subdomain"`
	ParentDomain string  `json:"parent_domain"`
	Scheme       string  `json:"scheme"`
	Port         int     `json:"port"`
}

// ApexDomain represents an apex domain for scope control
type ApexDomain struct {
	ID       string `json:"id"`
	AssetID  string `json:"asset_id"`
	Domain   string `json:"domain"`
	IsActive bool   `json:"is_active"`
}

// CrawlStats tracks crawl statistics for logging
type CrawlStats struct {
	SeedURLs          int
	EndpointsFound    int
	UniqueEndpoints   int
	DuplicatesSkipped int
	Errors            int
	StartTime         time.Time
	EndTime           time.Time
}

// NewCrawlStats creates a new stats tracker
func NewCrawlStats(seedURLCount int) *CrawlStats {
	return &CrawlStats{
		SeedURLs:  seedURLCount,
		StartTime: time.Now(),
	}
}

// Duration returns the crawl duration
func (s *CrawlStats) Duration() time.Duration {
	if s.EndTime.IsZero() {
		return time.Since(s.StartTime)
	}
	return s.EndTime.Sub(s.StartTime)
}

// Finish marks the crawl as complete
func (s *CrawlStats) Finish() {
	s.EndTime = time.Now()
}

// ToMap converts stats to a map for logging
func (s *CrawlStats) ToMap() map[string]interface{} {
	return map[string]interface{}{
		"seed_urls":           s.SeedURLs,
		"endpoints_found":     s.EndpointsFound,
		"unique_endpoints":    s.UniqueEndpoints,
		"duplicates_skipped":  s.DuplicatesSkipped,
		"errors":              s.Errors,
		"duration_seconds":    s.Duration().Seconds(),
		"crawl_rate_per_sec":  float64(s.EndpointsFound) / s.Duration().Seconds(),
	}
}


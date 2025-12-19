package main

import (
	"time"
)

// URLRecord represents a URL record in the urls table
type URLRecord struct {
	// Primary key
	ID string `json:"id,omitempty"`

	// Foreign keys
	AssetID   string  `json:"asset_id"`
	ScanJobID *string `json:"scan_job_id,omitempty"`

	// Core URL data
	URL         string                 `json:"url"`
	URLHash     string                 `json:"url_hash"`
	Domain      string                 `json:"domain"`
	Path        *string                `json:"path,omitempty"`
	QueryParams map[string]interface{} `json:"query_params"`

	// Discovery tracking
	Sources           []string  `json:"sources"`
	FirstDiscoveredBy string    `json:"first_discovered_by"`
	FirstDiscoveredAt time.Time `json:"first_discovered_at"`

	// Resolution metadata (populated by URL Resolver)
	ResolvedAt     *time.Time `json:"resolved_at,omitempty"`
	IsAlive        *bool      `json:"is_alive,omitempty"`
	StatusCode     *int       `json:"status_code,omitempty"`
	ContentType    *string    `json:"content_type,omitempty"`
	ContentLength  *int       `json:"content_length,omitempty"`
	ResponseTimeMs *int       `json:"response_time_ms,omitempty"`

	// Enrichment data
	Title         *string  `json:"title,omitempty"`
	FinalURL      *string  `json:"final_url,omitempty"`
	RedirectChain []int    `json:"redirect_chain"`
	Webserver     *string  `json:"webserver,omitempty"`
	Technologies  []string `json:"technologies"`

	// Classification
	FileExtension *string `json:"file_extension,omitempty"`

	// Timestamps
	CreatedAt time.Time `json:"created_at"`
	UpdatedAt time.Time `json:"updated_at"`
}

// URLMessage represents a URL message from the stream (from Katana, Waymore, etc.)
type URLMessage struct {
	URL          string `json:"url"`
	AssetID      string `json:"asset_id"`
	Source       string `json:"source"`
	SourceID     string `json:"source_id,omitempty"` // Optional: reference to source table
	DiscoveredAt string `json:"discovered_at"`
	ScanJobID    string `json:"scan_job_id,omitempty"`
}

// ProbeResult represents the result of probing a single URL
type ProbeResult struct {
	URL            string
	IsAlive        bool
	StatusCode     int
	ContentType    string
	ContentLength  int
	ResponseTimeMs int
	Title          string
	FinalURL       string
	RedirectChain  []int
	Webserver      string
	Technologies   []string
	Error          error
}

// StreamingConfig holds configuration for streaming consumer mode
type StreamingConfig struct {
	StreamInputKey    string        // Redis Stream to read from
	ConsumerGroupName string        // Consumer group name
	ConsumerName      string        // Unique consumer identifier
	BatchSize         int64         // Number of messages to read per XREADGROUP call
	BlockMilliseconds int64         // XREADGROUP blocking time in milliseconds
	RedisHost         string
	RedisPort         string
	RedisPassword     string
	ScanJobID         string
	AssetID           string
	MaxProcessingTime time.Duration // Maximum time to wait for completion marker
	ResolutionTTL     time.Duration // TTL for skipping recently resolved URLs
	ProbeBatchSize    int           // Number of URLs to probe in parallel
}

// ConsumeStreamResult holds statistics from stream consumption
type ConsumeStreamResult struct {
	URLsReceived   int
	URLsProbed     int
	URLsSkipped    int // Skipped due to TTL (fresh)
	URLsInserted   int
	URLsUpdated    int
	ProcessingTime time.Duration
}


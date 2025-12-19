package models

import "time"

// DiscoveredURL represents a URL discovered from VirusTotal's domain report
type DiscoveredURL struct {
	ID           string    `json:"id,omitempty"`
	ScanJobID    string    `json:"scan_job_id"`
	AssetID      string    `json:"asset_id"`
	Subdomain    string    `json:"subdomain"`     // The queried subdomain (e.g., api.example.com)
	URL          string    `json:"url"`           // The discovered URL
	Positives    int       `json:"positives"`     // Number of AV detections
	Total        int       `json:"total"`         // Total AV engines
	ScanDate     string    `json:"vt_scan_date"`  // VT's scan date for this URL
	Source       string    `json:"source"`        // Always "virustotal"
	DiscoveredAt time.Time `json:"discovered_at"`
}

// DomainResult represents the VT API response for a domain query
type DomainResult struct {
	Domain         string           `json:"domain"`
	ResponseCode   int              `json:"response_code"`
	UndetectedURLs []UndetectedURL  `json:"undetected_urls,omitempty"`
	Timestamp      time.Time        `json:"timestamp"`
}

// UndetectedURL represents a single URL from VT's undetected_urls array
type UndetectedURL struct {
	URL          string    `json:"url"`
	Positives    int       `json:"positives"`
	Total        int       `json:"total"`
	ScanDate     string    `json:"scan_date"`
	LastModified time.Time `json:"last_modified"`
}

// StreamMessage represents a message consumed from HTTPx stream
type StreamMessage struct {
	URL         string `json:"url"`
	Subdomain   string `json:"subdomain"`
	StatusCode  int    `json:"status_code"`
	Title       string `json:"title"`
	AssetID     string `json:"asset_id"`
	ScanJobID   string `json:"scan_job_id"`
	Source      string `json:"source"`
	PublishedAt string `json:"published_at"`
}

// ConsumeResult holds statistics from stream consumption
type ConsumeResult struct {
	SubdomainsReceived int
	SubdomainsQueried  int
	URLsDiscovered     int
	URLsStored         int
	URLsPublished      int
	ProcessingTime     time.Duration
}


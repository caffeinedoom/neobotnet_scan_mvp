package main

import "time"

// DiscoveredURL represents a URL discovered by Waymore
type DiscoveredURL struct {
	URL              string            `json:"url"`
	ParentDomain     string            `json:"parent_domain"`
	Source           string            `json:"source"`
	ArchiveTimestamp *time.Time        `json:"archive_timestamp,omitempty"`
	AssetID          string            `json:"asset_id"`
	ScanJobID        string            `json:"scan_job_id"`
	DiscoveredAt     string            `json:"discovered_at"`
	Metadata         map[string]string `json:"metadata,omitempty"`
}

// BatchConfig holds configuration for batch mode execution
type BatchConfig struct {
	BatchID          string            `json:"batch_id"`
	AssetID          string            `json:"asset_id"`
	ScanJobID        string            `json:"scan_job_id"`
	UserID           string            `json:"user_id"`
	BatchDomains     []string          `json:"batch_domains"`
	AssetScanMapping map[string]string `json:"asset_scan_mapping"`
	TotalDomains     int               `json:"total_domains"`
	BatchOffset      int               `json:"batch_offset"`
	BatchLimit       int               `json:"batch_limit"`
}

// StreamingConfig holds configuration for streaming mode execution
type StreamingConfig struct {
	StreamOutputKey   string        `json:"stream_output_key"`
	RedisHost         string        `json:"redis_host"`
	RedisPort         string        `json:"redis_port"`
	RedisPassword     string        `json:"redis_password,omitempty"`
	ScanJobID         string        `json:"scan_job_id"`
	AssetID           string        `json:"asset_id"`
	BatchSize         int64         `json:"batch_size"`
	MaxProcessingTime time.Duration `json:"max_processing_time"`
}

// ScanConfig holds general scan configuration
type ScanConfig struct {
	ScanJobID  string   `json:"scan_job_id"`
	UserID     string   `json:"user_id"`
	AssetID    string   `json:"asset_id"`
	Domains    []string `json:"domains"`
	Limit      int      `json:"limit"`
	Providers  []string `json:"providers"`
	ConfigPath string   `json:"config_path"`
	Timeout    int      `json:"timeout"` // Minutes
}

// ScanResult holds the result of a domain scan
type ScanResult struct {
	Domain       string          `json:"domain"`
	URLs         []DiscoveredURL `json:"urls"`
	TotalURLs    int             `json:"total_urls"`
	Duration     time.Duration   `json:"duration"`
	Error        error           `json:"error,omitempty"`
	ErrorMessage string          `json:"error_message,omitempty"`
}

// BulkInsertResult holds the result of a bulk database insert
type BulkInsertResult struct {
	InsertedCount int `json:"inserted_count"`
	UpdatedCount  int `json:"updated_count"`
	SkippedCount  int `json:"skipped_count"`
	ErrorCount    int `json:"error_count"`
}

// StreamResult holds the result of streaming operations
type StreamResult struct {
	StreamedCount int   `json:"streamed_count"`
	FailedCount   int   `json:"failed_count"`
	Error         error `json:"error,omitempty"`
}


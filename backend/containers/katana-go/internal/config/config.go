package config

import (
	"encoding/json"
	"fmt"
	"os"
	"strconv"
	"strings"
)

// ExecutionMode defines how the module runs
type ExecutionMode string

const (
	ModeSimple    ExecutionMode = "simple"
	ModeBatch     ExecutionMode = "batch"
	ModeStreaming ExecutionMode = "streaming"
)

// Config holds all configuration for the Katana module
type Config struct {
	// Execution Mode
	Mode ExecutionMode

	// Common Configuration
	ScanJobID    string
	AssetID      string
	UserID       string
	SupabaseURL  string
	SupabaseKey  string

	// Simple Mode
	TargetURLs []string

	// Batch Mode
	BatchID     string
	BatchOffset int
	BatchLimit  int

	// Streaming Mode
	RedisHost         string
	RedisPort         string
	RedisPassword     string
	StreamInputKey    string
	StreamOutputKey   string
	ConsumerGroup     string
	ConsumerName      string

	// Katana Configuration
	CrawlDepth      int
	HeadlessMode    bool
	RateLimit       int
	Concurrency     int
	Parallelism     int
	Timeout         int
	Strategy        string

	// Logger
	Logger *Logger
}

// LoadConfig loads configuration from environment variables
func LoadConfig() (*Config, error) {
	// Determine execution mode
	// Priority: STREAMING_MODE > BATCH_MODE > simple (default)
	// STREAMING_MODE takes precedence since it's more explicit
	mode := ModeSimple
	if os.Getenv("STREAMING_MODE") == "true" {
		mode = ModeStreaming
	} else if os.Getenv("BATCH_MODE") == "true" {
		mode = ModeBatch
	}

	// Common required variables
	scanJobID := os.Getenv("SCAN_JOB_ID")
	assetID := os.Getenv("ASSET_ID")
	userID := os.Getenv("USER_ID")
	supabaseURL := os.Getenv("SUPABASE_URL")
	supabaseKey := os.Getenv("SUPABASE_SERVICE_ROLE_KEY")

	if scanJobID == "" || assetID == "" || supabaseURL == "" || supabaseKey == "" {
		return nil, fmt.Errorf("missing required environment variables: SCAN_JOB_ID, ASSET_ID, SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY")
	}

	config := &Config{
		Mode:        mode,
		ScanJobID:   scanJobID,
		AssetID:     assetID,
		UserID:      userID,
		SupabaseURL: supabaseURL,
		SupabaseKey: supabaseKey,

		// Katana defaults (can be overridden)
		// HeadlessMode enables Chrome-based crawling for JavaScript rendering
		// Uses --no-sandbox for Fargate/Docker compatibility
		// DISABLED: go-rod panic in WaitDOMStable with zero interval (2025-12-22)
		// TODO: Re-enable once Katana SDK/go-rod issue is resolved
		CrawlDepth:   getEnvInt("CRAWL_DEPTH", 1),
		HeadlessMode: getEnvBool("HEADLESS_MODE", false),
		RateLimit:    getEnvInt("RATE_LIMIT", 150),
		Concurrency:  getEnvInt("CONCURRENCY", 10),
		Parallelism:  getEnvInt("PARALLELISM", 10),
		Timeout:      getEnvInt("TIMEOUT", 10),
		Strategy:     getEnvString("STRATEGY", "depth-first"),
	}

	// Load mode-specific configuration
	switch mode {
	case ModeSimple:
		if err := config.loadSimpleMode(); err != nil {
			return nil, err
		}
	case ModeBatch:
		if err := config.loadBatchMode(); err != nil {
			return nil, err
		}
	case ModeStreaming:
		if err := config.loadStreamingMode(); err != nil {
			return nil, err
		}
	}

	// Initialize logger with context
	logContext := map[string]string{
		"mode":        string(mode),
		"scan_job_id": scanJobID,
		"asset_id":    assetID,
	}
	config.Logger = NewLogger(logContext)

	return config, nil
}

// loadSimpleMode loads simple mode configuration
func (c *Config) loadSimpleMode() error {
	targetURLsStr := os.Getenv("TARGET_URLS")
	if targetURLsStr == "" {
		return fmt.Errorf("TARGET_URLS required for simple mode")
	}

	// Parse comma-separated URLs or JSON array
	if strings.HasPrefix(targetURLsStr, "[") {
		// JSON array format
		if err := json.Unmarshal([]byte(targetURLsStr), &c.TargetURLs); err != nil {
			return fmt.Errorf("failed to parse TARGET_URLS JSON: %w", err)
		}
	} else {
		// Comma-separated format
		c.TargetURLs = strings.Split(targetURLsStr, ",")
		// Trim whitespace
		for i := range c.TargetURLs {
			c.TargetURLs[i] = strings.TrimSpace(c.TargetURLs[i])
		}
	}

	if len(c.TargetURLs) == 0 {
		return fmt.Errorf("no target URLs provided")
	}

	return nil
}

// loadBatchMode loads batch mode configuration
func (c *Config) loadBatchMode() error {
	c.BatchID = os.Getenv("BATCH_ID")
	if c.BatchID == "" {
		return fmt.Errorf("BATCH_ID required for batch mode")
	}

	var err error
	c.BatchOffset, err = strconv.Atoi(os.Getenv("BATCH_OFFSET"))
	if err != nil {
		return fmt.Errorf("invalid BATCH_OFFSET: %w", err)
	}

	c.BatchLimit, err = strconv.Atoi(os.Getenv("BATCH_LIMIT"))
	if err != nil {
		return fmt.Errorf("invalid BATCH_LIMIT: %w", err)
	}

	if c.BatchLimit <= 0 {
		return fmt.Errorf("BATCH_LIMIT must be > 0")
	}

	return nil
}

// loadStreamingMode loads streaming mode configuration
func (c *Config) loadStreamingMode() error {
	c.RedisHost = os.Getenv("REDIS_HOST")
	c.RedisPort = os.Getenv("REDIS_PORT")
	c.RedisPassword = os.Getenv("REDIS_PASSWORD")
	c.StreamInputKey = os.Getenv("STREAM_INPUT_KEY")
	c.StreamOutputKey = os.Getenv("STREAM_OUTPUT_KEY")
	c.ConsumerGroup = os.Getenv("CONSUMER_GROUP")
	c.ConsumerName = os.Getenv("CONSUMER_NAME")

	if c.RedisHost == "" || c.RedisPort == "" {
		return fmt.Errorf("REDIS_HOST and REDIS_PORT required for streaming mode")
	}

	if c.StreamInputKey == "" || c.ConsumerGroup == "" || c.ConsumerName == "" {
		return fmt.Errorf("STREAM_INPUT_KEY, CONSUMER_GROUP, CONSUMER_NAME required for streaming mode")
	}

	// StreamOutputKey is optional (producer capability)

	return nil
}

// Validate validates the configuration
func (c *Config) Validate() error {
	// Validate crawl depth
	if c.CrawlDepth < 0 || c.CrawlDepth > 5 {
		return fmt.Errorf("CRAWL_DEPTH must be between 0 and 5")
	}

	// Validate concurrency
	if c.Concurrency < 1 || c.Concurrency > 50 {
		return fmt.Errorf("CONCURRENCY must be between 1 and 50")
	}

	// Validate strategy
	if c.Strategy != "depth-first" && c.Strategy != "breadth-first" {
		return fmt.Errorf("STRATEGY must be 'depth-first' or 'breadth-first'")
	}

	return nil
}

// Helper functions for environment variable parsing

func getEnvInt(key string, defaultValue int) int {
	val := os.Getenv(key)
	if val == "" {
		return defaultValue
	}
	intVal, err := strconv.Atoi(val)
	if err != nil {
		return defaultValue
	}
	return intVal
}

func getEnvBool(key string, defaultValue bool) bool {
	val := os.Getenv(key)
	if val == "" {
		return defaultValue
	}
	return val == "true" || val == "1" || val == "yes"
}

func getEnvString(key, defaultValue string) string {
	val := os.Getenv(key)
	if val == "" {
		return defaultValue
	}
	return val
}

// PrintConfig logs the configuration (without sensitive data)
func (c *Config) PrintConfig() {
	c.Logger.Info("=== Katana Scanner Configuration ===")
	c.Logger.Info("Execution Mode: %s", c.Mode)
	c.Logger.Info("Scan Job ID: %s", c.ScanJobID)
	c.Logger.Info("Asset ID: %s", c.AssetID)
	c.Logger.Info("Crawl Depth: %d", c.CrawlDepth)
	c.Logger.Info("Headless Mode: %v", c.HeadlessMode)
	c.Logger.Info("Concurrency: %d", c.Concurrency)
	c.Logger.Info("Rate Limit: %d req/s", c.RateLimit)
	c.Logger.Info("Strategy: %s", c.Strategy)

	switch c.Mode {
	case ModeSimple:
		c.Logger.Info("Target URLs: %d URLs", len(c.TargetURLs))
		if len(c.TargetURLs) <= 5 {
			for i, url := range c.TargetURLs {
				c.Logger.Debug("  [%d] %s", i+1, url)
			}
		}
	case ModeBatch:
		c.Logger.Info("Batch ID: %s", c.BatchID)
		c.Logger.Info("Batch Range: offset=%d, limit=%d", c.BatchOffset, c.BatchLimit)
	case ModeStreaming:
		c.Logger.Info("Redis: %s:%s", c.RedisHost, c.RedisPort)
		c.Logger.Info("Input Stream: %s", c.StreamInputKey)
		c.Logger.Info("Consumer Group: %s", c.ConsumerGroup)
		c.Logger.Info("Consumer Name: %s", c.ConsumerName)
	}

	c.Logger.Info("====================================")
}


package config

import (
	"encoding/json"
	"fmt"
	"net/url"
	"os"
	"strconv"
	"strings"
	"time"

	"github.com/sirupsen/logrus"
)

// ExecutionMode represents the module execution mode
type ExecutionMode string

const (
	ModeSimple    ExecutionMode = "simple"
	ModeBatch     ExecutionMode = "batch"
	ModeStreaming ExecutionMode = "streaming"
)

// Config holds all configuration for the TYVT module
type Config struct {
	// Core identifiers
	ScanJobID string
	UserID    string
	AssetID   string

	// Execution mode
	Mode ExecutionMode

	// Simple mode: direct subdomain input
	TargetSubdomains []string

	// Batch mode: database pagination
	BatchID     string
	BatchOffset int
	BatchLimit  int

	// Streaming mode: Redis consumer config
	StreamInputKey  string // e.g., scan:{job_id}:httpx:output
	StreamOutputKey string // e.g., scan:{job_id}:tyvt:output
	ConsumerGroup   string
	ConsumerName    string

	// Redis connection
	RedisHost     string
	RedisPort     string
	RedisPassword string

	// Supabase connection
	SupabaseURL string
	SupabaseKey string

	// VirusTotal configuration
	VTAPIKeys        []string      // Multiple API keys for rotation
	RotationInterval time.Duration // Key rotation interval
	RateLimitDelay   time.Duration // Delay between requests

	// Optional proxy support
	ProxyURL    *url.URL
	InsecureTLS bool

	// Timeouts
	ScanTimeout   time.Duration
	RequestTimeout time.Duration

	// Logger
	Logger *logrus.Logger
}

// LoadConfig loads configuration from environment variables
func LoadConfig() (*Config, error) {
	logger := logrus.New()
	logger.SetFormatter(&logrus.TextFormatter{
		FullTimestamp: true,
		ForceColors:   true,
	})
	logger.SetLevel(logrus.InfoLevel)

	cfg := &Config{
		Logger: logger,
	}

	// Determine execution mode
	batchMode := os.Getenv("BATCH_MODE") == "true"
	streamingMode := os.Getenv("STREAMING_MODE") == "true"

	if streamingMode {
		cfg.Mode = ModeStreaming
	} else if batchMode {
		cfg.Mode = ModeBatch
	} else {
		cfg.Mode = ModeSimple
	}

	// Core identifiers
	cfg.ScanJobID = os.Getenv("SCAN_JOB_ID")
	cfg.UserID = os.Getenv("USER_ID")
	cfg.AssetID = os.Getenv("ASSET_ID")

	// Supabase
	cfg.SupabaseURL = os.Getenv("SUPABASE_URL")
	cfg.SupabaseKey = os.Getenv("SUPABASE_SERVICE_ROLE_KEY")

	// Redis
	cfg.RedisHost = getEnvDefault("REDIS_HOST", "localhost")
	cfg.RedisPort = getEnvDefault("REDIS_PORT", "6379")
	cfg.RedisPassword = os.Getenv("REDIS_PASSWORD")

	// VirusTotal API keys (comma-separated or newline-separated)
	vtKeysRaw := os.Getenv("VT_API_KEYS")
	if vtKeysRaw == "" {
		// Try single key fallback
		singleKey := os.Getenv("VT_API_KEY")
		if singleKey != "" {
			cfg.VTAPIKeys = []string{singleKey}
		}
	} else {
		// Split by comma or newline
		keys := strings.FieldsFunc(vtKeysRaw, func(r rune) bool {
			return r == ',' || r == '\n'
		})
		for _, k := range keys {
			k = strings.TrimSpace(k)
			if k != "" && !strings.HasPrefix(k, "#") {
				cfg.VTAPIKeys = append(cfg.VTAPIKeys, k)
			}
		}
	}

	// Timing configurations
	cfg.RotationInterval = parseDuration(os.Getenv("VT_ROTATION_INTERVAL"), 15*time.Second)
	cfg.RateLimitDelay = parseDuration(os.Getenv("VT_RATE_LIMIT_DELAY"), 15*time.Second)
	cfg.ScanTimeout = parseDuration(os.Getenv("SCAN_TIMEOUT"), 60*time.Minute)
	cfg.RequestTimeout = parseDuration(os.Getenv("REQUEST_TIMEOUT"), 30*time.Second)

	// Optional proxy
	if proxyURLStr := os.Getenv("PROXY_URL"); proxyURLStr != "" {
		proxyURL, err := url.Parse(proxyURLStr)
		if err != nil {
			return nil, fmt.Errorf("invalid PROXY_URL: %w", err)
		}
		cfg.ProxyURL = proxyURL
	}
	cfg.InsecureTLS = os.Getenv("INSECURE_TLS") == "true"

	// Mode-specific configuration
	switch cfg.Mode {
	case ModeSimple:
		// Parse subdomains from JSON array
		subdomainsJSON := os.Getenv("SUBDOMAINS")
		if subdomainsJSON == "" {
			subdomainsJSON = os.Getenv("DOMAINS") // Fallback
		}
		if subdomainsJSON != "" {
			if err := json.Unmarshal([]byte(subdomainsJSON), &cfg.TargetSubdomains); err != nil {
				return nil, fmt.Errorf("failed to parse SUBDOMAINS JSON: %w", err)
			}
		}

	case ModeBatch:
		cfg.BatchID = os.Getenv("BATCH_ID")
		cfg.BatchOffset = getEnvInt("BATCH_OFFSET", 0)
		cfg.BatchLimit = getEnvInt("BATCH_LIMIT", 100)

	case ModeStreaming:
		cfg.StreamInputKey = os.Getenv("STREAM_INPUT_KEY")
		cfg.StreamOutputKey = os.Getenv("STREAM_OUTPUT_KEY")
		cfg.ConsumerGroup = getEnvDefault("CONSUMER_GROUP_NAME", "tyvt-consumers")
		cfg.ConsumerName = getEnvDefault("CONSUMER_NAME", fmt.Sprintf("tyvt-task-%s", cfg.ScanJobID[:8]))
	}

	return cfg, nil
}

// Validate checks that all required configuration is present
func (c *Config) Validate() error {
	// Always required
	required := map[string]string{
		"SCAN_JOB_ID":              c.ScanJobID,
		"USER_ID":                  c.UserID,
		"SUPABASE_URL":             c.SupabaseURL,
		"SUPABASE_SERVICE_ROLE_KEY": c.SupabaseKey,
	}

	// VirusTotal keys required
	if len(c.VTAPIKeys) == 0 {
		return fmt.Errorf("at least one VT_API_KEY or VT_API_KEYS is required")
	}

	// Mode-specific requirements
	switch c.Mode {
	case ModeSimple:
		if len(c.TargetSubdomains) == 0 {
			return fmt.Errorf("SUBDOMAINS or DOMAINS is required in simple mode")
		}

	case ModeBatch:
		required["ASSET_ID"] = c.AssetID
		required["BATCH_ID"] = c.BatchID

	case ModeStreaming:
		required["ASSET_ID"] = c.AssetID
		required["STREAM_INPUT_KEY"] = c.StreamInputKey
		required["REDIS_HOST"] = c.RedisHost
	}

	// Check required fields
	var missing []string
	for name, value := range required {
		if value == "" {
			missing = append(missing, name)
		}
	}

	if len(missing) > 0 {
		return fmt.Errorf("missing required environment variables: %v", missing)
	}

	return nil
}

// PrintConfig logs the current configuration (without secrets)
func (c *Config) PrintConfig() {
	c.Logger.Info("=== TYVT Configuration ===")
	c.Logger.Infof("  Mode: %s", c.Mode)
	c.Logger.Infof("  Scan Job ID: %s", c.ScanJobID)
	c.Logger.Infof("  Asset ID: %s", c.AssetID)
	c.Logger.Infof("  VT API Keys: %d configured", len(c.VTAPIKeys))
	c.Logger.Infof("  Key Rotation Interval: %s", c.RotationInterval)
	c.Logger.Infof("  Rate Limit Delay: %s", c.RateLimitDelay)

	if c.Mode == ModeStreaming {
		c.Logger.Infof("  Stream Input: %s", c.StreamInputKey)
		c.Logger.Infof("  Stream Output: %s", c.StreamOutputKey)
		c.Logger.Infof("  Consumer Group: %s", c.ConsumerGroup)
	}

	if c.ProxyURL != nil {
		c.Logger.Infof("  Proxy: %s://%s", c.ProxyURL.Scheme, c.ProxyURL.Host)
	}
}

// Helper functions
func getEnvDefault(key, defaultValue string) string {
	if value := os.Getenv(key); value != "" {
		return value
	}
	return defaultValue
}

func getEnvInt(key string, defaultValue int) int {
	if value := os.Getenv(key); value != "" {
		if intValue, err := strconv.Atoi(value); err == nil {
			return intValue
		}
	}
	return defaultValue
}

func parseDuration(value string, defaultValue time.Duration) time.Duration {
	if value == "" {
		return defaultValue
	}
	d, err := time.ParseDuration(value)
	if err != nil {
		return defaultValue
	}
	return d
}


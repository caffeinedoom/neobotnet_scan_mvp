package config

import (
	"os"
	"testing"
)

// setupEnv sets up test environment variables
func setupEnv(t *testing.T, envVars map[string]string) func() {
	// Store original values
	original := make(map[string]string)
	for key := range envVars {
		original[key] = os.Getenv(key)
	}

	// Set test values
	for key, value := range envVars {
		os.Setenv(key, value)
	}

	// Return cleanup function
	return func() {
		for key, value := range original {
			if value == "" {
				os.Unsetenv(key)
			} else {
				os.Setenv(key, value)
			}
		}
	}
}

// TestLoadConfig_SimpleMode tests loading configuration for simple mode
func TestLoadConfig_SimpleMode(t *testing.T) {
	cleanup := setupEnv(t, map[string]string{
		"SCAN_JOB_ID":              "test-job-123",
		"ASSET_ID":                 "test-asset-456",
		"USER_ID":                  "test-user-789",
		"SUPABASE_URL":             "https://test.supabase.co",
		"SUPABASE_SERVICE_ROLE_KEY": "test-key",
		"TARGET_URLS":              "https://example.com,https://test.com",
		"BATCH_MODE":               "",
		"STREAMING_MODE":           "",
	})
	defer cleanup()

	cfg, err := LoadConfig()
	if err != nil {
		t.Fatalf("LoadConfig() error = %v", err)
	}

	// Verify mode
	if cfg.Mode != ModeSimple {
		t.Errorf("Mode = %v, want %v", cfg.Mode, ModeSimple)
	}

	// Verify required fields
	if cfg.ScanJobID != "test-job-123" {
		t.Errorf("ScanJobID = %v, want test-job-123", cfg.ScanJobID)
	}
	if cfg.AssetID != "test-asset-456" {
		t.Errorf("AssetID = %v, want test-asset-456", cfg.AssetID)
	}
	if cfg.SupabaseURL != "https://test.supabase.co" {
		t.Errorf("SupabaseURL = %v, want https://test.supabase.co", cfg.SupabaseURL)
	}

	// Verify target URLs
	if len(cfg.TargetURLs) != 2 {
		t.Errorf("len(TargetURLs) = %d, want 2", len(cfg.TargetURLs))
	}
	if cfg.TargetURLs[0] != "https://example.com" {
		t.Errorf("TargetURLs[0] = %v, want https://example.com", cfg.TargetURLs[0])
	}

	// Verify defaults
	if cfg.CrawlDepth != 1 {
		t.Errorf("CrawlDepth = %d, want 1", cfg.CrawlDepth)
	}
	if cfg.HeadlessMode != true {
		t.Errorf("HeadlessMode = %v, want true", cfg.HeadlessMode)
	}
}

// TestLoadConfig_BatchMode tests loading configuration for batch mode
func TestLoadConfig_BatchMode(t *testing.T) {
	cleanup := setupEnv(t, map[string]string{
		"SCAN_JOB_ID":               "test-job-123",
		"ASSET_ID":                  "test-asset-456",
		"USER_ID":                   "test-user-789",
		"SUPABASE_URL":              "https://test.supabase.co",
		"SUPABASE_SERVICE_ROLE_KEY": "test-key",
		"BATCH_MODE":                "true",
		"BATCH_ID":                  "batch-001",
		"BATCH_OFFSET":              "0",
		"BATCH_LIMIT":               "20",
	})
	defer cleanup()

	cfg, err := LoadConfig()
	if err != nil {
		t.Fatalf("LoadConfig() error = %v", err)
	}

	// Verify mode
	if cfg.Mode != ModeBatch {
		t.Errorf("Mode = %v, want %v", cfg.Mode, ModeBatch)
	}

	// Verify batch fields
	if cfg.BatchID != "batch-001" {
		t.Errorf("BatchID = %v, want batch-001", cfg.BatchID)
	}
	if cfg.BatchOffset != 0 {
		t.Errorf("BatchOffset = %d, want 0", cfg.BatchOffset)
	}
	if cfg.BatchLimit != 20 {
		t.Errorf("BatchLimit = %d, want 20", cfg.BatchLimit)
	}
}

// TestLoadConfig_StreamingMode tests loading configuration for streaming mode
func TestLoadConfig_StreamingMode(t *testing.T) {
	cleanup := setupEnv(t, map[string]string{
		"SCAN_JOB_ID":               "test-job-123",
		"ASSET_ID":                  "test-asset-456",
		"USER_ID":                   "test-user-789",
		"SUPABASE_URL":              "https://test.supabase.co",
		"SUPABASE_SERVICE_ROLE_KEY": "test-key",
		"STREAMING_MODE":            "true",
		"REDIS_HOST":                "localhost",
		"REDIS_PORT":                "6379",
		"STREAM_INPUT_KEY":          "scan:httpx:results",
		"CONSUMER_GROUP":            "katana-workers",
		"CONSUMER_NAME":             "worker-1",
	})
	defer cleanup()

	cfg, err := LoadConfig()
	if err != nil {
		t.Fatalf("LoadConfig() error = %v", err)
	}

	// Verify mode
	if cfg.Mode != ModeStreaming {
		t.Errorf("Mode = %v, want %v", cfg.Mode, ModeStreaming)
	}

	// Verify streaming fields
	if cfg.RedisHost != "localhost" {
		t.Errorf("RedisHost = %v, want localhost", cfg.RedisHost)
	}
	if cfg.RedisPort != "6379" {
		t.Errorf("RedisPort = %v, want 6379", cfg.RedisPort)
	}
	if cfg.StreamInputKey != "scan:httpx:results" {
		t.Errorf("StreamInputKey = %v, want scan:httpx:results", cfg.StreamInputKey)
	}
}

// TestLoadConfig_MissingRequiredFields tests validation of missing required fields
func TestLoadConfig_MissingRequiredFields(t *testing.T) {
	tests := []struct {
		name    string
		envVars map[string]string
		wantErr bool
	}{
		{
			name: "Missing SCAN_JOB_ID",
			envVars: map[string]string{
				"ASSET_ID":                  "test-asset",
				"SUPABASE_URL":              "https://test.supabase.co",
				"SUPABASE_SERVICE_ROLE_KEY": "test-key",
			},
			wantErr: true,
		},
		{
			name: "Missing ASSET_ID",
			envVars: map[string]string{
				"SCAN_JOB_ID":               "test-job",
				"SUPABASE_URL":              "https://test.supabase.co",
				"SUPABASE_SERVICE_ROLE_KEY": "test-key",
			},
			wantErr: true,
		},
		{
			name: "Missing SUPABASE_URL",
			envVars: map[string]string{
				"SCAN_JOB_ID":               "test-job",
				"ASSET_ID":                  "test-asset",
				"SUPABASE_SERVICE_ROLE_KEY": "test-key",
			},
			wantErr: true,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			cleanup := setupEnv(t, tt.envVars)
			defer cleanup()

			_, err := LoadConfig()
			if (err != nil) != tt.wantErr {
				t.Errorf("LoadConfig() error = %v, wantErr %v", err, tt.wantErr)
			}
		})
	}
}

// TestValidate tests configuration validation
func TestValidate(t *testing.T) {
	tests := []struct {
		name    string
		cfg     *Config
		wantErr bool
	}{
		{
			name: "Valid config",
			cfg: &Config{
				CrawlDepth:  1,
				Concurrency: 10,
				Strategy:    "depth-first",
			},
			wantErr: false,
		},
		{
			name: "Invalid crawl depth (negative)",
			cfg: &Config{
				CrawlDepth:  -1,
				Concurrency: 10,
				Strategy:    "depth-first",
			},
			wantErr: true,
		},
		{
			name: "Invalid crawl depth (too high)",
			cfg: &Config{
				CrawlDepth:  10,
				Concurrency: 10,
				Strategy:    "depth-first",
			},
			wantErr: true,
		},
		{
			name: "Invalid concurrency (too low)",
			cfg: &Config{
				CrawlDepth:  1,
				Concurrency: 0,
				Strategy:    "depth-first",
			},
			wantErr: true,
		},
		{
			name: "Invalid concurrency (too high)",
			cfg: &Config{
				CrawlDepth:  1,
				Concurrency: 100,
				Strategy:    "depth-first",
			},
			wantErr: true,
		},
		{
			name: "Invalid strategy",
			cfg: &Config{
				CrawlDepth:  1,
				Concurrency: 10,
				Strategy:    "invalid-strategy",
			},
			wantErr: true,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			err := tt.cfg.Validate()
			if (err != nil) != tt.wantErr {
				t.Errorf("Validate() error = %v, wantErr %v", err, tt.wantErr)
			}
		})
	}
}

// TestGetEnvInt tests integer environment variable parsing
func TestGetEnvInt(t *testing.T) {
	tests := []struct {
		name         string
		key          string
		value        string
		defaultValue int
		expected     int
	}{
		{
			name:         "Valid integer",
			key:          "TEST_INT",
			value:        "42",
			defaultValue: 10,
			expected:     42,
		},
		{
			name:         "Empty value (use default)",
			key:          "TEST_INT",
			value:        "",
			defaultValue: 10,
			expected:     10,
		},
		{
			name:         "Invalid integer (use default)",
			key:          "TEST_INT",
			value:        "not-a-number",
			defaultValue: 10,
			expected:     10,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			if tt.value != "" {
				os.Setenv(tt.key, tt.value)
				defer os.Unsetenv(tt.key)
			}

			result := getEnvInt(tt.key, tt.defaultValue)
			if result != tt.expected {
				t.Errorf("getEnvInt() = %d, want %d", result, tt.expected)
			}
		})
	}
}

// TestGetEnvBool tests boolean environment variable parsing
func TestGetEnvBool(t *testing.T) {
	tests := []struct {
		name         string
		key          string
		value        string
		defaultValue bool
		expected     bool
	}{
		{
			name:         "True (lowercase)",
			key:          "TEST_BOOL",
			value:        "true",
			defaultValue: false,
			expected:     true,
		},
		{
			name:         "True (1)",
			key:          "TEST_BOOL",
			value:        "1",
			defaultValue: false,
			expected:     true,
		},
		{
			name:         "True (yes)",
			key:          "TEST_BOOL",
			value:        "yes",
			defaultValue: false,
			expected:     true,
		},
		{
			name:         "False (empty)",
			key:          "TEST_BOOL",
			value:        "",
			defaultValue: false,
			expected:     false,
		},
		{
			name:         "False (other value)",
			key:          "TEST_BOOL",
			value:        "no",
			defaultValue: false,
			expected:     false,
		},
		{
			name:         "Use default (empty)",
			key:          "TEST_BOOL",
			value:        "",
			defaultValue: true,
			expected:     true,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			if tt.value != "" {
				os.Setenv(tt.key, tt.value)
				defer os.Unsetenv(tt.key)
			} else {
				os.Unsetenv(tt.key)
			}

			result := getEnvBool(tt.key, tt.defaultValue)
			if result != tt.expected {
				t.Errorf("getEnvBool() = %v, want %v", result, tt.expected)
			}
		})
	}
}


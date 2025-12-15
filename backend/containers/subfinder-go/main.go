package main

import (
	"context"
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"os"
	"os/signal"
	"runtime"
	"strconv"
	"strings"
	"syscall"
	"time"

	"github.com/go-redis/redis/v8"
	"github.com/sirupsen/logrus"
)

// Configuration from environment variables and command line
type Config struct {
	Domains          []string          // Multiple domains to scan
	JobID            string            // Asset-level job ID (for backward compatibility)
	DomainJobMapping map[string]string // domain → scan_job_id mapping
	RedisHost        string
	RedisPort        string
	Timeout          int // Overall scan timeout in minutes
	Workers          int // Number of concurrent workers

	// Streaming mode configuration (Phase 2)
	StreamingMode   bool   // Enable Redis Streams output
	StreamOutputKey string // Redis Stream key for output (e.g., "scan:{job_id}:subfinder:output")
}

// Scanner represents the main subfinder scanner
type Scanner struct {
	config         *Config
	redisClient    *redis.Client
	supabaseClient *SupabaseClient
	logger         *logrus.Logger
	ctx            context.Context
	cancel         context.CancelFunc
	healthChecker  *HealthChecker
}

// PerformanceMetrics tracks detailed scan performance
type PerformanceMetrics struct {
	ScanStartTime   time.Time                 `json:"scan_start_time"`
	DomainMetrics   map[string]*DomainMetrics `json:"domain_metrics"`
	OverallMetrics  *OverallMetrics           `json:"overall_metrics"`
	ErrorMetrics    *ErrorMetrics             `json:"error_metrics"`
	ResourceMetrics *ResourceMetrics          `json:"resource_metrics"`
}

// DomainMetrics tracks per-domain performance
type DomainMetrics struct {
	Domain            string        `json:"domain"`
	StartTime         time.Time     `json:"start_time"`
	EndTime           *time.Time    `json:"end_time,omitempty"`
	Duration          time.Duration `json:"duration"`
	SubdomainsFound   int           `json:"subdomains_found"`
	SourcesUsed       []string      `json:"sources_used"`
	RetryCount        int           `json:"retry_count"`
	ErrorCount        int           `json:"error_count"`
	BytesTransferred  int64         `json:"bytes_transferred"`
	APICallsPerformed int           `json:"api_calls_performed"`
}

// OverallMetrics tracks scan-wide performance
type OverallMetrics struct {
	TotalDomains               int           `json:"total_domains"`
	CompletedDomains           int           `json:"completed_domains"`
	FailedDomains              int           `json:"failed_domains"`
	TotalSubdomains            int           `json:"total_subdomains"`
	AverageTimePerDomain       time.Duration `json:"average_time_per_domain"`
	ThroughputDomainsPerMin    float64       `json:"throughput_domains_per_min"`
	ThroughputSubdomainsPerMin float64       `json:"throughput_subdomains_per_min"`
	MemoryUsageMB              int64         `json:"memory_usage_mb"`
	CPUUsagePercent            float64       `json:"cpu_usage_percent"`
}

// ErrorMetrics tracks different types of errors
type ErrorMetrics struct {
	NetworkErrors        int `json:"network_errors"`
	TimeoutErrors        int `json:"timeout_errors"`
	AuthenticationErrors int `json:"authentication_errors"`
	RateLimitErrors      int `json:"rate_limit_errors"`
	ValidationErrors     int `json:"validation_errors"`
	DatabaseErrors       int `json:"database_errors"`
	UnknownErrors        int `json:"unknown_errors"`
}

// ResourceMetrics tracks resource utilization
type ResourceMetrics struct {
	PeakMemoryMB      int64   `json:"peak_memory_mb"`
	AverageMemoryMB   int64   `json:"average_memory_mb"`
	PeakCPUPercent    float64 `json:"peak_cpu_percent"`
	AverageCPUPercent float64 `json:"average_cpu_percent"`
	NetworkBytesIn    int64   `json:"network_bytes_in"`
	NetworkBytesOut   int64   `json:"network_bytes_out"`
	DiskIOReads       int64   `json:"disk_io_reads"`
	DiskIOWrites      int64   `json:"disk_io_writes"`
}

// HealthChecker performs comprehensive health monitoring
type HealthChecker struct {
	scanner         *Scanner
	lastHealthCheck time.Time
	healthStatus    map[string]interface{}
}

// ScanResult represents a discovered subdomain
// NOTE: This is an internal processing struct. IPAddresses field is kept for
// compatibility with subfinder library but is NOT persisted to database.
// After migration (2025-10-06), only subdomain, source, discovered_at, parent_domain
// are stored in the subdomains table. IP resolution will be handled by future DNS module.
type ScanResult struct {
	Subdomain    string            `json:"subdomain"`
	IPAddresses  []string          `json:"ip_addresses,omitempty"` // Not persisted (subfinder doesn't resolve IPs)
	Source       string            `json:"source"`
	DiscoveredAt string            `json:"discovered_at"`
	ParentDomain string            `json:"parent_domain"`
	Metadata     map[string]string `json:"metadata,omitempty"`
}

// HealthStatus represents the health status of the scanner
type HealthStatus struct {
	Status         string                 `json:"status"`
	Timestamp      string                 `json:"timestamp"`
	Version        string                 `json:"version"`
	Uptime         string                 `json:"uptime"`
	MemoryMB       uint64                 `json:"memory_mb"`
	Goroutines     int                    `json:"goroutines"`
	RedisConnected bool                   `json:"redis_connected"`
	SystemInfo     map[string]interface{} `json:"system_info"`
}

// startHealthServer starts a simple HTTP health endpoint for monitoring
func startHealthServer(scanner *Scanner) {
	// Only start health server if enabled
	if os.Getenv("HEALTH_CHECK_ENABLED") != "true" {
		return
	}

	port := getEnv("HEALTH_PORT", "8080")

	http.HandleFunc("/health", func(w http.ResponseWriter, r *http.Request) {
		health := getHealthStatus(scanner)
		w.Header().Set("Content-Type", "application/json")

		if health.Status == "healthy" {
			w.WriteHeader(http.StatusOK)
		} else {
			w.WriteHeader(http.StatusServiceUnavailable)
		}

		json.NewEncoder(w).Encode(health)
	})

	http.HandleFunc("/metrics", func(w http.ResponseWriter, r *http.Request) {
		metrics := getPerformanceMetrics(scanner)
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusOK)
		json.NewEncoder(w).Encode(metrics)
	})

	// Start server in background
	go func() {
		log.Printf("🏥 Health endpoint starting on port %s", port)
		if err := http.ListenAndServe(":"+port, nil); err != nil {
			log.Printf("❌ Health server failed: %v", err)
		}
	}()
}

// getHealthStatus returns the current health status
func getHealthStatus(scanner *Scanner) HealthStatus {
	var memStats runtime.MemStats
	runtime.ReadMemStats(&memStats)

	status := HealthStatus{
		Status:     "healthy",
		Timestamp:  time.Now().UTC().Format(time.RFC3339),
		Version:    "2.1.0",
		Uptime:     getUptime(),
		MemoryMB:   memStats.Alloc / 1024 / 1024,
		Goroutines: runtime.NumGoroutine(),
		SystemInfo: make(map[string]interface{}),
	}

	// Check Redis connectivity if scanner is available
	if scanner != nil && scanner.redisClient != nil {
		if err := scanner.redisClient.Ping(scanner.ctx).Err(); err != nil {
			status.RedisConnected = false
			status.Status = "degraded"
			status.SystemInfo["redis_error"] = err.Error()
		} else {
			status.RedisConnected = true
		}
	}

	// Check memory threshold
	if status.MemoryMB > 1024 { // More than 1GB
		status.Status = "warning"
		status.SystemInfo["memory_warning"] = "High memory usage detected"
	}

	// Add system information
	status.SystemInfo["hostname"] = getEnv("HOSTNAME", "unknown")
	status.SystemInfo["job_id"] = getEnv("JOB_ID", "unknown")
	status.SystemInfo["batch_mode"] = getEnv("BATCH_MODE", "false")

	return status
}

// getPerformanceMetrics returns current performance metrics
func getPerformanceMetrics(scanner *Scanner) map[string]interface{} {
	var memStats runtime.MemStats
	runtime.ReadMemStats(&memStats)

	metrics := map[string]interface{}{
		"timestamp": time.Now().UTC().Format(time.RFC3339),
		"memory": map[string]interface{}{
			"alloc_mb":       memStats.Alloc / 1024 / 1024,
			"total_alloc_mb": memStats.TotalAlloc / 1024 / 1024,
			"sys_mb":         memStats.Sys / 1024 / 1024,
			"heap_objects":   memStats.HeapObjects,
			"gc_cycles":      memStats.NumGC,
			"next_gc_mb":     memStats.NextGC / 1024 / 1024,
		},
		"runtime": map[string]interface{}{
			"goroutines": runtime.NumGoroutine(),
			"cpu_count":  runtime.NumCPU(),
			"go_version": runtime.Version(),
		},
		"process": map[string]interface{}{
			"uptime": getUptime(),
			"pid":    os.Getpid(),
		},
	}

	// Add scanner-specific metrics if available
	if scanner != nil {
		scannerMetrics := map[string]interface{}{
			"domains_configured": len(scanner.config.Domains),
			"workers_configured": scanner.config.Workers,
			"timeout_minutes":    scanner.config.Timeout,
		}

		if scanner.redisClient != nil {
			// Add Redis connection info
			scannerMetrics["redis_configured"] = true
		} else {
			scannerMetrics["redis_configured"] = false
		}

		metrics["scanner"] = scannerMetrics
	}

	return metrics
}

var startTime = time.Now()

// getUptime returns the uptime of the process
func getUptime() string {
	duration := time.Since(startTime)
	return duration.String()
}

// validateRequiredEnvVars validates that all required environment variables are set
func validateRequiredEnvVars(batchMode bool) error {
	// Required for all modes
	required := []string{
		"SCAN_JOB_ID",
		"USER_ID",
		"SUPABASE_URL",
		"SUPABASE_SERVICE_ROLE_KEY",
	}

	// Mode-specific requirements
	if batchMode {
		required = append(required, "BATCH_ID", "ASSET_ID", "BATCH_OFFSET", "BATCH_LIMIT")
	} else {
		required = append(required, "DOMAINS")
	}

	// Check for missing variables
	var missing []string
	for _, key := range required {
		if os.Getenv(key) == "" {
			missing = append(missing, key)
		}
	}

	if len(missing) > 0 {
		return fmt.Errorf("missing required environment variables: %v", missing)
	}

	return nil
}

func main() {
	// ============================================================
	// 1. DETERMINE EXECUTION MODE
	// ============================================================

	batchMode := os.Getenv("BATCH_MODE") == "true"

	log.Printf("🚀 Subfinder-Go Scanner starting up...")
	log.Printf("📋 Execution mode: %s", map[bool]string{true: "BATCH", false: "SIMPLE"}[batchMode])

	// ============================================================
	// 2. VALIDATE ENVIRONMENT VARIABLES
	// ============================================================

	if err := validateRequiredEnvVars(batchMode); err != nil {
		log.Fatalf("❌ Environment validation failed: %v", err)
	}

	log.Println("✅ Environment validation passed")

	// ============================================================
	// 3. ROUTE TO APPROPRIATE HANDLER
	// ============================================================

	if batchMode {
		log.Println("🔄 Starting BATCH mode execution...")
		runBatchMode()
		return
	}

	log.Println("🔄 Starting SIMPLE mode execution...")

	// ============================================================
	// 4. SIMPLE MODE: Parse inputs from environment variables
	// ============================================================

	// Parse SCAN_JOB_ID
	jobID := os.Getenv("SCAN_JOB_ID")

	// Parse domains from JSON array (not CSV)
	domainsJSON := os.Getenv("DOMAINS")
	var domains []string
	if err := json.Unmarshal([]byte(domainsJSON), &domains); err != nil {
		log.Fatalf("❌ Failed to parse DOMAINS JSON: %v (value: %s)", err, domainsJSON)
	}

	log.Printf("📊 Processing %d domains", len(domains))

	// Filter out empty domains
	var validDomains []string
	for _, domain := range domains {
		trimmed := strings.TrimSpace(domain)
		if trimmed != "" {
			validDomains = append(validDomains, trimmed)
		}
	}

	if len(validDomains) == 0 {
		log.Fatal("❌ No valid domains found in DOMAINS array")
	}

	log.Printf("✅ Parsed scan_job_id: %s, domains: %v (%d total)", jobID, validDomains, len(validDomains))

	config := &Config{
		Domains:   validDomains,
		JobID:     jobID,
		RedisHost: getEnv("REDIS_HOST", "localhost"),
		RedisPort: getEnv("REDIS_PORT", "6379"),
		Timeout:   getEnvInt("SCAN_TIMEOUT", 10), // 10 minutes default
		Workers:   getEnvInt("WORKERS", 10),      // 10 concurrent workers

		// Streaming mode configuration
		StreamingMode:   os.Getenv("STREAMING_MODE") == "true",
		StreamOutputKey: getEnv("STREAM_OUTPUT_KEY", ""),
	}

	// Parse optional ASSET_SCAN_MAPPING (domain → scan_job_id mapping)
	if mappingJSON := os.Getenv("ASSET_SCAN_MAPPING"); mappingJSON != "" {
		err := json.Unmarshal([]byte(mappingJSON), &config.DomainJobMapping)
		if err != nil {
			log.Printf("⚠️  WARN: Failed to parse ASSET_SCAN_MAPPING: %v. Using default scan_job_id.", err)
		} else {
			log.Printf("✅ Loaded domain→scan_job_id mapping for %d domains", len(config.DomainJobMapping))
		}
	}

	// Fallback: Also check legacy DOMAIN_JOB_MAPPING for backward compatibility
	if len(config.DomainJobMapping) == 0 {
		if legacyMappingJSON := os.Getenv("DOMAIN_JOB_MAPPING"); legacyMappingJSON != "" {
			err := json.Unmarshal([]byte(legacyMappingJSON), &config.DomainJobMapping)
			if err != nil {
				log.Printf("⚠️  WARN: Failed to parse DOMAIN_JOB_MAPPING: %v", err)
			} else {
				log.Printf("✅ Loaded domain→job_id mapping from legacy DOMAIN_JOB_MAPPING")
			}
		}
	}

	// Initialize scanner
	log.Printf("🔧 Initializing subfinder scanner with config: JobID=%s, Domains=%v, Workers=%d, Timeout=%dm",
		config.JobID, config.Domains, config.Workers, config.Timeout)

	// Log streaming mode configuration
	if config.StreamingMode {
		log.Printf("📤 Streaming mode ENABLED: Output key=%s", config.StreamOutputKey)

		// Validate streaming configuration
		if config.StreamOutputKey == "" {
			log.Fatal("❌ STREAMING_MODE=true requires STREAM_OUTPUT_KEY environment variable")
		}
		if config.RedisHost == "" || config.RedisPort == "" {
			log.Fatal("❌ STREAMING_MODE=true requires REDIS_HOST and REDIS_PORT environment variables")
		}

		log.Printf("✅ Streaming configuration validated")
	} else {
		log.Printf("💾 Standard mode: Results will be stored directly to database")
	}

	scanner, err := NewScanner(config)
	if err != nil {
		log.Fatalf("❌ Failed to initialize scanner: %v", err)
	}
	defer scanner.Close()

	// Start health monitoring server
	startHealthServer(scanner)

	// Setup graceful shutdown
	scanner.setupSignalHandling()

	// Start the scanning process
	log.Printf("🎯 Starting subfinder analysis for %d domains: %v", len(config.Domains), config.Domains)

	if err := scanner.Run(); err != nil {
		log.Fatalf("❌ Scan failed: %v", err)
	}

	log.Printf("✅ Subfinder scan completed successfully for job: %s", config.JobID)
}

// NewScanner creates a new scanner instance
func NewScanner(config *Config) (*Scanner, error) {
	// Setup logger
	logger := logrus.New()
	logger.SetFormatter(&logrus.JSONFormatter{})
	logger.SetLevel(logrus.InfoLevel)

	// Create context with timeout
	ctx, cancel := context.WithTimeout(context.Background(), time.Duration(config.Timeout)*time.Minute)

	// Initialize Redis client
	redisAddr := fmt.Sprintf("%s:%s", config.RedisHost, config.RedisPort)
	redisClient := redis.NewClient(&redis.Options{
		Addr:         redisAddr,
		Password:     "",
		DB:           0,
		DialTimeout:  10 * time.Second,
		ReadTimeout:  30 * time.Second,
		WriteTimeout: 30 * time.Second,
	})

	// Test Redis connection
	if err := redisClient.Ping(ctx).Err(); err != nil {
		cancel()
		return nil, fmt.Errorf("failed to connect to Redis: %v", err)
	}

	// Initialize Supabase client
	supabaseClient, err := NewSupabaseClient()
	if err != nil {
		cancel()
		return nil, fmt.Errorf("failed to initialize Supabase client: %v", err)
	}

	scanner := &Scanner{
		config:         config,
		redisClient:    redisClient,
		supabaseClient: supabaseClient,
		logger:         logger,
		ctx:            ctx,
		cancel:         cancel,
	}

	return scanner, nil
}

// setupSignalHandling sets up graceful shutdown on SIGTERM/SIGINT
func (s *Scanner) setupSignalHandling() {
	c := make(chan os.Signal, 1)
	signal.Notify(c, os.Interrupt, syscall.SIGTERM)

	go func() {
		<-c
		s.logger.Info("🛑 Received shutdown signal, initiating graceful shutdown...")
		s.cancel()
	}()
}

// Close cleans up resources
func (s *Scanner) Close() {
	if s.cancel != nil {
		s.cancel()
	}
	if s.redisClient != nil {
		s.redisClient.Close()
	}
}

// runBatchMode handles batch processing workflow
func runBatchMode() {
	// In batch mode, configuration comes from environment variables
	config := &Config{
		RedisHost: getEnv("REDIS_HOST", "localhost"),
		RedisPort: getEnv("REDIS_PORT", "6379"),
		Timeout:   60, // Default timeout
		Workers:   5,  // Default workers

		// PHASE 5 FIX: Read streaming configuration in batch mode
		StreamingMode:   os.Getenv("STREAMING_MODE") == "true",
		StreamOutputKey: getEnv("STREAM_OUTPUT_KEY", ""),
	}

	// Log streaming configuration
	if config.StreamingMode {
		log.Printf("📤 Streaming mode ENABLED in batch mode: Output key=%s", config.StreamOutputKey)
		if config.StreamOutputKey == "" {
			log.Fatal("❌ STREAMING_MODE=true requires STREAM_OUTPUT_KEY environment variable")
		}
	} else {
		log.Printf("💾 Standard batch mode: Results will be stored directly to database")
	}

	// Create scanner instance
	scanner, err := NewScanner(config)
	if err != nil {
		log.Fatalf("❌ Failed to create scanner: %v", err)
	}
	defer scanner.Close()

	// Load batch configuration
	batchConfig, err := scanner.loadBatchConfig()
	if err != nil {
		log.Fatalf("❌ Failed to load batch configuration: %v", err)
	}

	// Handle graceful shutdown
	scanner.setupSignalHandling()

	// Run batch scan
	log.Printf("🚀 Starting BATCH Subfinder scanner for %d domains...", len(batchConfig.BatchDomains))
	if err := scanner.runBatchScan(batchConfig); err != nil {
		log.Fatalf("❌ Batch scanner failed: %v", err)
	}

	log.Printf("✅ Batch Subfinder scanner completed successfully")
}

// Helper functions
func getEnv(key, defaultValue string) string {
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

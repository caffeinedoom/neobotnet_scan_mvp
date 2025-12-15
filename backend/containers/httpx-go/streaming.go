package main

import (
	"context"
	"fmt"
	"log"
	"os"
	"strings"
	"time"

	"github.com/go-redis/redis/v8"
)

// StreamingConfig holds configuration for streaming consumer mode
type StreamingConfig struct {
	StreamInputKey    string // Redis Stream to read from (e.g., "scan:{job_id}:subfinder:output")
	ConsumerGroupName string // Consumer group name (e.g., "httpx-consumers")
	ConsumerName      string // Unique consumer identifier (e.g., "httpx-{task_id}")
	BatchSize         int64  // Number of messages to read per XREADGROUP call
	BlockMilliseconds int64  // XREADGROUP blocking time in milliseconds
	RedisHost         string
	RedisPort         string
	ScanJobID         string
	MaxProcessingTime time.Duration // Maximum time to wait for completion marker
}

// SubdomainMessage represents a subdomain message from the stream
type SubdomainMessage struct {
	Subdomain    string                 `json:"subdomain"`
	Source       string                 `json:"source"`
	DiscoveredAt string                 `json:"discovered_at"`
	ParentDomain string                 `json:"parent_domain"`
	ScanJobID    string                 `json:"scan_job_id"`
	AssetID      string                 `json:"asset_id"` // ✅ FIX: Asset ID for database insertion
	Metadata     map[string]interface{} `json:"metadata"`
}

// CompletionMessage represents a completion marker from the stream
type CompletionMessage struct {
	Type         string `json:"type"`
	Module       string `json:"module"`
	ScanJobID    string `json:"scan_job_id"`
	Timestamp    string `json:"timestamp"`
	TotalResults int    `json:"total_results"`
}

// runStreamingMode runs HTTPx in streaming consumer mode
func runStreamingMode() error {
	log.Println("=" + strings.Repeat("=", 69))
	log.Println("🌊 HTTPx Streaming Consumer Mode")
	log.Println("=" + strings.Repeat("=", 69))

	// Load streaming configuration
	config, err := loadStreamingConfig()
	if err != nil {
		return fmt.Errorf("failed to load streaming config: %w", err)
	}

	// Print configuration
	printStreamingConfig(config)

	// Initialize Redis client
	redisClient, ctx, err := initializeRedisClient(config)
	if err != nil {
		return fmt.Errorf("failed to initialize Redis client: %w", err)
	}
	defer redisClient.Close()

	// Initialize consumer group (create if doesn't exist)
	if err := ensureConsumerGroup(redisClient, ctx, config); err != nil {
		return fmt.Errorf("failed to ensure consumer group: %w", err)
	}

	// Initialize Supabase client
	supabaseClient, err := NewSupabaseClient()
	if err != nil {
		return fmt.Errorf("failed to initialize Supabase client: %w", err)
	}

	// Start consuming from stream
	log.Println("\n🔍 Starting to consume subdomains from stream...")
	if err := consumeStream(redisClient, ctx, config, supabaseClient); err != nil {
		return fmt.Errorf("stream consumption failed: %w", err)
	}

	log.Println("\n✅ Stream consumption completed successfully")

	// ============================================================
	// FIX: Update batch_scan_jobs status to completed
	// ============================================================
	// This ensures the backend monitoring can detect when HTTPx
	// has actually finished processing (not just reading from stream)
	log.Println("\n📊 Updating batch status to completed...")
	batchID := os.Getenv("BATCH_ID")

	if batchID != "" {
		if err := supabaseClient.UpdateBatchScanStatus(batchID, "completed", map[string]interface{}{
			"completed_at": time.Now().UTC().Format(time.RFC3339),
		}); err != nil {
			// Don't fail the entire process if status update fails
			// The work is done, status update is just for tracking
			log.Printf("⚠️  Warning: Could not update batch status: %v", err)
		} else {
			log.Println("✅ Batch status updated to completed")
		}
	} else {
		log.Println("⚠️  Warning: BATCH_ID not set, skipping status update")
	}

	return nil
}

// loadStreamingConfig loads streaming configuration from environment variables
func loadStreamingConfig() (*StreamingConfig, error) {
	config := &StreamingConfig{
		StreamInputKey:    os.Getenv("STREAM_INPUT_KEY"),
		ConsumerGroupName: os.Getenv("CONSUMER_GROUP_NAME"),
		ConsumerName:      os.Getenv("CONSUMER_NAME"),
		RedisHost:         os.Getenv("REDIS_HOST"),
		RedisPort:         os.Getenv("REDIS_PORT"),
		ScanJobID:         os.Getenv("SCAN_JOB_ID"),
		BatchSize:         getEnvInt64("BATCH_SIZE", 50),                                         // Default: 50 messages per batch
		BlockMilliseconds: getEnvInt64("BLOCK_MILLISECONDS", 5000),                               // Default: 5 seconds
		MaxProcessingTime: time.Duration(getEnvInt64("MAX_PROCESSING_TIME", 3600)) * time.Second, // Default: 1 hour
	}

	// Validate required fields
	var missing []string
	if config.StreamInputKey == "" {
		missing = append(missing, "STREAM_INPUT_KEY")
	}
	if config.ConsumerGroupName == "" {
		missing = append(missing, "CONSUMER_GROUP_NAME")
	}
	if config.ConsumerName == "" {
		missing = append(missing, "CONSUMER_NAME")
	}
	if config.RedisHost == "" {
		missing = append(missing, "REDIS_HOST")
	}
	if config.RedisPort == "" {
		missing = append(missing, "REDIS_PORT")
	}
	if config.ScanJobID == "" {
		missing = append(missing, "SCAN_JOB_ID")
	}

	if len(missing) > 0 {
		return nil, fmt.Errorf("missing required environment variables: %v", missing)
	}

	return config, nil
}

// printStreamingConfig prints streaming configuration for debugging
func printStreamingConfig(config *StreamingConfig) {
	log.Println("\n📋 Streaming Configuration:")
	log.Printf("  • Stream Input: %s", config.StreamInputKey)
	log.Printf("  • Consumer Group: %s", config.ConsumerGroupName)
	log.Printf("  • Consumer Name: %s", config.ConsumerName)
	log.Printf("  • Redis: %s:%s", config.RedisHost, config.RedisPort)
	log.Printf("  • Batch Size: %d messages", config.BatchSize)
	log.Printf("  • Block Time: %d ms", config.BlockMilliseconds)
	log.Printf("  • Max Processing Time: %s", config.MaxProcessingTime)
}

// initializeRedisClient creates a Redis client for streaming
func initializeRedisClient(config *StreamingConfig) (*redis.Client, context.Context, error) {
	redisAddr := fmt.Sprintf("%s:%s", config.RedisHost, config.RedisPort)

	client := redis.NewClient(&redis.Options{
		Addr:         redisAddr,
		Password:     "", // No password for local dev, will be added for AWS ElastiCache
		DB:           0,
		DialTimeout:  10 * time.Second,
		ReadTimeout:  30 * time.Second,
		WriteTimeout: 30 * time.Second,
	})

	ctx := context.Background()

	// Test connection
	if err := client.Ping(ctx).Err(); err != nil {
		return nil, nil, fmt.Errorf("redis connection failed: %w", err)
	}

	log.Println("✅ Redis connection established")
	return client, ctx, nil
}

// ensureConsumerGroup creates the consumer group if it doesn't exist
func ensureConsumerGroup(client *redis.Client, ctx context.Context, config *StreamingConfig) error {
	// Try to create consumer group (starts from beginning with "0")
	// If group already exists, this will return an error which we can ignore
	err := client.XGroupCreateMkStream(ctx, config.StreamInputKey, config.ConsumerGroupName, "0").Err()

	if err != nil && !strings.Contains(err.Error(), "BUSYGROUP") {
		// BUSYGROUP means group already exists, which is fine
		return fmt.Errorf("failed to create consumer group: %w", err)
	}

	if err == nil {
		log.Printf("✅ Consumer group created: %s", config.ConsumerGroupName)
	} else {
		log.Printf("✅ Consumer group already exists: %s", config.ConsumerGroupName)
	}

	return nil
}

// consumeStream consumes messages from Redis Stream using XREADGROUP
func consumeStream(client *redis.Client, ctx context.Context, config *StreamingConfig,
	supabaseClient *SupabaseClient) error {

	processedCount := 0
	completionReceived := false
	startTime := time.Now()

	log.Printf("\n🔄 Starting stream consumption loop...")
	log.Printf("  • Reading from: %s", config.StreamInputKey)
	log.Printf("  • Consumer: %s in group %s", config.ConsumerName, config.ConsumerGroupName)

	for {
		// Check if max processing time exceeded
		if time.Since(startTime) > config.MaxProcessingTime {
			log.Printf("⚠️  Max processing time (%s) exceeded, stopping", config.MaxProcessingTime)
			break
		}

		// Check if we already received completion marker
		if completionReceived {
			log.Println("✅ Completion marker received, exiting consumption loop")
			break
		}

		// Read messages from stream using XREADGROUP
		streams, err := client.XReadGroup(ctx, &redis.XReadGroupArgs{
			Group:    config.ConsumerGroupName,
			Consumer: config.ConsumerName,
			Streams:  []string{config.StreamInputKey, ">"}, // ">" means only new messages
			Count:    config.BatchSize,
			Block:    time.Duration(config.BlockMilliseconds) * time.Millisecond,
		}).Result()

		if err != nil {
			if err == redis.Nil {
				// No messages available, continue waiting
				continue
			}
			return fmt.Errorf("XREADGROUP failed: %w", err)
		}

		// Process messages from all streams (should only be one in our case)
		for _, stream := range streams {
			for _, message := range stream.Messages {
				// Check if this is a completion marker
				if isCompletionMarker(message.Values) {
					log.Println("\n🏁 Completion marker detected!")
					completionReceived = true

					// ACK the completion marker
					if err := client.XAck(ctx, config.StreamInputKey, config.ConsumerGroupName, message.ID).Err(); err != nil {
						log.Printf("⚠️  Failed to ACK completion marker: %v", err)
					}

					break // Exit inner loop
				}

				// Process subdomain message (HTTP probing)
				if err := processSubdomainMessage(message, supabaseClient); err != nil {
					log.Printf("❌ Error processing message %s: %v", message.ID, err)
					// Continue processing other messages even if one fails
					continue
				}

				// ACK the message after successful processing
				if err := client.XAck(ctx, config.StreamInputKey, config.ConsumerGroupName, message.ID).Err(); err != nil {
					log.Printf("⚠️  Failed to ACK message %s: %v", message.ID, err)
				}

				processedCount++

				// Log progress every 10 messages
				if processedCount%10 == 0 {
					log.Printf("📊 Progress: %d subdomains processed", processedCount)
				}
			}

			if completionReceived {
				break // Exit outer loop
			}
		}
	}

	log.Printf("\n📊 Final Statistics:")
	log.Printf("  • Total subdomains processed: %d", processedCount)
	log.Printf("  • Processing time: %s", time.Since(startTime).Round(time.Second))

	return nil
}

// isCompletionMarker checks if a message is a completion marker
func isCompletionMarker(values map[string]interface{}) bool {
	msgType, ok := values["type"].(string)
	return ok && msgType == "completion"
}

// processSubdomainMessage processes a single subdomain message from the stream
// Performs HTTP probing and stores results to http_probes table
func processSubdomainMessage(message redis.XMessage, supabaseClient *SupabaseClient) error {
	// Parse subdomain from message
	subdomain, ok := message.Values["subdomain"].(string)
	if !ok || subdomain == "" {
		return fmt.Errorf("invalid or missing subdomain in message")
	}

	source, _ := message.Values["source"].(string)
	scanJobID, _ := message.Values["scan_job_id"].(string)

	// Read asset_id from the stream message
	// Subfinder includes asset_id in each subdomain message
	assetID, _ := message.Values["asset_id"].(string)

	// Fallback to environment variable if not in message (backward compatibility)
	if assetID == "" {
		assetID = os.Getenv("ASSET_ID")
		log.Printf("    ⚠️  asset_id not in message, using environment: %s", assetID)
	}

	log.Printf("  🌐 Probing: %s (from %s)", subdomain, source)

	// Perform HTTP probing using httpx SDK
	probes, err := probeHTTP([]string{subdomain}, scanJobID, assetID)
	if err != nil {
		log.Printf("    ⚠️  HTTP probing failed: %v", err)
		return nil // Don't fail the entire process for one failed probe
	}

	if len(probes) == 0 {
		log.Printf("    ℹ️  No HTTP response (subdomain may not have web service)")
		return nil
	}

	log.Printf("    ✅ Found %d HTTP probe(s)", len(probes))

	// Log probe details
	for _, probe := range probes {
		if probe.StatusCode != nil {
			log.Printf("       → %s: %d %s", probe.Scheme, *probe.StatusCode, probe.URL)
		}
	}

	// Store HTTP probes to database
	result, err := supabaseClient.BulkInsertHTTPProbes(probes)
	if err != nil {
		return fmt.Errorf("failed to store HTTP probes: %w", err)
	}

	log.Printf("    💾 HTTP probes: %d inserted, %d skipped, %d errors",
		result.InsertedCount, result.SkippedCount, result.ErrorCount)

	return nil
}

// getEnvInt64 returns an int64 environment variable or a default value
func getEnvInt64(key string, defaultValue int64) int64 {
	if value := os.Getenv(key); value != "" {
		var intValue int64
		if _, err := fmt.Sscanf(value, "%d", &intValue); err == nil {
			return intValue
		}
	}
	return defaultValue
}

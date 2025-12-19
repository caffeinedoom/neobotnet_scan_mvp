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

// runStreamingMode runs URL Resolver in streaming consumer mode
func runStreamingMode() error {
	log.Println("=" + strings.Repeat("=", 69))
	log.Println("🔗 URL Resolver Streaming Consumer Mode")
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

	// Initialize consumer group
	if err := ensureConsumerGroup(redisClient, ctx, config); err != nil {
		return fmt.Errorf("failed to ensure consumer group: %w", err)
	}

	// Initialize Supabase client
	supabaseClient, err := NewSupabaseClient()
	if err != nil {
		return fmt.Errorf("failed to initialize Supabase client: %w", err)
	}

	// Start consuming from stream
	log.Println("\n🔍 Starting to consume URLs from stream...")
	consumeResult, err := consumeStream(redisClient, ctx, config, supabaseClient)
	if err != nil {
		return fmt.Errorf("stream consumption failed: %w", err)
	}

	log.Println("\n✅ Stream consumption completed successfully")

	// Update batch_scan_jobs status to completed
	log.Println("\n📊 Updating batch status to completed...")
	batchID := os.Getenv("BATCH_ID")

	if batchID != "" {
		if err := supabaseClient.UpdateBatchScanStatus(batchID, "completed", map[string]interface{}{
			"completed_at":  time.Now().UTC().Format(time.RFC3339),
			"urls_received": consumeResult.URLsReceived,
			"urls_probed":   consumeResult.URLsProbed,
			"urls_skipped":  consumeResult.URLsSkipped,
			"urls_inserted": consumeResult.URLsInserted,
			"urls_updated":  consumeResult.URLsUpdated,
		}); err != nil {
			log.Printf("⚠️  Warning: Could not update batch status: %v", err)
		} else {
			log.Println("✅ Batch status updated to completed")
		}
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
		RedisPassword:     os.Getenv("REDIS_PASSWORD"),
		ScanJobID:         os.Getenv("SCAN_JOB_ID"),
		AssetID:           os.Getenv("ASSET_ID"),
		BatchSize:         getEnvInt64("BATCH_SIZE", 10),
		BlockMilliseconds: getEnvInt64("BLOCK_MILLISECONDS", 5000),
		MaxProcessingTime: time.Duration(getEnvInt64("MAX_PROCESSING_TIME", 3600)) * time.Second,
		ResolutionTTL:     time.Duration(getEnvInt64("RESOLUTION_TTL_HOURS", 24)) * time.Hour,
		ProbeBatchSize:    int(getEnvInt64("PROBE_BATCH_SIZE", 100)),
	}

	// Also check CONSUMER_GROUP (without _NAME suffix)
	if config.ConsumerGroupName == "" {
		config.ConsumerGroupName = os.Getenv("CONSUMER_GROUP")
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
	log.Printf("  • Resolution TTL: %s", config.ResolutionTTL)
	log.Printf("  • Probe Batch Size: %d URLs", config.ProbeBatchSize)
}

// initializeRedisClient creates a Redis client for streaming
func initializeRedisClient(config *StreamingConfig) (*redis.Client, context.Context, error) {
	redisAddr := fmt.Sprintf("%s:%s", config.RedisHost, config.RedisPort)

	client := redis.NewClient(&redis.Options{
		Addr:         redisAddr,
		Password:     config.RedisPassword,
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
	err := client.XGroupCreateMkStream(ctx, config.StreamInputKey, config.ConsumerGroupName, "0").Err()

	if err != nil && !strings.Contains(err.Error(), "BUSYGROUP") {
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
	supabaseClient *SupabaseClient) (*ConsumeStreamResult, error) {

	result := &ConsumeStreamResult{}
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
			Streams:  []string{config.StreamInputKey, ">"},
			Count:    config.BatchSize,
			Block:    time.Duration(config.BlockMilliseconds) * time.Millisecond,
		}).Result()

		if err != nil {
			if err == redis.Nil {
				continue
			}
			return result, fmt.Errorf("XREADGROUP failed: %w", err)
		}

		// Process messages from all streams
		for _, stream := range streams {
			for _, message := range stream.Messages {
				// Check if this is a completion marker
				if isCompletionMarker(message.Values) {
					log.Println("\n🏁 Completion marker detected!")
					if totalResults, ok := message.Values["total_results"]; ok {
						log.Printf("   Producer published %v URLs total", totalResults)
					}
					completionReceived = true

					// ACK the completion marker
					if err := client.XAck(ctx, config.StreamInputKey, config.ConsumerGroupName, message.ID).Err(); err != nil {
						log.Printf("⚠️  Failed to ACK completion marker: %v", err)
					}

					break
				}

				// Process URL message
				processResult, err := processURLMessage(message, config, supabaseClient)
				if err != nil {
					log.Printf("❌ Error processing message %s: %v", message.ID, err)
				} else {
					result.URLsReceived++
					result.URLsProbed += processResult.Probed
					result.URLsSkipped += processResult.Skipped
					result.URLsInserted += processResult.Inserted
					result.URLsUpdated += processResult.Updated
				}

				// ACK the message after processing
				if err := client.XAck(ctx, config.StreamInputKey, config.ConsumerGroupName, message.ID).Err(); err != nil {
					log.Printf("⚠️  Failed to ACK message %s: %v", message.ID, err)
				}

				// Log progress every 10 URLs
				if result.URLsReceived%10 == 0 && result.URLsReceived > 0 {
					log.Printf("📊 Progress: %d URLs received, %d probed, %d skipped",
						result.URLsReceived, result.URLsProbed, result.URLsSkipped)
				}
			}

			if completionReceived {
				break
			}
		}
	}

	result.ProcessingTime = time.Since(startTime)

	log.Printf("\n📊 Final Statistics:")
	log.Printf("  • Total URLs received: %d", result.URLsReceived)
	log.Printf("  • URLs probed: %d", result.URLsProbed)
	log.Printf("  • URLs skipped (fresh TTL): %d", result.URLsSkipped)
	log.Printf("  • URLs inserted (new): %d", result.URLsInserted)
	log.Printf("  • URLs updated: %d", result.URLsUpdated)
	log.Printf("  • Processing time: %s", result.ProcessingTime.Round(time.Second))

	return result, nil
}

// ProcessURLResult holds the result of processing a single URL message
type ProcessURLResult struct {
	Probed   int
	Skipped  int
	Inserted int
	Updated  int
}

// processURLMessage processes a single URL message from the stream
func processURLMessage(message redis.XMessage, config *StreamingConfig,
	supabaseClient *SupabaseClient) (*ProcessURLResult, error) {

	result := &ProcessURLResult{}

	// Parse URL from message
	rawURL, ok := message.Values["url"].(string)
	if !ok || rawURL == "" {
		return result, fmt.Errorf("invalid or missing URL in message")
	}

	// Parse source
	source := "unknown"
	if s, ok := message.Values["source"].(string); ok {
		source = s
	}

	// Parse asset_id
	assetID := config.AssetID
	if a, ok := message.Values["asset_id"].(string); ok && a != "" {
		assetID = a
	}

	log.Printf("  🔗 Processing: %s (from %s)", rawURL, source)

	// Normalize URL and generate hash
	normalizedURL, urlHash, err := NormalizeAndHash(rawURL)
	if err != nil {
		return result, fmt.Errorf("failed to normalize URL: %w", err)
	}

	// Check if URL already exists in database
	existing, err := supabaseClient.GetURLByHash(assetID, urlHash)
	if err != nil {
		return result, fmt.Errorf("failed to check existing URL: %w", err)
	}

	if existing != nil {
		// URL exists - check TTL
		if existing.ResolvedAt != nil {
			age := time.Since(*existing.ResolvedAt)
			if age < config.ResolutionTTL {
				// Fresh - skip probing, just add source if new
				log.Printf("    ⏭️  Skipped (resolved %s ago, TTL: %s)", age.Round(time.Minute), config.ResolutionTTL)
				result.Skipped++

				// Add source if not already present
				if err := supabaseClient.AddSourceToURL(assetID, urlHash, source); err != nil {
					log.Printf("    ⚠️  Failed to add source: %v", err)
				}

				return result, nil
			}
			// Stale - will re-probe
			log.Printf("    🔄 Stale (resolved %s ago), re-probing...", age.Round(time.Minute))
		}
	}

	// Probe the URL
	probeResult := ProbeURL(normalizedURL)
	result.Probed++

	if probeResult.Error != nil {
		log.Printf("    ❌ Probe error: %v", probeResult.Error)
		// Still update the record to mark it as dead
		probeResult.IsAlive = false
	} else if probeResult.IsAlive {
		log.Printf("    ✅ %d %s (%dms)", probeResult.StatusCode, probeResult.ContentType, probeResult.ResponseTimeMs)
	} else {
		log.Printf("    ⚠️  No response")
	}

	// Store or update in database
	if existing != nil {
		// Update existing record
		if err := supabaseClient.UpdateURLResolution(assetID, urlHash, probeResult, &source); err != nil {
			return result, fmt.Errorf("failed to update URL: %w", err)
		}
		result.Updated++
		log.Printf("    💾 Updated existing record")
	} else {
		// Insert new record
		now := time.Now()
		domain, path, queryParams, fileExt, err := ParseURLComponents(normalizedURL)
		if err != nil {
			return result, fmt.Errorf("failed to parse URL components: %w", err)
		}

		record := &URLRecord{
			AssetID:           assetID,
			URL:               normalizedURL,
			URLHash:           urlHash,
			Domain:            domain,
			Path:              &path,
			QueryParams:       queryParams,
			Sources:           []string{source},
			FirstDiscoveredBy: source,
			FirstDiscoveredAt: now,
			ResolvedAt:        &now,
			IsAlive:           &probeResult.IsAlive,
			StatusCode:        &probeResult.StatusCode,
			ResponseTimeMs:    &probeResult.ResponseTimeMs,
			Technologies:      probeResult.Technologies,
			RedirectChain:     probeResult.RedirectChain,
			CreatedAt:         now,
			UpdatedAt:         now,
		}

		// Add optional fields
		if probeResult.ContentType != "" {
			record.ContentType = &probeResult.ContentType
		}
		if probeResult.ContentLength > 0 {
			record.ContentLength = &probeResult.ContentLength
		}
		if probeResult.Title != "" {
			record.Title = &probeResult.Title
		}
		if probeResult.FinalURL != "" {
			record.FinalURL = &probeResult.FinalURL
		}
		if probeResult.Webserver != "" {
			record.Webserver = &probeResult.Webserver
		}
		if fileExt != nil {
			record.FileExtension = fileExt
		}

		if err := supabaseClient.InsertURL(record); err != nil {
			return result, fmt.Errorf("failed to insert URL: %w", err)
		}
		result.Inserted++
		log.Printf("    💾 Inserted new record")
	}

	return result, nil
}

// isCompletionMarker checks if a message is a completion marker
func isCompletionMarker(values map[string]interface{}) bool {
	msgType, ok := values["type"].(string)
	return ok && msgType == "completion"
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


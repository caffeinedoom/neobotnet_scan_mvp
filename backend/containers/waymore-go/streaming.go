package main

import (
	"context"
	"fmt"
	"log"
	"os"
	"time"

	"github.com/go-redis/redis/v8"
)

// RedisStreamProducer handles streaming URLs to Redis
type RedisStreamProducer struct {
	client        *redis.Client
	streamKey     string
	ctx           context.Context
	streamedCount int
}

// NewRedisStreamProducer creates a new Redis stream producer
func NewRedisStreamProducer() (*RedisStreamProducer, error) {
	redisHost := os.Getenv("REDIS_HOST")
	redisPort := os.Getenv("REDIS_PORT")
	redisPassword := os.Getenv("REDIS_PASSWORD")
	streamKey := os.Getenv("STREAM_OUTPUT_KEY")

	if redisHost == "" || redisPort == "" {
		return nil, fmt.Errorf("REDIS_HOST and REDIS_PORT are required")
	}

	if streamKey == "" {
		return nil, fmt.Errorf("STREAM_OUTPUT_KEY is required for streaming mode")
	}

	redisAddr := fmt.Sprintf("%s:%s", redisHost, redisPort)

	client := redis.NewClient(&redis.Options{
		Addr:         redisAddr,
		Password:     redisPassword,
		DB:           0,
		DialTimeout:  10 * time.Second,
		ReadTimeout:  30 * time.Second,
		WriteTimeout: 30 * time.Second,
	})

	ctx := context.Background()

	// Test connection
	if err := client.Ping(ctx).Err(); err != nil {
		return nil, fmt.Errorf("redis connection failed: %w", err)
	}

	log.Printf("✅ Redis connection established: %s", redisAddr)

	return &RedisStreamProducer{
		client:    client,
		streamKey: streamKey,
		ctx:       ctx,
	}, nil
}

// StreamURLs streams multiple URLs to Redis
func (p *RedisStreamProducer) StreamURLs(urls []DiscoveredURL) (int, error) {
	streamed := 0

	for _, url := range urls {
		if err := p.StreamURL(url); err != nil {
			log.Printf("⚠️  Failed to stream URL %s: %v", url.URL, err)
			continue
		}
		streamed++
	}

	return streamed, nil
}

// StreamURL streams a single URL to Redis
func (p *RedisStreamProducer) StreamURL(url DiscoveredURL) error {
	// Build message values (compatible with URL Resolver consumer)
	values := map[string]interface{}{
		"url":           url.URL,
		"parent_domain": url.ParentDomain,
		"source":        url.Source,
		"asset_id":      url.AssetID,
		"scan_job_id":   url.ScanJobID,
		"discovered_at": url.DiscoveredAt,
		"type":          "url", // Distinguish from completion markers
	}

	// XADD to stream with maxlen for memory management
	_, err := p.client.XAdd(p.ctx, &redis.XAddArgs{
		Stream: p.streamKey,
		MaxLen: 100000, // Cap stream at 100k messages
		Approx: true,   // Use ~ for performance
		Values: values,
	}).Result()

	if err != nil {
		return fmt.Errorf("XADD failed: %w", err)
	}

	p.streamedCount++
	return nil
}

// SendCompletionMarker sends a completion marker to signal end of stream
func (p *RedisStreamProducer) SendCompletionMarker(totalURLs int) error {
	values := map[string]interface{}{
		"type":          "completion",
		"module":        "waymore",
		"scan_job_id":   os.Getenv("SCAN_JOB_ID"),
		"timestamp":     time.Now().UTC().Format(time.RFC3339),
		"total_results": fmt.Sprintf("%d", totalURLs),
	}

	_, err := p.client.XAdd(p.ctx, &redis.XAddArgs{
		Stream: p.streamKey,
		Values: values,
	}).Result()

	if err != nil {
		return fmt.Errorf("failed to send completion marker: %w", err)
	}

	log.Printf("📤 Completion marker sent: %d total URLs", totalURLs)
	return nil
}

// GetStreamedCount returns the number of URLs streamed
func (p *RedisStreamProducer) GetStreamedCount() int {
	return p.streamedCount
}

// Close closes the Redis connection
func (p *RedisStreamProducer) Close() error {
	if p.client != nil {
		return p.client.Close()
	}
	return nil
}


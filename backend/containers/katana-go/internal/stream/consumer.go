package stream

import (
	"context"
	"fmt"
	"strings"
	"time"

	"katana-go/internal/config"
	"katana-go/internal/database"
	"katana-go/internal/models"
	"katana-go/internal/scanner"

	"github.com/go-redis/redis/v8"
)

// URLMessage represents a URL message from the HTTPx stream
type URLMessage struct {
	URL         string `json:"url"`
	StatusCode  int    `json:"status_code"`
	ContentType string `json:"content_type"`
	Title       string `json:"title"`
	AssetID     string `json:"asset_id"`
	ScanJobID   string `json:"scan_job_id"`
	Source      string `json:"source"`
	PublishedAt string `json:"published_at"`
}

// ConsumerResult holds statistics from stream consumption
type ConsumerResult struct {
	URLsReceived      int
	URLsCrawled       int
	EndpointsFound    int
	EndpointsStored   int
	URLsPublished     int // URLs published to URL Resolver stream
	ProcessingTime    time.Duration
}

// Consumer handles Redis stream consumption for Katana
type Consumer struct {
	cfg          *config.Config
	redisClient  *redis.Client
	ctx          context.Context
	repo         *database.Repository
	scanner      *scanner.Scanner
	logger       *config.Logger
}

// NewConsumer creates a new stream consumer
func NewConsumer(cfg *config.Config, repo *database.Repository, scanner *scanner.Scanner) (*Consumer, error) {
	// Initialize Redis client
	redisAddr := fmt.Sprintf("%s:%s", cfg.RedisHost, cfg.RedisPort)
	
	redisClient := redis.NewClient(&redis.Options{
		Addr:         redisAddr,
		Password:     cfg.RedisPassword,
		DB:           0,
		DialTimeout:  10 * time.Second,
		ReadTimeout:  30 * time.Second,
		WriteTimeout: 30 * time.Second,
	})

	ctx := context.Background()

	// Test connection
	if err := redisClient.Ping(ctx).Err(); err != nil {
		return nil, fmt.Errorf("redis connection failed: %w", err)
	}

	cfg.Logger.Info("Redis connection established: %s", redisAddr)

	return &Consumer{
		cfg:         cfg,
		redisClient: redisClient,
		ctx:         ctx,
		repo:        repo,
		scanner:     scanner,
		logger:      cfg.Logger,
	}, nil
}

// EnsureConsumerGroup creates the consumer group if it doesn't exist
func (c *Consumer) EnsureConsumerGroup() error {
	// Try to create consumer group (starts from beginning with "0")
	// If group already exists, this will return an error which we can ignore
	err := c.redisClient.XGroupCreateMkStream(c.ctx, c.cfg.StreamInputKey, c.cfg.ConsumerGroup, "0").Err()

	if err != nil && !strings.Contains(err.Error(), "BUSYGROUP") {
		// BUSYGROUP means group already exists, which is fine
		return fmt.Errorf("failed to create consumer group: %w", err)
	}

	if err == nil {
		c.logger.Info("Consumer group created: %s", c.cfg.ConsumerGroup)
	} else {
		c.logger.Info("Consumer group already exists: %s", c.cfg.ConsumerGroup)
	}

	return nil
}

// Consume starts consuming URLs from the stream and crawling them
func (c *Consumer) Consume() (*ConsumerResult, error) {
	result := &ConsumerResult{}
	completionReceived := false
	startTime := time.Now()

	// Configurable values
	batchSize := int64(10)                           // URLs per batch read
	blockTimeout := 5 * time.Second                  // Block timeout for XREADGROUP
	maxProcessingTime := 3600 * time.Second          // 1 hour max

	c.logger.Info("Starting stream consumption loop...")
	c.logger.Info("  • Reading from: %s", c.cfg.StreamInputKey)
	c.logger.Info("  • Consumer: %s in group %s", c.cfg.ConsumerName, c.cfg.ConsumerGroup)

	for {
		// Check if max processing time exceeded
		if time.Since(startTime) > maxProcessingTime {
			c.logger.Warn("Max processing time (%s) exceeded, stopping", maxProcessingTime)
			break
		}

		// Check if we already received completion marker
		if completionReceived {
			c.logger.Info("Completion marker received, exiting consumption loop")
			break
		}

		// Read messages from stream using XREADGROUP
		streams, err := c.redisClient.XReadGroup(c.ctx, &redis.XReadGroupArgs{
			Group:    c.cfg.ConsumerGroup,
			Consumer: c.cfg.ConsumerName,
			Streams:  []string{c.cfg.StreamInputKey, ">"}, // ">" means only new messages
			Count:    batchSize,
			Block:    blockTimeout,
		}).Result()

		if err != nil {
			if err == redis.Nil {
				// No messages available, continue waiting
				continue
			}
			return result, fmt.Errorf("XREADGROUP failed: %w", err)
		}

		// Process messages from all streams
		for _, stream := range streams {
			for _, message := range stream.Messages {
				// Check if this is a completion marker
				if c.isCompletionMarker(message.Values) {
					c.logger.Info("🏁 Completion marker detected from HTTPx!")
					
					// Log completion marker details
					if totalResults, ok := message.Values["total_results"]; ok {
						c.logger.Info("   HTTPx published %v URLs total", totalResults)
					}
					
					completionReceived = true

					// ACK the completion marker
					if err := c.redisClient.XAck(c.ctx, c.cfg.StreamInputKey, c.cfg.ConsumerGroup, message.ID).Err(); err != nil {
						c.logger.Warn("Failed to ACK completion marker: %v", err)
					}

					break // Exit inner loop
				}

				// Process URL message (crawling)
				crawlResult, err := c.processURLMessage(message)
				if err != nil {
					c.logger.Error("Error processing message %s: %v", message.ID, err)
					// Continue processing other messages even if one fails
				} else {
					result.URLsReceived++
					result.URLsCrawled++
					result.EndpointsFound += crawlResult.EndpointsFound
					result.EndpointsStored += crawlResult.EndpointsStored
					result.URLsPublished += crawlResult.EndpointsPublished
				}

				// ACK the message after processing
				if err := c.redisClient.XAck(c.ctx, c.cfg.StreamInputKey, c.cfg.ConsumerGroup, message.ID).Err(); err != nil {
					c.logger.Warn("Failed to ACK message %s: %v", message.ID, err)
				}

				// Log progress every 5 URLs
				if result.URLsCrawled%5 == 0 && result.URLsCrawled > 0 {
					c.logger.Info("📊 Progress: %d URLs crawled, %d endpoints found",
						result.URLsCrawled, result.EndpointsFound)
				}
			}

			if completionReceived {
				break // Exit outer loop
			}
		}
	}

	result.ProcessingTime = time.Since(startTime)

	// Send completion marker to URL Resolver stream
	if err := c.sendURLCompletionMarker(result.URLsPublished); err != nil {
		c.logger.Warn("Failed to send completion marker to URL stream: %v", err)
	}

	c.logger.Info("📊 Final Statistics:")
	c.logger.Info("  • URLs received: %d", result.URLsReceived)
	c.logger.Info("  • URLs crawled: %d", result.URLsCrawled)
	c.logger.Info("  • Endpoints found: %d", result.EndpointsFound)
	c.logger.Info("  • Endpoints stored: %d", result.EndpointsStored)
	c.logger.Info("  • URLs published: %d", result.URLsPublished)
	c.logger.Info("  • Processing time: %s", result.ProcessingTime.Round(time.Second))

	return result, nil
}

// CrawlResult holds the result of crawling a single URL
type CrawlResult struct {
	EndpointsFound    int
	EndpointsStored   int
	EndpointsPublished int
}

// processURLMessage processes a single URL message from the stream
func (c *Consumer) processURLMessage(message redis.XMessage) (*CrawlResult, error) {
	result := &CrawlResult{}

	// Parse URL from message
	url, ok := message.Values["url"].(string)
	if !ok || url == "" {
		return result, fmt.Errorf("invalid or missing URL in message")
	}

	// Parse optional fields
	title := ""
	if t, ok := message.Values["title"].(string); ok {
		title = t
	}

	c.logger.Info("🕷️ Crawling: %s", url)
	if title != "" {
		c.logger.Debug("   Title: %s", title)
	}

	// Perform crawl using Katana scanner
	ctx := context.Background()
	endpoints, err := c.scanner.Crawl(ctx, []string{url})
	if err != nil {
		c.logger.Warn("Crawl failed for %s: %v", url, err)
		return result, nil // Don't fail the entire process for one failed crawl
	}

	result.EndpointsFound = len(endpoints)
	c.logger.Info("   ✅ Found %d endpoints", len(endpoints))

	// Store endpoints to database
	if len(endpoints) > 0 {
		if err := c.repo.BatchUpsertEndpoints(endpoints); err != nil {
			c.logger.Error("Failed to store endpoints for %s: %v", url, err)
			return result, nil // Continue processing other URLs
		}
		result.EndpointsStored = len(endpoints)
		c.logger.Debug("   💾 Stored %d endpoints", len(endpoints))

		// Publish endpoints to URL Resolver stream (producer)
		published, err := c.publishToURLStream(endpoints)
		if err != nil {
			c.logger.Warn("Failed to publish endpoints to URL stream: %v", err)
		}
		result.EndpointsPublished = published
	}

	return result, nil
}

// isCompletionMarker checks if a message is a completion marker from HTTPx
func (c *Consumer) isCompletionMarker(values map[string]interface{}) bool {
	msgType, ok := values["type"].(string)
	return ok && msgType == "completion"
}

// Close cleans up consumer resources
func (c *Consumer) Close() error {
	if c.redisClient != nil {
		return c.redisClient.Close()
	}
	return nil
}

// publishToURLStream publishes discovered endpoints to the URL Resolver stream
// This acts as a producer for the url-resolver consumer
func (c *Consumer) publishToURLStream(endpoints []*models.CrawledEndpoint) (int, error) {
	if c.cfg.StreamOutputKey == "" {
		// No output stream configured, skip publishing
		return 0, nil
	}

	published := 0
	for _, ep := range endpoints {
		// Build scan_job_id value
		scanJobID := ""
		if ep.ScanJobID != nil {
			scanJobID = *ep.ScanJobID
		}

		values := map[string]interface{}{
			"url":           ep.URL,
			"asset_id":      ep.AssetID,
			"scan_job_id":   scanJobID,
			"source":        "katana",
			"published_at":  time.Now().UTC().Format(time.RFC3339),
		}

		// Add optional fields if present
		if ep.Method != "" {
			values["method"] = ep.Method
		}
		if ep.ContentType != nil && *ep.ContentType != "" {
			values["content_type"] = *ep.ContentType
		}

		err := c.redisClient.XAdd(c.ctx, &redis.XAddArgs{
			Stream: c.cfg.StreamOutputKey,
			Values: values,
		}).Err()

		if err != nil {
			c.logger.Warn("Failed to publish URL to stream: %s - %v", ep.URL, err)
			continue
		}
		published++
	}

	if published > 0 {
		c.logger.Debug("   📤 Published %d URLs to %s", published, c.cfg.StreamOutputKey)
	}

	return published, nil
}

// sendURLCompletionMarker sends a completion marker to the URL Resolver stream
func (c *Consumer) sendURLCompletionMarker(totalURLs int) error {
	if c.cfg.StreamOutputKey == "" {
		// No output stream configured, skip
		return nil
	}

	values := map[string]interface{}{
		"type":          "completion",
		"source":        "katana",
		"scan_job_id":   c.cfg.ScanJobID,
		"asset_id":      c.cfg.AssetID,
		"total_results": totalURLs,
		"completed_at":  time.Now().UTC().Format(time.RFC3339),
	}

	err := c.redisClient.XAdd(c.ctx, &redis.XAddArgs{
		Stream: c.cfg.StreamOutputKey,
		Values: values,
	}).Err()

	if err != nil {
		return fmt.Errorf("failed to send completion marker: %w", err)
	}

	c.logger.Info("🏁 Completion marker sent to %s (total: %d URLs)", c.cfg.StreamOutputKey, totalURLs)
	return nil
}


package stream

import (
	"context"
	"fmt"
	"strings"
	"time"

	"github.com/go-redis/redis/v8"
	"github.com/sirupsen/logrus"

	"tyvt-go/internal/client"
	"tyvt-go/internal/config"
	"tyvt-go/internal/database"
	"tyvt-go/internal/models"
)

// Consumer handles Redis stream consumption from HTTPx output
type Consumer struct {
	cfg         *config.Config
	redisClient *redis.Client
	ctx         context.Context
	repo        *database.Repository
	vtClient    *client.VirusTotalClient
	logger      *logrus.Logger
}

// NewConsumer creates a new stream consumer
func NewConsumer(
	cfg *config.Config,
	repo *database.Repository,
	vtClient *client.VirusTotalClient,
) (*Consumer, error) {
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

	cfg.Logger.Infof("🔌 Redis connected: %s", redisAddr)

	return &Consumer{
		cfg:         cfg,
		redisClient: redisClient,
		ctx:         ctx,
		repo:        repo,
		vtClient:    vtClient,
		logger:      cfg.Logger,
	}, nil
}

// EnsureConsumerGroup creates the consumer group if it doesn't exist
func (c *Consumer) EnsureConsumerGroup() error {
	// Try to create consumer group (starts from beginning with "0")
	err := c.redisClient.XGroupCreateMkStream(
		c.ctx,
		c.cfg.StreamInputKey,
		c.cfg.ConsumerGroup,
		"0",
	).Err()

	if err != nil && !strings.Contains(err.Error(), "BUSYGROUP") {
		return fmt.Errorf("failed to create consumer group: %w", err)
	}

	if err == nil {
		c.logger.Infof("✅ Consumer group created: %s", c.cfg.ConsumerGroup)
	} else {
		c.logger.Infof("✅ Consumer group exists: %s", c.cfg.ConsumerGroup)
	}

	return nil
}

// Consume starts consuming subdomains from the HTTPx stream
func (c *Consumer) Consume() (*models.ConsumeResult, error) {
	result := &models.ConsumeResult{}
	completionReceived := false
	startTime := time.Now()

	// Configuration
	batchSize := int64(10)
	blockTimeout := 5 * time.Second
	maxProcessingTime := c.cfg.ScanTimeout

	// Track unique subdomains to avoid duplicate VT queries
	queriedSubdomains := make(map[string]bool)

	c.logger.Info("🌊 Starting stream consumption loop...")
	c.logger.Infof("  • Reading from: %s", c.cfg.StreamInputKey)
	c.logger.Infof("  • Consumer: %s in group %s", c.cfg.ConsumerName, c.cfg.ConsumerGroup)

	for {
		// Check timeout
		if time.Since(startTime) > maxProcessingTime {
			c.logger.Warn("⏰ Max processing time exceeded, stopping")
			break
		}

		// Check completion
		if completionReceived {
			c.logger.Info("✅ Completion marker received, exiting loop")
			break
		}

		// Read messages from stream
		streams, err := c.redisClient.XReadGroup(c.ctx, &redis.XReadGroupArgs{
			Group:    c.cfg.ConsumerGroup,
			Consumer: c.cfg.ConsumerName,
			Streams:  []string{c.cfg.StreamInputKey, ">"},
			Count:    batchSize,
			Block:    blockTimeout,
		}).Result()

		if err != nil {
			if err == redis.Nil {
				continue // No messages, keep waiting
			}
			return result, fmt.Errorf("XREADGROUP failed: %w", err)
		}

		// Process messages
		for _, stream := range streams {
			for _, message := range stream.Messages {
				// Check for completion marker
				if c.isCompletionMarker(message.Values) {
					c.logger.Info("🏁 Completion marker detected from HTTPx!")

					if totalResults, ok := message.Values["total_results"]; ok {
						c.logger.Infof("   HTTPx published %v URLs total", totalResults)
					}

					completionReceived = true
					c.redisClient.XAck(c.ctx, c.cfg.StreamInputKey, c.cfg.ConsumerGroup, message.ID)
					break
				}

				// Process HTTPx message
				subdomain := c.extractSubdomain(message.Values)
				if subdomain == "" {
					c.redisClient.XAck(c.ctx, c.cfg.StreamInputKey, c.cfg.ConsumerGroup, message.ID)
					continue
				}

				result.SubdomainsReceived++

				// Skip if already queried (deduplication)
				if queriedSubdomains[subdomain] {
					c.logger.Debugf("   Skipping duplicate: %s", subdomain)
					c.redisClient.XAck(c.ctx, c.cfg.StreamInputKey, c.cfg.ConsumerGroup, message.ID)
					continue
				}
				queriedSubdomains[subdomain] = true

				// Query VirusTotal for this subdomain
				queryResult, err := c.processSubdomain(subdomain)
				if err != nil {
					c.logger.Warnf("⚠️  Failed to query VT for %s: %v", subdomain, err)
				} else {
					result.SubdomainsQueried++
					result.URLsDiscovered += queryResult.URLsDiscovered
					result.URLsStored += queryResult.URLsStored
					result.URLsPublished += queryResult.URLsPublished
				}

				// Acknowledge message
				c.redisClient.XAck(c.ctx, c.cfg.StreamInputKey, c.cfg.ConsumerGroup, message.ID)

				// Log progress every 5 subdomains
				if result.SubdomainsQueried%5 == 0 && result.SubdomainsQueried > 0 {
					c.logger.Infof("📊 Progress: %d subdomains queried, %d URLs discovered",
						result.SubdomainsQueried, result.URLsDiscovered)
				}
			}

			if completionReceived {
				break
			}
		}
	}

	result.ProcessingTime = time.Since(startTime)

	// Send completion marker to output stream (if configured)
	if err := c.sendCompletionMarker(result.URLsPublished); err != nil {
		c.logger.Warnf("Failed to send completion marker: %v", err)
	}

	// Final statistics
	c.logger.Info("📊 Final Statistics:")
	c.logger.Infof("  • Subdomains received: %d", result.SubdomainsReceived)
	c.logger.Infof("  • Subdomains queried: %d", result.SubdomainsQueried)
	c.logger.Infof("  • URLs discovered: %d", result.URLsDiscovered)
	c.logger.Infof("  • URLs stored: %d", result.URLsStored)
	c.logger.Infof("  • URLs published: %d", result.URLsPublished)
	c.logger.Infof("  • Processing time: %s", result.ProcessingTime.Round(time.Second))

	return result, nil
}

// SubdomainResult holds results from processing a single subdomain
type SubdomainResult struct {
	URLsDiscovered int
	URLsStored     int
	URLsPublished  int
}

// processSubdomain queries VT for a subdomain and processes results
func (c *Consumer) processSubdomain(subdomain string) (*SubdomainResult, error) {
	result := &SubdomainResult{}

	c.logger.Infof("🔍 Querying VirusTotal: %s", subdomain)

	// Query VirusTotal
	vtResult, err := c.vtClient.QueryDomain(c.ctx, subdomain)
	if err != nil {
		return result, err
	}

	if vtResult.ResponseCode != 1 {
		c.logger.Debugf("   Domain not found in VT database: %s", subdomain)
		return result, nil
	}

	result.URLsDiscovered = len(vtResult.UndetectedURLs)

	if result.URLsDiscovered == 0 {
		c.logger.Debugf("   No undetected URLs for: %s", subdomain)
		return result, nil
	}

	c.logger.Infof("   ✅ Found %d undetected URLs", result.URLsDiscovered)

	// Convert to database models
	discoveredURLs := make([]models.DiscoveredURL, 0, len(vtResult.UndetectedURLs))
	for _, u := range vtResult.UndetectedURLs {
		discoveredURLs = append(discoveredURLs, models.DiscoveredURL{
			ScanJobID:    c.cfg.ScanJobID,
			AssetID:      c.cfg.AssetID,
			Subdomain:    subdomain,
			URL:          u.URL,
			Positives:    u.Positives,
			Total:        u.Total,
			ScanDate:     u.ScanDate,
			Source:       "virustotal",
			DiscoveredAt: time.Now(),
		})
	}

	// Store in database
	if err := c.repo.BatchInsertDiscoveredURLs(discoveredURLs); err != nil {
		c.logger.Errorf("Failed to store URLs for %s: %v", subdomain, err)
	} else {
		result.URLsStored = len(discoveredURLs)
	}

	// Publish to output stream (for downstream modules like url-resolver or katana)
	published, err := c.publishToOutputStream(discoveredURLs)
	if err != nil {
		c.logger.Warnf("Failed to publish URLs to stream: %v", err)
	}
	result.URLsPublished = published

	return result, nil
}

// extractSubdomain gets the subdomain from an HTTPx stream message
func (c *Consumer) extractSubdomain(values map[string]interface{}) string {
	// HTTPx messages contain the URL - we need to extract the subdomain/host
	if urlStr, ok := values["url"].(string); ok && urlStr != "" {
		// Parse URL to get host
		if strings.HasPrefix(urlStr, "http://") || strings.HasPrefix(urlStr, "https://") {
			parts := strings.SplitN(urlStr, "://", 2)
			if len(parts) == 2 {
				hostPath := parts[1]
				host := strings.SplitN(hostPath, "/", 2)[0]
				// Remove port if present
				host = strings.SplitN(host, ":", 2)[0]
				return host
			}
		}
	}

	// Fallback: try subdomain field directly
	if subdomain, ok := values["subdomain"].(string); ok {
		return subdomain
	}

	// Fallback: try host field
	if host, ok := values["host"].(string); ok {
		return host
	}

	return ""
}

// isCompletionMarker checks if a message is a completion marker
func (c *Consumer) isCompletionMarker(values map[string]interface{}) bool {
	msgType, ok := values["type"].(string)
	return ok && msgType == "completion"
}

// publishToOutputStream publishes discovered URLs to the output stream
func (c *Consumer) publishToOutputStream(urls []models.DiscoveredURL) (int, error) {
	if c.cfg.StreamOutputKey == "" {
		return 0, nil // No output stream configured
	}

	published := 0
	for _, u := range urls {
		values := map[string]interface{}{
			"url":          u.URL,
			"subdomain":    u.Subdomain,
			"asset_id":     u.AssetID,
			"scan_job_id":  u.ScanJobID,
			"source":       "virustotal",
			"positives":    u.Positives,
			"total":        u.Total,
			"published_at": time.Now().UTC().Format(time.RFC3339),
		}

		err := c.redisClient.XAdd(c.ctx, &redis.XAddArgs{
			Stream: c.cfg.StreamOutputKey,
			Values: values,
		}).Err()

		if err != nil {
			c.logger.Warnf("Failed to publish URL: %s - %v", u.URL, err)
			continue
		}
		published++
	}

	if published > 0 {
		c.logger.Debugf("   📤 Published %d URLs to %s", published, c.cfg.StreamOutputKey)
	}

	return published, nil
}

// sendCompletionMarker sends a completion marker to the output stream
func (c *Consumer) sendCompletionMarker(totalURLs int) error {
	if c.cfg.StreamOutputKey == "" {
		return nil
	}

	values := map[string]interface{}{
		"type":          "completion",
		"source":        "tyvt",
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

	c.logger.Infof("🏁 Completion marker sent to %s (total: %d URLs)", c.cfg.StreamOutputKey, totalURLs)
	return nil
}

// Close cleans up consumer resources
func (c *Consumer) Close() error {
	if c.redisClient != nil {
		return c.redisClient.Close()
	}
	return nil
}


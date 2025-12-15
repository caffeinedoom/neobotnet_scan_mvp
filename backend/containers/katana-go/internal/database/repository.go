package database

import (
	"fmt"
	"time"

	"katana-go/internal/config"
	"katana-go/internal/models"
)

// Repository handles database operations for crawled endpoints
type Repository struct {
	client *SupabaseClient
	logger *config.Logger
}

// NewRepository creates a new Repository instance
func NewRepository(client *SupabaseClient, logger *config.Logger) *Repository {
	return &Repository{
		client: client,
		logger: logger,
	}
}

// UpsertEndpoint inserts or updates a crawled endpoint using ON CONFLICT logic.
// 
// Upsert behavior (based on UNIQUE constraint on asset_id + url_hash):
// - If endpoint doesn't exist: INSERT with all fields
// - If endpoint exists: UPDATE last_seen_at and increment times_discovered
//
// This matches the PostgreSQL logic:
//   ON CONFLICT (asset_id, url_hash) DO UPDATE SET
//     last_seen_at = EXCLUDED.last_seen_at,
//     times_discovered = crawled_endpoints.times_discovered + 1
func (r *Repository) UpsertEndpoint(endpoint *models.CrawledEndpoint) error {
	// Prepare data for upsert
	data := map[string]interface{}{
		"asset_id":         endpoint.AssetID,
		"scan_job_id":      endpoint.ScanJobID,
		"url":              endpoint.URL,
		"url_hash":         endpoint.URLHash,
		"method":           endpoint.Method,
		"source_url":       endpoint.SourceURL,
		"is_seed_url":      endpoint.IsSeedURL,
		"status_code":      endpoint.StatusCode,
		"content_type":     endpoint.ContentType,
		"content_length":   endpoint.ContentLength,
		"first_seen_at":    endpoint.FirstSeenAt,
		"last_seen_at":     endpoint.LastSeenAt,
		"times_discovered": endpoint.TimesDiscovered,
	}

	// Use Supabase upsert (resolution=merge-duplicates)
	// Note: Supabase's merge-duplicates doesn't support custom ON CONFLICT logic,
	// so we need to handle this manually by checking if the endpoint exists first.
	
	// Check if endpoint exists
	existing, err := r.GetEndpointByHash(endpoint.AssetID, endpoint.URLHash)
	if err != nil {
		// If error is "not found", proceed with insert
		// Otherwise, return the error
		if err.Error() != "endpoint not found" {
			return fmt.Errorf("failed to check existing endpoint: %w", err)
		}
	}

	if existing != nil {
		// Endpoint exists - update only last_seen_at and times_discovered
		updateData := map[string]interface{}{
			"last_seen_at":     endpoint.LastSeenAt,
			"times_discovered": existing.TimesDiscovered + 1,
		}
		
		filters := map[string]string{
			"asset_id":  fmt.Sprintf("eq.%s", endpoint.AssetID),
			"url_hash":  fmt.Sprintf("eq.%s", endpoint.URLHash),
		}

		if err := r.client.Update("crawled_endpoints", filters, updateData); err != nil {
			return fmt.Errorf("failed to update endpoint: %w", err)
		}

		r.logger.Debug("Updated existing endpoint: url=%s, times_discovered=%d",
			endpoint.URL, existing.TimesDiscovered+1)
	} else {
		// Endpoint doesn't exist - insert new record
		if err := r.client.Insert("crawled_endpoints", data, false); err != nil {
			return fmt.Errorf("failed to insert endpoint: %w", err)
		}

		r.logger.Debug("Inserted new endpoint: url=%s, is_seed=%v",
			endpoint.URL, endpoint.IsSeedURL)
	}

	return nil
}

// GetEndpointByHash retrieves an endpoint by asset_id and url_hash
func (r *Repository) GetEndpointByHash(assetID, urlHash string) (*models.CrawledEndpoint, error) {
	filters := map[string]string{
		"asset_id": fmt.Sprintf("eq.%s", assetID),
		"url_hash": fmt.Sprintf("eq.%s", urlHash),
	}

	var result []models.CrawledEndpoint
	if err := r.client.Query("crawled_endpoints", filters, &result); err != nil {
		return nil, fmt.Errorf("failed to query endpoint: %w", err)
	}

	if len(result) == 0 {
		return nil, fmt.Errorf("endpoint not found")
	}

	return &result[0], nil
}

// BatchUpsertEndpoints performs batch upsert for multiple endpoints
// Processes endpoints one by one (can be optimized later with bulk operations)
func (r *Repository) BatchUpsertEndpoints(endpoints []*models.CrawledEndpoint) error {
	successCount := 0
	errorCount := 0

	for _, endpoint := range endpoints {
		if err := r.UpsertEndpoint(endpoint); err != nil {
			r.logger.Error("Failed to upsert endpoint %s: %v", endpoint.URL, err)
			errorCount++
			continue
		}
		successCount++
	}

	r.logger.Info("Batch upsert completed: total=%d, success=%d, errors=%d",
		len(endpoints), successCount, errorCount)

	if errorCount > 0 {
		return fmt.Errorf("batch upsert completed with %d errors out of %d endpoints", errorCount, len(endpoints))
	}

	return nil
}

// GetSeedURLsForAsset retrieves seed URLs (from http_probes) for a given asset
// Supports pagination via offset and limit (set limit=0 for all results)
// These will be used as crawl targets in batch/streaming modes
func (r *Repository) GetSeedURLsForAsset(assetID string, offset, limit int) ([]string, error) {
	filters := map[string]string{
		"asset_id":    fmt.Sprintf("eq.%s", assetID),
		"status_code": "eq.200", // Only crawl URLs that responded with 200 OK
		"select":      "url,final_url", // Need both to handle redirects
	}
	
	// Add pagination if limit > 0
	if limit > 0 {
		filters["offset"] = fmt.Sprintf("%d", offset)
		filters["limit"] = fmt.Sprintf("%d", limit)
	}

	var result []struct {
		URL      string  `json:"url"`
		FinalURL *string `json:"final_url"`
	}

	if err := r.client.Query("http_probes", filters, &result); err != nil {
		return nil, fmt.Errorf("failed to query seed URLs: %w", err)
	}

	urls := make([]string, 0, len(result))
	for _, row := range result {
		// Prefer final_url (after redirects) if available, otherwise use base url
		targetURL := row.URL
		if row.FinalURL != nil && *row.FinalURL != "" {
			targetURL = *row.FinalURL
		}
		if targetURL != "" {
			urls = append(urls, targetURL)
		}
	}

	r.logger.Info("Retrieved seed URLs: asset_id=%s, count=%d", assetID, len(urls))

	return urls, nil
}

// UpdateScanJobStatus updates the status of a scan job
func (r *Repository) UpdateScanJobStatus(scanJobID string, status string, metadata map[string]interface{}) error {
	updateData := map[string]interface{}{
		"status":     status,
		"updated_at": time.Now(),
	}

	if metadata != nil {
		updateData["metadata"] = metadata
	}

	filters := map[string]string{
		"id": fmt.Sprintf("eq.%s", scanJobID),
	}

	if err := r.client.Update("batch_scan_jobs", filters, updateData); err != nil {
		return fmt.Errorf("failed to update scan job status: %w", err)
	}

	r.logger.Info("Updated scan job status: scan_job_id=%s, status=%s", scanJobID, status)

	return nil
}


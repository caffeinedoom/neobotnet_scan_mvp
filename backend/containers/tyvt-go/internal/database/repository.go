package database

import (
	"encoding/json"
	"fmt"
	"net/url"
	"time"

	"github.com/sirupsen/logrus"
	"tyvt-go/internal/models"
)

// Repository provides database operations for TYVT module
type Repository struct {
	client *SupabaseClient
	logger *logrus.Logger
}

// NewRepository creates a new repository instance
func NewRepository(client *SupabaseClient, logger *logrus.Logger) *Repository {
	return &Repository{
		client: client,
		logger: logger,
	}
}

// GetSubdomainsForAsset fetches subdomains from the subdomains table for batch mode
func (r *Repository) GetSubdomainsForAsset(assetID string, offset, limit int) ([]string, error) {
	endpoint := fmt.Sprintf(
		"subdomains?asset_id=eq.%s&order=discovered_at.desc&offset=%d&limit=%d&select=subdomain",
		url.QueryEscape(assetID),
		offset,
		limit,
	)

	respBody, err := r.client.doQueryRequest(endpoint)
	if err != nil {
		return nil, fmt.Errorf("failed to fetch subdomains: %w", err)
	}

	var records []struct {
		Subdomain string `json:"subdomain"`
	}

	if err := json.Unmarshal(respBody, &records); err != nil {
		return nil, fmt.Errorf("failed to parse subdomains: %w", err)
	}

	subdomains := make([]string, len(records))
	for i, r := range records {
		subdomains[i] = r.Subdomain
	}

	return subdomains, nil
}

// GetHTTPProbesForAsset fetches unique subdomains from http_probes for batch mode
// This is useful because we want to query VT for domains that have responded to HTTP
func (r *Repository) GetHTTPProbesForAsset(assetID string, offset, limit int) ([]string, error) {
	endpoint := fmt.Sprintf(
		"http_probes?asset_id=eq.%s&order=discovered_at.desc&offset=%d&limit=%d&select=subdomain",
		url.QueryEscape(assetID),
		offset,
		limit,
	)

	respBody, err := r.client.doQueryRequest(endpoint)
	if err != nil {
		return nil, fmt.Errorf("failed to fetch http probes: %w", err)
	}

	var records []struct {
		Subdomain string `json:"subdomain"`
	}

	if err := json.Unmarshal(respBody, &records); err != nil {
		return nil, fmt.Errorf("failed to parse http probes: %w", err)
	}

	// Deduplicate subdomains
	seen := make(map[string]bool)
	var subdomains []string
	for _, rec := range records {
		if !seen[rec.Subdomain] {
			seen[rec.Subdomain] = true
			subdomains = append(subdomains, rec.Subdomain)
		}
	}

	return subdomains, nil
}

// BatchInsertDiscoveredURLs inserts multiple discovered URLs
func (r *Repository) BatchInsertDiscoveredURLs(urls []models.DiscoveredURL) error {
	if len(urls) == 0 {
		return nil
	}

	// Convert to database format
	records := make([]map[string]interface{}, len(urls))
	for i, u := range urls {
		records[i] = map[string]interface{}{
			"scan_job_id":   u.ScanJobID,
			"asset_id":      u.AssetID,
			"subdomain":     u.Subdomain,
			"url":           u.URL,
			"positives":     u.Positives,
			"total":         u.Total,
			"vt_scan_date":  u.ScanDate,
			"source":        "virustotal",
			"discovered_at": u.DiscoveredAt.Format(time.RFC3339),
		}
	}

	// Use upsert to handle duplicates (based on url + asset_id unique constraint)
	_, err := r.client.doRequest("POST", "vt_discovered_urls?on_conflict=url,asset_id", records)
	if err != nil {
		return fmt.Errorf("failed to insert discovered URLs: %w", err)
	}

	r.logger.Infof("💾 Stored %d discovered URLs", len(urls))
	return nil
}

// UpdateScanJobStatus updates the scan job status in the database
func (r *Repository) UpdateScanJobStatus(scanJobID, status string, metadata map[string]interface{}) error {
	endpoint := fmt.Sprintf("scan_jobs?id=eq.%s", url.QueryEscape(scanJobID))

	update := map[string]interface{}{
		"status": status,
	}

	// Add metadata fields
	for k, v := range metadata {
		update[k] = v
	}

	_, err := r.client.doRequest("PATCH", endpoint, update)
	if err != nil {
		// Log but don't fail - status updates are best-effort
		r.logger.Warnf("Failed to update scan job status: %v", err)
		return nil
	}

	return nil
}

// GetDiscoveredURLCount returns the count of discovered URLs for a scan job
func (r *Repository) GetDiscoveredURLCount(scanJobID string) (int, error) {
	endpoint := fmt.Sprintf(
		"vt_discovered_urls?scan_job_id=eq.%s&select=id",
		url.QueryEscape(scanJobID),
	)

	respBody, err := r.client.doQueryRequest(endpoint)
	if err != nil {
		return 0, err
	}

	var records []struct {
		ID string `json:"id"`
	}

	if err := json.Unmarshal(respBody, &records); err != nil {
		return 0, err
	}

	return len(records), nil
}


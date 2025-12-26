package main

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"log"
	"net/http"
	"os"
	"time"
)

// SupabaseClient handles database operations
type SupabaseClient struct {
	URL        string
	ServiceKey string
	HTTPClient *http.Client
}

// NewSupabaseClient creates a new Supabase client
func NewSupabaseClient() (*SupabaseClient, error) {
	url := os.Getenv("SUPABASE_URL")
	key := os.Getenv("SUPABASE_SERVICE_ROLE_KEY")

	if url == "" || key == "" {
		return nil, fmt.Errorf("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are required")
	}

	return &SupabaseClient{
		URL:        url,
		ServiceKey: key,
		HTTPClient: &http.Client{
			Timeout: 60 * time.Second,
		},
	}, nil
}

// HistoricalURLRecord represents a record for the historical_urls table
type HistoricalURLRecord struct {
	URL              string            `json:"url"`
	ParentDomain     string            `json:"parent_domain"`
	Source           string            `json:"source"`
	ArchiveTimestamp *string           `json:"archive_timestamp,omitempty"`
	AssetID          string            `json:"asset_id"`
	ScanJobID        string            `json:"scan_job_id,omitempty"`
	DiscoveredAt     string            `json:"discovered_at"`
	Metadata         map[string]string `json:"metadata,omitempty"`
}

// BulkInsertHistoricalURLs inserts multiple URLs with upsert handling
func (c *SupabaseClient) BulkInsertHistoricalURLs(urls []DiscoveredURL) (*BulkInsertResult, error) {
	result := &BulkInsertResult{}

	if len(urls) == 0 {
		return result, nil
	}

	// Convert to database records
	records := make([]HistoricalURLRecord, 0, len(urls))
	for _, u := range urls {
		record := HistoricalURLRecord{
			URL:          u.URL,
			ParentDomain: u.ParentDomain,
			Source:       u.Source,
			AssetID:      u.AssetID,
			ScanJobID:    u.ScanJobID,
			DiscoveredAt: u.DiscoveredAt,
			Metadata:     u.Metadata,
		}
		records = append(records, record)
	}

	// Insert in batches of 500 to avoid payload limits
	batchSize := 500
	for i := 0; i < len(records); i += batchSize {
		end := i + batchSize
		if end > len(records) {
			end = len(records)
		}
		batch := records[i:end]

		inserted, updated, err := c.insertBatch(batch)
		if err != nil {
			log.Printf("⚠️  Batch insert error (batch %d): %v", i/batchSize+1, err)
			result.ErrorCount += len(batch)
			continue
		}

		result.InsertedCount += inserted
		result.UpdatedCount += updated
	}

	return result, nil
}

// insertBatch inserts a batch of records
func (c *SupabaseClient) insertBatch(records []HistoricalURLRecord) (int, int, error) {
	jsonData, err := json.Marshal(records)
	if err != nil {
		return 0, 0, fmt.Errorf("failed to marshal records: %w", err)
	}

	// Use upsert with conflict handling on (url, asset_id)
	req, err := http.NewRequest("POST",
		fmt.Sprintf("%s/rest/v1/historical_urls", c.URL),
		bytes.NewBuffer(jsonData))
	if err != nil {
		return 0, 0, fmt.Errorf("failed to create request: %w", err)
	}

	req.Header.Set("apikey", c.ServiceKey)
	req.Header.Set("Authorization", "Bearer "+c.ServiceKey)
	req.Header.Set("Content-Type", "application/json")
	// Use upsert: on conflict update discovered_at
	req.Header.Set("Prefer", "resolution=merge-duplicates,return=minimal")

	resp, err := c.HTTPClient.Do(req)
	if err != nil {
		return 0, 0, fmt.Errorf("request failed: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode == http.StatusCreated || resp.StatusCode == http.StatusOK {
		return len(records), 0, nil
	}

	// Read error response
	body, _ := io.ReadAll(resp.Body)
	return 0, 0, fmt.Errorf("insert failed with status %d: %s", resp.StatusCode, string(body))
}

// FetchApexDomains fetches active apex domains for an asset
func (c *SupabaseClient) FetchApexDomains(assetID string) ([]string, error) {
	url := fmt.Sprintf("%s/rest/v1/apex_domains?asset_id=eq.%s&is_active=eq.true&select=domain",
		c.URL, assetID)

	req, err := http.NewRequest("GET", url, nil)
	if err != nil {
		return nil, fmt.Errorf("failed to create request: %w", err)
	}

	req.Header.Set("apikey", c.ServiceKey)
	req.Header.Set("Authorization", "Bearer "+c.ServiceKey)

	resp, err := c.HTTPClient.Do(req)
	if err != nil {
		return nil, fmt.Errorf("request failed: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		body, _ := io.ReadAll(resp.Body)
		return nil, fmt.Errorf("fetch failed with status %d: %s", resp.StatusCode, string(body))
	}

	var records []struct {
		Domain string `json:"domain"`
	}

	if err := json.NewDecoder(resp.Body).Decode(&records); err != nil {
		return nil, fmt.Errorf("failed to decode response: %w", err)
	}

	domains := make([]string, len(records))
	for i, r := range records {
		domains[i] = r.Domain
	}

	return domains, nil
}

// UpdateBatchScanStatus updates the status of a batch scan job
func (c *SupabaseClient) UpdateBatchScanStatus(batchID, status string, metadata map[string]interface{}) error {
	payload := map[string]interface{}{
		"status": status,
	}

	// Merge metadata if provided
	if metadata != nil {
		for k, v := range metadata {
			payload[k] = v
		}
	}

	// Add completed_at if status is completed or failed
	if status == "completed" || status == "failed" {
		payload["completed_at"] = time.Now().UTC().Format(time.RFC3339)
	}

	jsonData, err := json.Marshal(payload)
	if err != nil {
		return fmt.Errorf("failed to marshal payload: %w", err)
	}

	url := fmt.Sprintf("%s/rest/v1/batch_scan_jobs?id=eq.%s", c.URL, batchID)

	req, err := http.NewRequest("PATCH", url, bytes.NewBuffer(jsonData))
	if err != nil {
		return fmt.Errorf("failed to create request: %w", err)
	}

	req.Header.Set("apikey", c.ServiceKey)
	req.Header.Set("Authorization", "Bearer "+c.ServiceKey)
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Prefer", "return=minimal")

	resp, err := c.HTTPClient.Do(req)
	if err != nil {
		return fmt.Errorf("request failed: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK && resp.StatusCode != http.StatusNoContent {
		body, _ := io.ReadAll(resp.Body)
		return fmt.Errorf("update failed with status %d: %s", resp.StatusCode, string(body))
	}

	return nil
}

// UpdateScanJobStatus updates the status of an asset scan job
func (c *SupabaseClient) UpdateScanJobStatus(scanJobID, status string, metadata map[string]interface{}) error {
	payload := map[string]interface{}{
		"status": status,
	}

	if metadata != nil {
		payload["metadata"] = metadata
	}

	if status == "completed" || status == "failed" {
		payload["completed_at"] = time.Now().UTC().Format(time.RFC3339)
	}

	jsonData, err := json.Marshal(payload)
	if err != nil {
		return fmt.Errorf("failed to marshal payload: %w", err)
	}

	url := fmt.Sprintf("%s/rest/v1/asset_scan_jobs?id=eq.%s", c.URL, scanJobID)

	req, err := http.NewRequest("PATCH", url, bytes.NewBuffer(jsonData))
	if err != nil {
		return fmt.Errorf("failed to create request: %w", err)
	}

	req.Header.Set("apikey", c.ServiceKey)
	req.Header.Set("Authorization", "Bearer "+c.ServiceKey)
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Prefer", "return=minimal")

	resp, err := c.HTTPClient.Do(req)
	if err != nil {
		return fmt.Errorf("request failed: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK && resp.StatusCode != http.StatusNoContent {
		body, _ := io.ReadAll(resp.Body)
		return fmt.Errorf("update failed with status %d: %s", resp.StatusCode, string(body))
	}

	return nil
}


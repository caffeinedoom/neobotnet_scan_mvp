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
	url        string
	serviceKey string
	httpClient *http.Client
}

// NewSupabaseClient creates a new Supabase client from environment variables
func NewSupabaseClient() (*SupabaseClient, error) {
	url := os.Getenv("SUPABASE_URL")
	serviceKey := os.Getenv("SUPABASE_SERVICE_ROLE_KEY")

	if url == "" {
		return nil, fmt.Errorf("SUPABASE_URL environment variable is required")
	}
	if serviceKey == "" {
		return nil, fmt.Errorf("SUPABASE_SERVICE_ROLE_KEY environment variable is required")
	}

	return &SupabaseClient{
		url:        url,
		serviceKey: serviceKey,
		httpClient: &http.Client{Timeout: 60 * time.Second},
	}, nil
}

// SupabaseError represents detailed error response from Supabase
type SupabaseError struct {
	Code    string `json:"code"`
	Details string `json:"details"`
	Hint    string `json:"hint"`
	Message string `json:"message"`
}

// Error implements the error interface
func (e SupabaseError) Error() string {
	return fmt.Sprintf("Supabase error [%s]: %s (Details: %s, Hint: %s)",
		e.Code, e.Message, e.Details, e.Hint)
}

// GetURLByHash retrieves a URL record by asset_id and url_hash
func (sc *SupabaseClient) GetURLByHash(assetID, urlHash string) (*URLRecord, error) {
	url := fmt.Sprintf("%s/rest/v1/urls?asset_id=eq.%s&url_hash=eq.%s&select=*",
		sc.url, assetID, urlHash)

	req, err := http.NewRequest("GET", url, nil)
	if err != nil {
		return nil, fmt.Errorf("failed to create request: %w", err)
	}

	req.Header.Set("apikey", sc.serviceKey)
	req.Header.Set("Authorization", fmt.Sprintf("Bearer %s", sc.serviceKey))
	req.Header.Set("Content-Type", "application/json")

	resp, err := sc.httpClient.Do(req)
	if err != nil {
		return nil, fmt.Errorf("failed to execute request: %w", err)
	}
	defer resp.Body.Close()

	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, fmt.Errorf("failed to read response: %w", err)
	}

	if resp.StatusCode != http.StatusOK {
		var supabaseErr SupabaseError
		if err := json.Unmarshal(body, &supabaseErr); err != nil {
			return nil, fmt.Errorf("HTTP %d: %s", resp.StatusCode, string(body))
		}
		return nil, supabaseErr
	}

	var records []URLRecord
	if err := json.Unmarshal(body, &records); err != nil {
		return nil, fmt.Errorf("failed to parse response: %w", err)
	}

	if len(records) == 0 {
		return nil, nil // Not found
	}

	return &records[0], nil
}

// InsertURL inserts a new URL record
func (sc *SupabaseClient) InsertURL(record *URLRecord) error {
	url := fmt.Sprintf("%s/rest/v1/urls", sc.url)

	jsonData, err := json.Marshal(record)
	if err != nil {
		return fmt.Errorf("failed to marshal record: %w", err)
	}

	req, err := http.NewRequest("POST", url, bytes.NewBuffer(jsonData))
	if err != nil {
		return fmt.Errorf("failed to create request: %w", err)
	}

	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Authorization", fmt.Sprintf("Bearer %s", sc.serviceKey))
	req.Header.Set("apikey", sc.serviceKey)
	req.Header.Set("Prefer", "return=minimal")

	resp, err := sc.httpClient.Do(req)
	if err != nil {
		return fmt.Errorf("failed to execute request: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		body, _ := io.ReadAll(resp.Body)
		var supabaseErr SupabaseError
		if err := json.Unmarshal(body, &supabaseErr); err != nil {
			return fmt.Errorf("HTTP %d: %s", resp.StatusCode, string(body))
		}
		return supabaseErr
	}

	return nil
}

// UpdateURLResolution updates an existing URL record with resolution data
func (sc *SupabaseClient) UpdateURLResolution(assetID, urlHash string, result *ProbeResult, newSource *string) error {
	url := fmt.Sprintf("%s/rest/v1/urls?asset_id=eq.%s&url_hash=eq.%s",
		sc.url, assetID, urlHash)

	now := time.Now().UTC()

	// Build update payload
	updateData := map[string]interface{}{
		"resolved_at":      now.Format(time.RFC3339),
		"is_alive":         result.IsAlive,
		"status_code":      result.StatusCode,
		"response_time_ms": result.ResponseTimeMs,
		"updated_at":       now.Format(time.RFC3339),
	}

	// Add optional fields if present
	if result.ContentType != "" {
		updateData["content_type"] = result.ContentType
	}
	if result.ContentLength > 0 {
		updateData["content_length"] = result.ContentLength
	}
	if result.Title != "" {
		updateData["title"] = result.Title
	}
	if result.FinalURL != "" {
		updateData["final_url"] = result.FinalURL
	}
	if result.Webserver != "" {
		updateData["webserver"] = result.Webserver
	}
	if len(result.Technologies) > 0 {
		updateData["technologies"] = result.Technologies
	}
	if len(result.RedirectChain) > 0 {
		updateData["redirect_chain"] = result.RedirectChain
	}

	jsonData, err := json.Marshal(updateData)
	if err != nil {
		return fmt.Errorf("failed to marshal update data: %w", err)
	}

	req, err := http.NewRequest("PATCH", url, bytes.NewBuffer(jsonData))
	if err != nil {
		return fmt.Errorf("failed to create request: %w", err)
	}

	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Authorization", fmt.Sprintf("Bearer %s", sc.serviceKey))
	req.Header.Set("apikey", sc.serviceKey)
	req.Header.Set("Prefer", "return=minimal")

	resp, err := sc.httpClient.Do(req)
	if err != nil {
		return fmt.Errorf("failed to execute request: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		body, _ := io.ReadAll(resp.Body)
		var supabaseErr SupabaseError
		if err := json.Unmarshal(body, &supabaseErr); err != nil {
			return fmt.Errorf("HTTP %d: %s", resp.StatusCode, string(body))
		}
		return supabaseErr
	}

	return nil
}

// AddSourceToURL adds a new source to an existing URL's sources array
// Uses PostgreSQL jsonb_insert or array append via RPC
func (sc *SupabaseClient) AddSourceToURL(assetID, urlHash, newSource string) error {
	// First get the existing record
	existing, err := sc.GetURLByHash(assetID, urlHash)
	if err != nil {
		return fmt.Errorf("failed to get existing URL: %w", err)
	}
	if existing == nil {
		return fmt.Errorf("URL not found")
	}

	// Check if source already exists
	for _, s := range existing.Sources {
		if s == newSource {
			return nil // Already exists, no update needed
		}
	}

	// Add new source
	updatedSources := append(existing.Sources, newSource)

	url := fmt.Sprintf("%s/rest/v1/urls?asset_id=eq.%s&url_hash=eq.%s",
		sc.url, assetID, urlHash)

	updateData := map[string]interface{}{
		"sources":    updatedSources,
		"updated_at": time.Now().UTC().Format(time.RFC3339),
	}

	jsonData, err := json.Marshal(updateData)
	if err != nil {
		return fmt.Errorf("failed to marshal update data: %w", err)
	}

	req, err := http.NewRequest("PATCH", url, bytes.NewBuffer(jsonData))
	if err != nil {
		return fmt.Errorf("failed to create request: %w", err)
	}

	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Authorization", fmt.Sprintf("Bearer %s", sc.serviceKey))
	req.Header.Set("apikey", sc.serviceKey)
	req.Header.Set("Prefer", "return=minimal")

	resp, err := sc.httpClient.Do(req)
	if err != nil {
		return fmt.Errorf("failed to execute request: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		body, _ := io.ReadAll(resp.Body)
		return fmt.Errorf("HTTP %d: %s", resp.StatusCode, string(body))
	}

	log.Printf("    📝 Added source '%s' to URL", newSource)
	return nil
}

// UpdateBatchScanStatus updates the status of a batch scan job
func (sc *SupabaseClient) UpdateBatchScanStatus(batchID, status string, metadata map[string]interface{}) error {
	if batchID == "" {
		return fmt.Errorf("batch_id is required")
	}

	url := fmt.Sprintf("%s/rest/v1/batch_scan_jobs?id=eq.%s", sc.url, batchID)

	// Prepare update payload
	updateData := map[string]interface{}{
		"status":     status,
		"updated_at": time.Now().UTC().Format(time.RFC3339),
	}

	// Add completion timestamp if completed
	if status == "completed" || status == "failed" {
		updateData["completed_at"] = time.Now().UTC().Format(time.RFC3339)
	}

	// Merge metadata if provided
	if metadata != nil {
		for key, value := range metadata {
			updateData[key] = value
		}
	}

	jsonData, err := json.Marshal(updateData)
	if err != nil {
		return fmt.Errorf("failed to marshal update data: %v", err)
	}

	req, err := http.NewRequest("PATCH", url, bytes.NewBuffer(jsonData))
	if err != nil {
		return fmt.Errorf("failed to create HTTP request: %v", err)
	}

	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Authorization", fmt.Sprintf("Bearer %s", sc.serviceKey))
	req.Header.Set("apikey", sc.serviceKey)
	req.Header.Set("Prefer", "return=minimal")

	resp, err := sc.httpClient.Do(req)
	if err != nil {
		return fmt.Errorf("failed to send HTTP request: %v", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		bodyBytes, _ := io.ReadAll(resp.Body)
		var supabaseErr SupabaseError
		if err := json.Unmarshal(bodyBytes, &supabaseErr); err != nil {
			return fmt.Errorf("HTTP %d: %s", resp.StatusCode, string(bodyBytes))
		}
		return supabaseErr
	}

	log.Printf("✅ Updated batch scan %s to status: %s", batchID, status)
	return nil
}


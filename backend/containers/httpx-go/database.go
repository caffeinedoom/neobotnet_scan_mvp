package main

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
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
		httpClient: &http.Client{Timeout: 60 * time.Second}, // Longer timeout for batch operations
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

// DNSRecord represents a DNS record for database storage
type DNSRecord struct {
	Subdomain    string `json:"subdomain"`
	ParentDomain string `json:"parent_domain"`
	RecordType   string `json:"record_type"`
	RecordValue  string `json:"record_value"`
	TTL          *int   `json:"ttl,omitempty"`
	Priority     *int   `json:"priority,omitempty"` // For MX records
	ResolvedAt   string `json:"resolved_at"`
	ScanJobID    string `json:"scan_job_id,omitempty"`
	BatchScanID  string `json:"batch_scan_id,omitempty"`
	AssetID      string `json:"asset_id,omitempty"`
}

// BulkInsertResult represents the result of bulk insert operation
type BulkInsertResult struct {
	InsertedCount int `json:"inserted_count"`
	UpdatedCount  int `json:"updated_count"`
	SkippedCount  int `json:"skipped_count"`
	ErrorCount    int `json:"error_count"`
}

// BulkInsertDNSRecords inserts multiple DNS records using PostgreSQL function
func (sc *SupabaseClient) BulkInsertDNSRecords(records []DNSRecord) (*BulkInsertResult, error) {
	if len(records) == 0 {
		return &BulkInsertResult{}, nil
	}

	// Call the PostgreSQL function bulk_insert_dns_records
	url := fmt.Sprintf("%s/rest/v1/rpc/bulk_insert_dns_records", sc.url)

	// Prepare the payload
	payload := map[string]interface{}{
		"records": records,
	}

	jsonData, err := json.Marshal(payload)
	if err != nil {
		return nil, fmt.Errorf("failed to marshal DNS records: %v", err)
	}

	// Log batch information
	fmt.Printf("📤 Inserting %d DNS records (payload size: %d bytes)\n",
		len(records), len(jsonData))

	// Log sample record for debugging (first 2 records)
	if len(records) > 0 {
		sampleCount := 2
		if len(records) < sampleCount {
			sampleCount = len(records)
		}
		if sampleData, err := json.MarshalIndent(records[:sampleCount], "", "  "); err == nil {
			fmt.Printf("🔍 Sample records (%d of %d):\n%s\n", sampleCount, len(records), string(sampleData))
		}
	}

	// Create HTTP request
	req, err := http.NewRequest("POST", url, bytes.NewBuffer(jsonData))
	if err != nil {
		return nil, fmt.Errorf("failed to create HTTP request: %v", err)
	}

	// Set headers
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Authorization", fmt.Sprintf("Bearer %s", sc.serviceKey))
	req.Header.Set("apikey", sc.serviceKey)
	req.Header.Set("Prefer", "return=representation")

	// Send request
	fmt.Printf("🌐 Sending POST request to: %s\n", url)
	resp, err := sc.httpClient.Do(req)
	if err != nil {
		return nil, fmt.Errorf("failed to send HTTP request: %v", err)
	}
	defer resp.Body.Close()

	// Read response body
	bodyBytes, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, fmt.Errorf("failed to read response body: %v", err)
	}

	// Check for HTTP errors
	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		var supabaseErr SupabaseError
		if err := json.Unmarshal(bodyBytes, &supabaseErr); err != nil {
			return nil, fmt.Errorf("HTTP %d: %s", resp.StatusCode, string(bodyBytes))
		}
		return nil, supabaseErr
	}

	// Parse the result
	// The function returns a table with one row: (inserted_count, updated_count, skipped_count, error_count)
	var result []BulkInsertResult
	if err := json.Unmarshal(bodyBytes, &result); err != nil {
		return nil, fmt.Errorf("failed to parse response: %v (body: %s)", err, string(bodyBytes))
	}

	if len(result) == 0 {
		return nil, fmt.Errorf("unexpected empty result from bulk_insert_dns_records")
	}

	fmt.Printf("✅ Bulk insert completed: %d inserted, %d updated, %d skipped, %d errors\n",
		result[0].InsertedCount, result[0].UpdatedCount, result[0].SkippedCount, result[0].ErrorCount)

	return &result[0], nil
}

// SubdomainRecord represents a subdomain to be inserted
type SubdomainRecord struct {
	Subdomain    string `json:"subdomain"`
	ParentDomain string `json:"parent_domain"`
	ScanJobID    string `json:"scan_job_id"`
	AssetID      string `json:"asset_id"` // ✅ FIX: Asset ID (required by database schema)
	SourceModule string `json:"source_module"`
	DiscoveredAt string `json:"discovered_at"`
}

// SubdomainInsertResult represents the result of subdomain insert operation
type SubdomainInsertResult struct {
	InsertedCount int `json:"inserted"`
	SkippedCount  int `json:"skipped"`
}

// BulkInsertSubdomains inserts multiple subdomain records using PostgreSQL function
func (sc *SupabaseClient) BulkInsertSubdomains(records []SubdomainRecord) (*SubdomainInsertResult, error) {
	if len(records) == 0 {
		return &SubdomainInsertResult{}, nil
	}

	// Call the PostgreSQL function bulk_insert_subdomains
	url := fmt.Sprintf("%s/rest/v1/rpc/bulk_insert_subdomains", sc.url)

	// Prepare the payload
	payload := map[string]interface{}{
		"records": records,
	}

	jsonData, err := json.Marshal(payload)
	if err != nil {
		return nil, fmt.Errorf("failed to marshal subdomain records: %v", err)
	}

	fmt.Printf("📤 Inserting %d subdomain records (payload size: %d bytes)\n",
		len(records), len(jsonData))

	// Create request
	req, err := http.NewRequest("POST", url, bytes.NewBuffer(jsonData))
	if err != nil {
		return nil, fmt.Errorf("failed to create request: %v", err)
	}

	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("apikey", sc.serviceKey)
	req.Header.Set("Authorization", fmt.Sprintf("Bearer %s", sc.serviceKey))
	req.Header.Set("Prefer", "return=representation")

	fmt.Printf("🌐 Sending POST request to: %s\n", url)

	// Execute request
	client := &http.Client{Timeout: 30 * time.Second}
	resp, err := client.Do(req)
	if err != nil {
		return nil, fmt.Errorf("request failed: %v", err)
	}
	defer resp.Body.Close()

	// Read response
	bodyBytes, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, fmt.Errorf("failed to read response body: %v", err)
	}

	// Check for HTTP errors
	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		var supabaseErr SupabaseError
		if err := json.Unmarshal(bodyBytes, &supabaseErr); err != nil {
			return nil, fmt.Errorf("HTTP %d: %s", resp.StatusCode, string(bodyBytes))
		}
		return nil, supabaseErr
	}

	// Parse the result
	var result []SubdomainInsertResult
	if err := json.Unmarshal(bodyBytes, &result); err != nil {
		return nil, fmt.Errorf("failed to parse response: %v (body: %s)", err, string(bodyBytes))
	}

	if len(result) == 0 {
		return nil, fmt.Errorf("unexpected empty result from bulk_insert_subdomains")
	}

	fmt.Printf("✅ Bulk subdomain insert completed: %d inserted, %d skipped\n",
		result[0].InsertedCount, result[0].SkippedCount)

	return &result[0], nil
}

// UpdateScanJobStatus updates the status of a scan job
func (sc *SupabaseClient) UpdateScanJobStatus(jobID, status string, metadata map[string]interface{}) error {
	if jobID == "" {
		return fmt.Errorf("job_id is required")
	}

	url := fmt.Sprintf("%s/rest/v1/asset_scan_jobs?id=eq.%s", sc.url, jobID)

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

	// Create HTTP request
	req, err := http.NewRequest("PATCH", url, bytes.NewBuffer(jsonData))
	if err != nil {
		return fmt.Errorf("failed to create HTTP request: %v", err)
	}

	// Set headers
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Authorization", fmt.Sprintf("Bearer %s", sc.serviceKey))
	req.Header.Set("apikey", sc.serviceKey)
	req.Header.Set("Prefer", "return=minimal")

	// Send request
	resp, err := sc.httpClient.Do(req)
	if err != nil {
		return fmt.Errorf("failed to send HTTP request: %v", err)
	}
	defer resp.Body.Close()

	// Check for HTTP errors
	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		bodyBytes, _ := io.ReadAll(resp.Body)
		var supabaseErr SupabaseError
		if err := json.Unmarshal(bodyBytes, &supabaseErr); err != nil {
			return fmt.Errorf("HTTP %d: %s", resp.StatusCode, string(bodyBytes))
		}
		return supabaseErr
	}

	fmt.Printf("✅ Updated scan job %s to status: %s\n", jobID, status)
	return nil
}

// UpdateBatchScanStatus updates the status of a batch scan job with retry logic
func (sc *SupabaseClient) UpdateBatchScanStatus(batchID, status string, metadata map[string]interface{}) error {
	return sc.UpdateBatchScanStatusWithRetry(batchID, status, metadata, 3) // 3 retries by default
}

// UpdateBatchScanStatusWithRetry updates the status of a batch scan job with configurable retries
func (sc *SupabaseClient) UpdateBatchScanStatusWithRetry(batchID, status string, metadata map[string]interface{}, maxRetries int) error {
	if batchID == "" {
		return fmt.Errorf("batch_id is required")
	}

	var lastErr error
	for attempt := 1; attempt <= maxRetries; attempt++ {
		err := sc.updateBatchScanStatusOnce(batchID, status, metadata)
		if err == nil {
			return nil
		}
		lastErr = err
		fmt.Printf("⚠️  Status update failed (attempt %d/%d): %v\n", attempt, maxRetries, err)
		if attempt < maxRetries {
			// Exponential backoff: 1s, 2s, 4s...
			sleepDuration := time.Duration(1<<uint(attempt-1)) * time.Second
			fmt.Printf("   Retrying in %v...\n", sleepDuration)
			time.Sleep(sleepDuration)
		}
	}
	return fmt.Errorf("status update failed after %d retries: %w", maxRetries, lastErr)
}

// updateBatchScanStatusOnce performs a single status update attempt
func (sc *SupabaseClient) updateBatchScanStatusOnce(batchID, status string, metadata map[string]interface{}) error {
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

	// Create HTTP request
	req, err := http.NewRequest("PATCH", url, bytes.NewBuffer(jsonData))
	if err != nil {
		return fmt.Errorf("failed to create HTTP request: %v", err)
	}

	// Set headers
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Authorization", fmt.Sprintf("Bearer %s", sc.serviceKey))
	req.Header.Set("apikey", sc.serviceKey)
	req.Header.Set("Prefer", "return=minimal")

	// Send request
	resp, err := sc.httpClient.Do(req)
	if err != nil {
		return fmt.Errorf("failed to send HTTP request: %v", err)
	}
	defer resp.Body.Close()

	// Check for HTTP errors
	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		bodyBytes, _ := io.ReadAll(resp.Body)
		var supabaseErr SupabaseError
		if err := json.Unmarshal(bodyBytes, &supabaseErr); err != nil {
			return fmt.Errorf("HTTP %d: %s", resp.StatusCode, string(bodyBytes))
		}
		return supabaseErr
	}

	fmt.Printf("✅ Updated batch scan %s to status: %s\n", batchID, status)
	return nil
}

// GetSubdomainsForAsset fetches discovered subdomains for an asset from the database with pagination
// This enables DNSX to run independently on previously discovered subdomains
// offset: Starting index for pagination (0-based)
// limit: Maximum number of subdomains to fetch (0 = fetch all)
func (sc *SupabaseClient) GetSubdomainsForAsset(assetID string, offset int, limit int) ([]string, error) {
	fmt.Printf("📥 Fetching subdomains for asset: %s (offset=%d, limit=%d)\n", assetID, offset, limit)

	// Query subdomains table with pagination
	// PostgREST syntax: limit=X&offset=Y
	var url string
	if limit > 0 {
		url = fmt.Sprintf("%s/rest/v1/subdomains?asset_id=eq.%s&select=subdomain&limit=%d&offset=%d",
			sc.url, assetID, limit, offset)
	} else {
		// No limit specified, fetch all (backward compatibility)
		url = fmt.Sprintf("%s/rest/v1/subdomains?asset_id=eq.%s&select=subdomain",
			sc.url, assetID)
	}

	req, err := http.NewRequest("GET", url, nil)
	if err != nil {
		return nil, fmt.Errorf("failed to create request: %w", err)
	}

	// Set headers for Supabase authentication
	req.Header.Set("apikey", sc.serviceKey)
	req.Header.Set("Authorization", fmt.Sprintf("Bearer %s", sc.serviceKey))
	req.Header.Set("Content-Type", "application/json")

	// Execute request
	resp, err := sc.httpClient.Do(req)
	if err != nil {
		return nil, fmt.Errorf("failed to fetch subdomains: %w", err)
	}
	defer resp.Body.Close()

	// Read response body
	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, fmt.Errorf("failed to read response: %w", err)
	}

	// Check for HTTP errors
	if resp.StatusCode != http.StatusOK {
		var supabaseErr SupabaseError
		if err := json.Unmarshal(body, &supabaseErr); err != nil {
			return nil, fmt.Errorf("HTTP %d: %s", resp.StatusCode, string(body))
		}
		return nil, supabaseErr
	}

	// Parse JSON response
	var results []struct {
		Subdomain string `json:"subdomain"`
	}

	if err := json.Unmarshal(body, &results); err != nil {
		return nil, fmt.Errorf("failed to parse subdomains: %w", err)
	}

	// Extract subdomain strings
	subdomains := make([]string, len(results))
	for i, r := range results {
		subdomains[i] = r.Subdomain
	}

	if limit > 0 {
		fmt.Printf("✅ Fetched %d subdomains from database (batch: %d-%d)\n",
			len(subdomains), offset, offset+len(subdomains))
	} else {
		fmt.Printf("✅ Fetched %d subdomains from database (all)\n", len(subdomains))
	}
	return subdomains, nil
}

// HTTPProbeInsertResult represents the result of HTTP probe bulk insert operation
type HTTPProbeInsertResult struct {
	InsertedCount int `json:"inserted_count"`
	SkippedCount  int `json:"skipped_count"`
	ErrorCount    int `json:"error_count"`
}

// BulkInsertHTTPProbes inserts multiple HTTP probe records directly into http_probes table
func (sc *SupabaseClient) BulkInsertHTTPProbes(probes []HTTPProbe) (*HTTPProbeInsertResult, error) {
	if len(probes) == 0 {
		return &HTTPProbeInsertResult{}, nil
	}

	// Insert directly into http_probes table
	url := fmt.Sprintf("%s/rest/v1/http_probes", sc.url)

	// Marshal probes to JSON
	jsonData, err := json.Marshal(probes)
	if err != nil {
		return nil, fmt.Errorf("failed to marshal HTTP probes: %v", err)
	}

	// Log batch information
	fmt.Printf("📤 Inserting %d HTTP probes (payload size: %d bytes)\n",
		len(probes), len(jsonData))

	// Log sample probe for debugging (first probe only)
	if len(probes) > 0 {
		if sampleData, err := json.MarshalIndent(probes[0], "", "  "); err == nil {
			fmt.Printf("🔍 Sample probe (1 of %d):\n%s\n", len(probes), string(sampleData))
		}
	}

	// Create HTTP request
	req, err := http.NewRequest("POST", url, bytes.NewBuffer(jsonData))
	if err != nil {
		return nil, fmt.Errorf("failed to create HTTP request: %v", err)
	}

	// Set headers
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Authorization", fmt.Sprintf("Bearer %s", sc.serviceKey))
	req.Header.Set("apikey", sc.serviceKey)
	req.Header.Set("Prefer", "return=minimal")

	// Send request
	fmt.Printf("🌐 Sending POST request to: %s\n", url)
	resp, err := sc.httpClient.Do(req)
	if err != nil {
		return nil, fmt.Errorf("failed to send HTTP request: %v", err)
	}
	defer resp.Body.Close()

	// Read response body
	bodyBytes, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, fmt.Errorf("failed to read response body: %v", err)
	}

	// Check for HTTP errors
	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		var supabaseErr SupabaseError
		if err := json.Unmarshal(bodyBytes, &supabaseErr); err != nil {
			return nil, fmt.Errorf("HTTP %d: %s", resp.StatusCode, string(bodyBytes))
		}
		return nil, supabaseErr
	}

	// Success - count inserted records
	result := &HTTPProbeInsertResult{
		InsertedCount: len(probes),
		SkippedCount:  0,
		ErrorCount:    0,
	}

	fmt.Printf("✅ Bulk insert completed: %d HTTP probes inserted\n", result.InsertedCount)

	return result, nil
}

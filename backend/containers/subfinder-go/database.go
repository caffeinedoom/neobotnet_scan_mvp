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

// BatchInsertSubdomains inserts multiple subdomain records into Supabase
func (sc *SupabaseClient) BatchInsertSubdomains(records []map[string]interface{}) error {
	if len(records) == 0 {
		return nil
	}

	url := fmt.Sprintf("%s/rest/v1/subdomains", sc.url)

	// Marshal records to JSON
	jsonData, err := json.Marshal(records)
	if err != nil {
		return fmt.Errorf("failed to marshal subdomain records: %v", err)
	}

	// Log batch information
	fmt.Printf("📤 Inserting %d subdomain records (payload size: %d bytes)\n",
		len(records), len(jsonData))

	// Log sample record for debugging
	if len(records) > 0 {
		if sampleRecord, err := json.MarshalIndent(records[0], "", "  "); err == nil {
			fmt.Printf("🔍 Sample record:\n%s\n", string(sampleRecord))
		}
	}

	// Create HTTP request
	req, err := http.NewRequest("POST", url, bytes.NewBuffer(jsonData))
	if err != nil {
		return fmt.Errorf("failed to create HTTP request: %v", err)
	}

	// Set headers
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Authorization", fmt.Sprintf("Bearer %s", sc.serviceKey))
	req.Header.Set("apikey", sc.serviceKey)
	// MIGRATION 003 (2025-10-07): Handle duplicates gracefully with global dedup constraint
	// resolution=ignore-duplicates: Silently ignore records that violate unique constraint
	// This is critical after changing constraint to UNIQUE(parent_domain, subdomain)
	req.Header.Set("Prefer", "resolution=ignore-duplicates,return=minimal")

	// Send request
	fmt.Printf("🌐 Sending POST request to: %s\n", url)
	resp, err := sc.httpClient.Do(req)
	if err != nil {
		return fmt.Errorf("failed to send HTTP request: %v", err)
	}
	defer resp.Body.Close()

	// Read response body
	responseBody, err := io.ReadAll(resp.Body)
	if err != nil {
		fmt.Printf("⚠️  Failed to read response body: %v\n", err)
		responseBody = []byte("Failed to read response")
	}

	fmt.Printf("📥 Database response: HTTP %d (body size: %d bytes)\n",
		resp.StatusCode, len(responseBody))

	// Check response status
	if resp.StatusCode >= 200 && resp.StatusCode < 300 {
		// Note: With resolution=ignore-duplicates, Supabase returns 201 even if some records
		// were skipped due to conflicts. This is expected behavior with global dedup.
		fmt.Printf("✅ Successfully processed %d subdomain records (duplicates auto-ignored)\n", len(records))
		return nil
	}

	// Handle error response
	fmt.Printf("❌ Database error response:\n%s\n", string(responseBody))

	// Try to parse Supabase error format
	var supabaseErr SupabaseError
	if jsonErr := json.Unmarshal(responseBody, &supabaseErr); jsonErr == nil {
		return fmt.Errorf("database insertion failed: %v", supabaseErr)
	}

	// Fallback to generic error
	return fmt.Errorf("database insertion failed: HTTP %d - %s",
		resp.StatusCode, string(responseBody))
}

// GetAssetDomains retrieves all active apex domains for an asset
func (sc *SupabaseClient) GetAssetDomains(assetID string) ([]string, error) {
	url := fmt.Sprintf("%s/rest/v1/apex_domains?asset_id=eq.%s&is_active=eq.true&select=domain",
		sc.url, assetID)

	req, err := http.NewRequest("GET", url, nil)
	if err != nil {
		return nil, fmt.Errorf("failed to create HTTP request: %v", err)
	}

	// Set headers
	req.Header.Set("Authorization", fmt.Sprintf("Bearer %s", sc.serviceKey))
	req.Header.Set("apikey", sc.serviceKey)

	// Send request
	resp, err := sc.httpClient.Do(req)
	if err != nil {
		return nil, fmt.Errorf("failed to send HTTP request: %v", err)
	}
	defer resp.Body.Close()

	// Read response
	responseBody, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, fmt.Errorf("failed to read response body: %v", err)
	}

	if resp.StatusCode != 200 {
		return nil, fmt.Errorf("failed to get domains: HTTP %d - %s",
			resp.StatusCode, string(responseBody))
	}

	// Parse response
	var domainRecords []struct {
		Domain string `json:"domain"`
	}

	if err := json.Unmarshal(responseBody, &domainRecords); err != nil {
		return nil, fmt.Errorf("failed to parse domain records: %v", err)
	}

	// Extract domain strings
	var domains []string
	for _, record := range domainRecords {
		domains = append(domains, record.Domain)
	}

	return domains, nil
}

// UpdateScanJobStatus updates the status of a scan job
func (sc *SupabaseClient) UpdateScanJobStatus(jobID, status string, metadata map[string]interface{}) error {
	url := fmt.Sprintf("%s/rest/v1/scan_jobs?id=eq.%s", sc.url, jobID)

	// Prepare update data
	updateData := map[string]interface{}{
		"status":     status,
		"updated_at": time.Now().UTC().Format(time.RFC3339),
	}

	// Add metadata if provided
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

	// Check response
	if resp.StatusCode >= 200 && resp.StatusCode < 300 {
		fmt.Printf("✅ Updated scan job %s status to: %s\n", jobID, status)
		return nil
	}

	// Read error response
	responseBody, _ := io.ReadAll(resp.Body)
	return fmt.Errorf("failed to update scan job status: HTTP %d - %s",
		resp.StatusCode, string(responseBody))
}

// UpdateBatchScanJob updates a batch scan job record
func (c *SupabaseClient) UpdateBatchScanJob(batchID string, updates map[string]interface{}) error {
	// Convert updates to JSON
	updateData, err := json.Marshal(updates)
	if err != nil {
		return fmt.Errorf("failed to marshal batch updates: %v", err)
	}

	// Make HTTP PATCH request
	url := fmt.Sprintf("%s/rest/v1/batch_scan_jobs?id=eq.%s", c.url, batchID)
	req, err := http.NewRequest("PATCH", url, bytes.NewBuffer(updateData))
	if err != nil {
		return fmt.Errorf("failed to create batch update request: %v", err)
	}

	req.Header.Set("Authorization", "Bearer "+c.serviceKey)
	req.Header.Set("apikey", c.serviceKey) // 🔧 FIX: Add missing apikey header for Supabase authentication
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Prefer", "return=minimal")

	resp, err := c.httpClient.Do(req)
	if err != nil {
		return fmt.Errorf("failed to execute batch update request: %v", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode >= 200 && resp.StatusCode < 300 {
		fmt.Printf("✅ Updated batch scan job %s\n", batchID)
		return nil
	}

	// Read error response
	responseBody, _ := io.ReadAll(resp.Body)
	return fmt.Errorf("failed to update batch scan job: HTTP %d - %s",
		resp.StatusCode, string(responseBody))
}

// UpdateBatchDomainAssignment updates a batch domain assignment record
func (c *SupabaseClient) UpdateBatchDomainAssignment(batchID string, domain string, updates map[string]interface{}) error {
	// Convert updates to JSON
	updateData, err := json.Marshal(updates)
	if err != nil {
		return fmt.Errorf("failed to marshal domain assignment updates: %v", err)
	}

	// Make HTTP PATCH request - filter by both batch_id and domain
	url := fmt.Sprintf("%s/rest/v1/batch_domain_assignments?batch_scan_id=eq.%s&domain=eq.%s", c.url, batchID, domain)
	req, err := http.NewRequest("PATCH", url, bytes.NewBuffer(updateData))
	if err != nil {
		return fmt.Errorf("failed to create domain assignment update request: %v", err)
	}

	req.Header.Set("Authorization", "Bearer "+c.serviceKey)
	req.Header.Set("apikey", c.serviceKey) // 🔧 FIX: Add missing apikey header for Supabase authentication
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Prefer", "return=minimal")

	resp, err := c.httpClient.Do(req)
	if err != nil {
		return fmt.Errorf("failed to execute domain assignment update request: %v", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode >= 200 && resp.StatusCode < 300 {
		return nil
	}

	// Read error response
	responseBody, _ := io.ReadAll(resp.Body)
	return fmt.Errorf("failed to update batch domain assignment: HTTP %d - %s",
		resp.StatusCode, string(responseBody))
}

// UpdateAssetScanJob updates an asset scan job record
func (c *SupabaseClient) UpdateAssetScanJob(assetScanID string, updates map[string]interface{}) error {
	// Convert updates to JSON
	updateData, err := json.Marshal(updates)
	if err != nil {
		return fmt.Errorf("failed to marshal asset scan updates: %v", err)
	}

	fmt.Printf("🔬 DIAGNOSTIC: UpdateAssetScanJob called for ID: %s\n", assetScanID)
	fmt.Printf("🔬 DIAGNOSTIC: Update payload: %s\n", string(updateData))

	// Make HTTP PATCH request
	url := fmt.Sprintf("%s/rest/v1/asset_scan_jobs?id=eq.%s", c.url, assetScanID)
	fmt.Printf("🔬 DIAGNOSTIC: PATCH URL: %s\n", url)

	req, err := http.NewRequest("PATCH", url, bytes.NewBuffer(updateData))
	if err != nil {
		return fmt.Errorf("failed to create asset scan update request: %v", err)
	}

	req.Header.Set("Authorization", "Bearer "+c.serviceKey)
	req.Header.Set("apikey", c.serviceKey) // 🔧 FIX: Add missing apikey header for Supabase authentication
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Prefer", "return=minimal")

	fmt.Printf("🔬 DIAGNOSTIC: Sending PATCH request...\n")

	resp, err := c.httpClient.Do(req)
	if err != nil {
		fmt.Printf("❌ DIAGNOSTIC: HTTP request failed: %v\n", err)
		return fmt.Errorf("failed to execute asset scan update request: %v", err)
	}
	defer resp.Body.Close()

	fmt.Printf("🔬 DIAGNOSTIC: Received HTTP %d response\n", resp.StatusCode)

	if resp.StatusCode >= 200 && resp.StatusCode < 300 {
		fmt.Printf("✅ DIAGNOSTIC: Successfully updated asset_scan_jobs for ID: %s\n", assetScanID)
		return nil
	}

	// Read error response
	responseBody, _ := io.ReadAll(resp.Body)
	fmt.Printf("❌ DIAGNOSTIC: Error response body: %s\n", string(responseBody))
	return fmt.Errorf("failed to update asset scan job: HTTP %d - %s",
		resp.StatusCode, string(responseBody))
}

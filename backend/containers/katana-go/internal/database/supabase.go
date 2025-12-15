package database

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"time"
)

// SupabaseClient handles HTTP communication with Supabase REST API
type SupabaseClient struct {
	baseURL    string
	apiKey     string
	httpClient *http.Client
}

// NewSupabaseClient creates a new Supabase client
func NewSupabaseClient(baseURL, apiKey string) *SupabaseClient {
	return &SupabaseClient{
		baseURL: baseURL,
		apiKey:  apiKey,
		httpClient: &http.Client{
			Timeout: 30 * time.Second,
		},
	}
}

// Insert performs a POST request to insert data into a table
// Uses the `Prefer: resolution=merge-duplicates` header for upserts
func (c *SupabaseClient) Insert(table string, data interface{}, upsert bool) error {
	url := fmt.Sprintf("%s/rest/v1/%s", c.baseURL, table)

	jsonData, err := json.Marshal(data)
	if err != nil {
		return fmt.Errorf("failed to marshal data: %w", err)
	}

	req, err := http.NewRequest("POST", url, bytes.NewBuffer(jsonData))
	if err != nil {
		return fmt.Errorf("failed to create request: %w", err)
	}

	// Set headers
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("apikey", c.apiKey)
	req.Header.Set("Authorization", fmt.Sprintf("Bearer %s", c.apiKey))

	// Enable upsert if requested (ON CONFLICT DO UPDATE)
	if upsert {
		req.Header.Set("Prefer", "resolution=merge-duplicates")
	}

	resp, err := c.httpClient.Do(req)
	if err != nil {
		return fmt.Errorf("failed to execute request: %w", err)
	}
	defer resp.Body.Close()

	// Check for errors
	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		body, _ := io.ReadAll(resp.Body)
		return fmt.Errorf("supabase request failed (status %d): %s", resp.StatusCode, string(body))
	}

	return nil
}

// Query performs a GET request to fetch data from a table with filters
func (c *SupabaseClient) Query(table string, filters map[string]string, result interface{}) error {
	url := fmt.Sprintf("%s/rest/v1/%s", c.baseURL, table)

	req, err := http.NewRequest("GET", url, nil)
	if err != nil {
		return fmt.Errorf("failed to create request: %w", err)
	}

	// Add query parameters for filters
	q := req.URL.Query()
	for key, value := range filters {
		q.Add(key, value)
	}
	req.URL.RawQuery = q.Encode()

	// Set headers
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("apikey", c.apiKey)
	req.Header.Set("Authorization", fmt.Sprintf("Bearer %s", c.apiKey))

	resp, err := c.httpClient.Do(req)
	if err != nil {
		return fmt.Errorf("failed to execute request: %w", err)
	}
	defer resp.Body.Close()

	// Check for errors
	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		body, _ := io.ReadAll(resp.Body)
		return fmt.Errorf("supabase request failed (status %d): %s", resp.StatusCode, string(body))
	}

	// Decode response
	if err := json.NewDecoder(resp.Body).Decode(result); err != nil {
		return fmt.Errorf("failed to decode response: %w", err)
	}

	return nil
}

// Update performs a PATCH request to update data in a table
func (c *SupabaseClient) Update(table string, filters map[string]string, data interface{}) error {
	url := fmt.Sprintf("%s/rest/v1/%s", c.baseURL, table)

	jsonData, err := json.Marshal(data)
	if err != nil {
		return fmt.Errorf("failed to marshal data: %w", err)
	}

	req, err := http.NewRequest("PATCH", url, bytes.NewBuffer(jsonData))
	if err != nil {
		return fmt.Errorf("failed to create request: %w", err)
	}

	// Add query parameters for filters
	q := req.URL.Query()
	for key, value := range filters {
		q.Add(key, value)
	}
	req.URL.RawQuery = q.Encode()

	// Set headers
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("apikey", c.apiKey)
	req.Header.Set("Authorization", fmt.Sprintf("Bearer %s", c.apiKey))

	resp, err := c.httpClient.Do(req)
	if err != nil {
		return fmt.Errorf("failed to execute request: %w", err)
	}
	defer resp.Body.Close()

	// Check for errors
	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		body, _ := io.ReadAll(resp.Body)
		return fmt.Errorf("supabase request failed (status %d): %s", resp.StatusCode, string(body))
	}

	return nil
}


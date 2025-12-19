package client

import (
	"context"
	"crypto/tls"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"time"

	"tyvt-go/internal/limiter"
	"tyvt-go/internal/models"
	"tyvt-go/internal/rotator"
)

const (
	// VirusTotalAPIURL is the base URL for the VT domain report API
	VirusTotalAPIURL = "https://virustotal.com/vtapi/v2/domain/report"
	DefaultTimeout   = 30 * time.Second
)

// VirusTotalClient handles all VT API interactions
type VirusTotalClient struct {
	httpClient  *http.Client
	keyRotator  *rotator.KeyRotator
	rateLimiter *limiter.RateLimiter
}

// NewVirusTotalClient creates a new VT client with key rotation and rate limiting
//
// Parameters:
//   - keyRotator: manages API key rotation
//   - rateLimiter: enforces rate limits
//   - proxyURL: optional proxy (pass nil for direct connection)
//   - insecureTLS: skip TLS verification (use with caution)
func NewVirusTotalClient(
	keyRotator *rotator.KeyRotator,
	rateLimiter *limiter.RateLimiter,
	proxyURL *url.URL,
	insecureTLS bool,
) *VirusTotalClient {
	transport := &http.Transport{}

	// Configure proxy if provided
	if proxyURL != nil {
		transport.Proxy = http.ProxyURL(proxyURL)
	}

	// Configure TLS if insecure mode requested
	if insecureTLS {
		transport.TLSClientConfig = &tls.Config{
			InsecureSkipVerify: true,
		}
	}

	return &VirusTotalClient{
		httpClient: &http.Client{
			Timeout:   DefaultTimeout,
			Transport: transport,
		},
		keyRotator:  keyRotator,
		rateLimiter: rateLimiter,
	}
}

// QueryDomain queries VirusTotal for domain information and returns undetected URLs
func (c *VirusTotalClient) QueryDomain(ctx context.Context, domain string) (*models.DomainResult, error) {
	apiKey := c.keyRotator.CurrentKey()
	if apiKey == "" {
		return nil, fmt.Errorf("no API key available")
	}

	// Wait for rate limiter
	if err := c.rateLimiter.Wait(ctx, apiKey); err != nil {
		return nil, fmt.Errorf("rate limiter error: %w", err)
	}

	// Build request URL
	reqURL := fmt.Sprintf("%s?apikey=%s&domain=%s",
		VirusTotalAPIURL,
		url.QueryEscape(apiKey),
		url.QueryEscape(domain),
	)

	req, err := http.NewRequestWithContext(ctx, "GET", reqURL, nil)
	if err != nil {
		return nil, fmt.Errorf("failed to create request: %w", err)
	}

	req.Header.Set("User-Agent", "neobotnet-tyvt/1.0")

	resp, err := c.httpClient.Do(req)
	if err != nil {
		return nil, fmt.Errorf("failed to execute request: %w", err)
	}
	defer resp.Body.Close()

	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, fmt.Errorf("failed to read response body: %w", err)
	}

	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("API returned status %d: %s", resp.StatusCode, string(body))
	}

	// Parse JSON response
	var rawResponse map[string]interface{}
	if err := json.Unmarshal(body, &rawResponse); err != nil {
		return nil, fmt.Errorf("failed to parse JSON response: %w", err)
	}

	result := &models.DomainResult{
		Domain:    domain,
		Timestamp: time.Now(),
	}

	// Extract response_code
	if responseCode, ok := rawResponse["response_code"].(float64); ok {
		result.ResponseCode = int(responseCode)
	}

	// If response_code != 1, the domain wasn't found in VT database
	if result.ResponseCode != 1 {
		return result, nil
	}

	// Parse undetected_urls
	if err := c.parseUndetectedURLs(rawResponse, result); err != nil {
		return result, fmt.Errorf("failed to parse undetected URLs: %w", err)
	}

	return result, nil
}

// parseUndetectedURLs extracts undetected_urls from the VT response
func (c *VirusTotalClient) parseUndetectedURLs(rawResponse map[string]interface{}, result *models.DomainResult) error {
	undetectedInterface, exists := rawResponse["undetected_urls"]
	if !exists {
		return nil
	}

	undetectedArray, ok := undetectedInterface.([]interface{})
	if !ok {
		return nil
	}

	for _, item := range undetectedArray {
		// VT returns undetected_urls as arrays: [url, sha256, positives, total, scan_date]
		urlData, ok := item.([]interface{})
		if !ok || len(urlData) < 5 {
			continue
		}

		urlStr, ok := urlData[0].(string)
		if !ok {
			continue
		}

		// Skip index 1 (SHA256 hash)
		positives, ok := urlData[2].(float64)
		if !ok {
			continue
		}

		total, ok := urlData[3].(float64)
		if !ok {
			continue
		}

		scanDate, ok := urlData[4].(string)
		if !ok {
			continue
		}

		undetectedURL := models.UndetectedURL{
			URL:          urlStr,
			Positives:    int(positives),
			Total:        int(total),
			ScanDate:     scanDate,
			LastModified: time.Now(),
		}

		result.UndetectedURLs = append(result.UndetectedURLs, undetectedURL)
	}

	return nil
}

// Close cleans up the client (stops key rotation)
func (c *VirusTotalClient) Close() {
	if c.keyRotator != nil {
		c.keyRotator.Stop()
	}
}

// GetQuotaStatus returns current quota usage for the active key
func (c *VirusTotalClient) GetQuotaStatus() (dailyUsed, monthlyUsed int) {
	apiKey := c.keyRotator.CurrentKey()
	if apiKey == "" {
		return 0, 0
	}
	return c.rateLimiter.GetQuotaStatus(apiKey)
}


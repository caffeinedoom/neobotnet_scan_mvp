package main

import (
	"fmt"
	"log"
	"strings"
	"time"

	"github.com/projectdiscovery/goflags"
	"github.com/projectdiscovery/httpx/runner"
	"golang.org/x/net/publicsuffix"
)

// HTTPProbe represents a single HTTP probe result
// Maps to http_probes table schema (22 columns)
type HTTPProbe struct {
	// Foreign keys
	ScanJobID string `json:"scan_job_id"`
	AssetID   string `json:"asset_id"`

	// HTTPx core output fields (14 fields)
	StatusCode       *int     `json:"status_code"`        // nullable
	URL              string   `json:"url"`                // NOT NULL
	Title            *string  `json:"title"`              // nullable
	WebServer        *string  `json:"webserver"`          // nullable
	ContentLength    *int     `json:"content_length"`     // nullable
	FinalURL         *string  `json:"final_url"`          // nullable
	IP               *string  `json:"ip"`                 // nullable
	Technologies     []string `json:"technologies"`       // JSONB array
	CDNName          *string  `json:"cdn_name"`           // nullable
	ContentType      *string  `json:"content_type"`       // nullable
	ASN              *string  `json:"asn"`                // nullable
	ChainStatusCodes []int    `json:"chain_status_codes"` // JSONB array
	Location         *string  `json:"location"`           // nullable
	FaviconMD5       *string  `json:"favicon_md5"`        // nullable

	// Parsed/derived fields (4 fields)
	Subdomain    string `json:"subdomain"`     // NOT NULL
	ParentDomain string `json:"parent_domain"` // NOT NULL
	Scheme       string `json:"scheme"`        // NOT NULL (http/https)
	Port         int    `json:"port"`          // NOT NULL

	// Metadata (1 field)
	CreatedAt string `json:"created_at"` // timestamp
}

// probeHTTP performs HTTP probing for multiple subdomains using httpx SDK
func probeHTTP(subdomains []string, scanJobID string, assetID string) ([]HTTPProbe, error) {
	var allProbes []HTTPProbe
	createdAt := time.Now().UTC().Format(time.RFC3339)

	log.Printf("🌐 Starting HTTP probing for %d subdomains\n", len(subdomains))

	// Configure httpx options
	options := runner.Options{
		Methods:         "GET",                           // HTTP method
		InputTargetHost: goflags.StringSlice(subdomains), // Input subdomains

		// Enable important probes
		TechDetect:         true,   // Technology detection
		StatusCode:         true,   // Status codes
		ExtractTitle:       true,   // Page titles
		OutputServerHeader: true,   // Server headers
		OutputCDN:          "true", // CDN detection (string field)
		Location:           true,   // Redirect location
		ContentLength:      true,   // Response size
		Favicon:            true,   // Favicon hash

		// Redirect handling
		FollowRedirects: true,
		MaxRedirects:    10,

		// Performance
		Threads: 50,
		Timeout: 10, // 10 seconds per subdomain
		Retries: 1,

		// Silent mode (reduce noise)
		Silent: true,

		// Result handler - called for each result
		OnResult: func(r runner.Result) {
			// Handle errors
			if r.Err != nil {
				log.Printf("  ⚠️  Error probing %s: %v", r.Input, r.Err)
				return
			}

			// Convert runner.Result to HTTPProbe
			probe := convertResultToProbe(r, scanJobID, assetID, createdAt)

			// Only add successful probes (with status code)
			if probe.StatusCode != nil {
				allProbes = append(allProbes, probe)
				log.Printf("  ✅ %s → %d (%s)", r.Input, *probe.StatusCode, probe.Scheme)
			}
		},
	}

	// Validate options
	if err := options.ValidateOptions(); err != nil {
		return nil, fmt.Errorf("invalid httpx options: %v", err)
	}

	// Create httpx runner
	httpxRunner, err := runner.New(&options)
	if err != nil {
		return nil, fmt.Errorf("failed to create httpx runner: %v", err)
	}
	defer httpxRunner.Close()

	// Run enumeration (blocks until complete)
	log.Println("🔄 Running HTTP enumeration...")
	httpxRunner.RunEnumeration()

	log.Printf("📊 Total HTTP probes completed: %d\n", len(allProbes))
	return allProbes, nil
}

// convertResultToProbe maps runner.Result fields to HTTPProbe struct
func convertResultToProbe(r runner.Result, scanJobID string, assetID string, createdAt string) HTTPProbe {
	probe := HTTPProbe{
		// Foreign keys
		ScanJobID: scanJobID,
		AssetID:   assetID,

		// Core fields (NOT NULL in our schema)
		URL:       r.URL,
		Subdomain: extractSubdomain(r.Input, r.Host),
		Scheme:    r.Scheme,
		CreatedAt: createdAt,

		// Initialize arrays (default to empty, not nil)
		Technologies:     []string{},
		ChainStatusCodes: []int{},
	}

	// Status code
	if r.StatusCode > 0 {
		probe.StatusCode = &r.StatusCode
	}

	// Title
	if r.Title != "" {
		probe.Title = &r.Title
	}

	// Web server
	if r.WebServer != "" {
		probe.WebServer = &r.WebServer
	}

	// Content length
	if r.ContentLength > 0 {
		probe.ContentLength = &r.ContentLength
	}

	// Final URL (after redirects)
	if r.FinalURL != "" {
		probe.FinalURL = &r.FinalURL
	}

	// IP address (prefer IPv4, fallback to IPv6)
	if len(r.A) > 0 {
		probe.IP = &r.A[0]
	} else if len(r.AAAA) > 0 {
		probe.IP = &r.AAAA[0]
	}

	// Technologies (already []string)
	if len(r.Technologies) > 0 {
		probe.Technologies = r.Technologies
	}

	// CDN name
	if r.CDNName != "" {
		probe.CDNName = &r.CDNName
	}

	// Content type
	if r.ContentType != "" {
		probe.ContentType = &r.ContentType
	}

	// ASN (extract from *AsnResponse)
	if r.ASN != nil && r.ASN.AsNumber != "" {
		probe.ASN = &r.ASN.AsNumber
	}

	// Chain status codes (already []int)
	if len(r.ChainStatusCodes) > 0 {
		probe.ChainStatusCodes = r.ChainStatusCodes
	}

	// Location (redirect)
	if r.Location != "" {
		probe.Location = &r.Location
	}

	// Favicon MD5
	if r.FavIconMD5 != "" {
		probe.FaviconMD5 = &r.FavIconMD5
	}

	// Parent domain (extract from host)
	probe.ParentDomain = extractParentDomain(r.Host)

	// Port (convert string to int, default to 80/443)
	probe.Port = parsePort(r.Port, r.Scheme)

	return probe
}

// extractSubdomain extracts the subdomain from input or host
func extractSubdomain(input, host string) string {
	// Use host if available, otherwise fall back to input
	if host != "" {
		return host
	}
	return input
}

// extractParentDomain extracts the parent/apex domain (e.g., example.com from sub.example.com)
func extractParentDomain(subdomain string) string {
	// Remove protocol if present
	subdomain = strings.TrimPrefix(subdomain, "http://")
	subdomain = strings.TrimPrefix(subdomain, "https://")

	// Remove port if present
	if colonIndex := strings.Index(subdomain, ":"); colonIndex != -1 {
		subdomain = subdomain[:colonIndex]
	}

	// Remove path if present
	if slashIndex := strings.Index(subdomain, "/"); slashIndex != -1 {
		subdomain = subdomain[:slashIndex]
	}

	// Use publicsuffix library to extract eTLD+1
	parentDomain, err := publicsuffix.EffectiveTLDPlusOne(subdomain)
	if err != nil {
		// Fallback: simple split (take last 2 parts)
		parts := strings.Split(subdomain, ".")
		if len(parts) >= 2 {
			return strings.Join(parts[len(parts)-2:], ".")
		}
		return subdomain
	}

	return parentDomain
}

// parsePort converts port string to int with fallback to default ports
func parsePort(portStr string, scheme string) int {
	// Try to parse port string
	if portStr != "" {
		var port int
		if _, err := fmt.Sscanf(portStr, "%d", &port); err == nil && port > 0 && port <= 65535 {
			return port
		}
	}

	// Fallback to default ports based on scheme
	if scheme == "https" {
		return 443
	}
	return 80
}

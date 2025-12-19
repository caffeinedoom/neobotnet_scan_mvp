package main

import (
	"crypto/sha256"
	"encoding/hex"
	"net/url"
	"path/filepath"
	"sort"
	"strings"
)

// NormalizeURL normalizes a URL for consistent deduplication
// - Lowercases scheme and host
// - Sorts query parameters
// - Removes fragments
// - Removes trailing slashes (except for root)
func NormalizeURL(rawURL string) (string, error) {
	parsed, err := url.Parse(rawURL)
	if err != nil {
		return "", err
	}

	// Lowercase scheme and host
	parsed.Scheme = strings.ToLower(parsed.Scheme)
	parsed.Host = strings.ToLower(parsed.Host)

	// Remove fragment
	parsed.Fragment = ""

	// Sort query parameters for consistent ordering
	if parsed.RawQuery != "" {
		params := parsed.Query()
		keys := make([]string, 0, len(params))
		for k := range params {
			keys = append(keys, k)
		}
		sort.Strings(keys)

		sortedParams := url.Values{}
		for _, k := range keys {
			values := params[k]
			sort.Strings(values)
			for _, v := range values {
				sortedParams.Add(k, v)
			}
		}
		parsed.RawQuery = sortedParams.Encode()
	}

	// Remove trailing slash (except for root path)
	if parsed.Path != "/" && strings.HasSuffix(parsed.Path, "/") {
		parsed.Path = strings.TrimSuffix(parsed.Path, "/")
	}

	return parsed.String(), nil
}

// HashURL generates a SHA256 hash of a URL string
func HashURL(rawURL string) string {
	hash := sha256.Sum256([]byte(rawURL))
	return hex.EncodeToString(hash[:])
}

// NormalizeAndHash normalizes a URL and returns both normalized URL and hash
func NormalizeAndHash(rawURL string) (normalized string, hash string, err error) {
	normalized, err = NormalizeURL(rawURL)
	if err != nil {
		return "", "", err
	}
	hash = HashURL(normalized)
	return normalized, hash, nil
}

// ExtractDomain extracts the domain (host) from a URL
func ExtractDomain(rawURL string) (string, error) {
	parsed, err := url.Parse(rawURL)
	if err != nil {
		return "", err
	}
	// Remove port if present
	host := parsed.Hostname()
	return strings.ToLower(host), nil
}

// ExtractPath extracts the path component from a URL
func ExtractPath(rawURL string) (string, error) {
	parsed, err := url.Parse(rawURL)
	if err != nil {
		return "", err
	}
	if parsed.Path == "" {
		return "/", nil
	}
	return parsed.Path, nil
}

// ExtractQueryParams parses query parameters into a map
func ExtractQueryParams(rawURL string) (map[string]interface{}, error) {
	parsed, err := url.Parse(rawURL)
	if err != nil {
		return nil, err
	}

	result := make(map[string]interface{})
	for key, values := range parsed.Query() {
		if len(values) == 1 {
			result[key] = values[0]
		} else {
			result[key] = values
		}
	}
	return result, nil
}

// ExtractFileExtension extracts the file extension from a URL path
// Returns nil if no extension is found
func ExtractFileExtension(rawURL string) *string {
	parsed, err := url.Parse(rawURL)
	if err != nil {
		return nil
	}

	// Get the last segment of the path
	path := parsed.Path
	if path == "" || path == "/" {
		return nil
	}

	// Extract extension
	ext := filepath.Ext(path)
	if ext == "" || ext == "." {
		return nil
	}

	// Normalize to lowercase
	ext = strings.ToLower(ext)
	return &ext
}

// ParseURLComponents extracts all components from a URL for database storage
func ParseURLComponents(rawURL string) (domain, path string, queryParams map[string]interface{}, fileExt *string, err error) {
	domain, err = ExtractDomain(rawURL)
	if err != nil {
		return
	}

	path, err = ExtractPath(rawURL)
	if err != nil {
		return
	}

	queryParams, err = ExtractQueryParams(rawURL)
	if err != nil {
		return
	}

	fileExt = ExtractFileExtension(rawURL)

	return
}


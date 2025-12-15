package dedup

import (
	"crypto/sha256"
	"encoding/hex"
	"net/url"
	"sort"
	"strings"
)

// NormalizeURL normalizes a URL for consistent hashing and deduplication.
// 
// Normalization rules:
// 1. Lowercase scheme and host
// 2. Remove fragment (#section)
// 3. Sort query parameters alphabetically
// 4. Remove trailing slash from path (unless path is just "/")
// 5. Remove default ports (:80 for http, :443 for https)
//
// Examples:
//   Input:  "HTTPS://Example.COM:443/api/users?id=123&sort=asc#section"
//   Output: "https://example.com/api/users?id=123&sort=asc"
func NormalizeURL(rawURL string) (string, error) {
	// Parse the URL
	u, err := url.Parse(rawURL)
	if err != nil {
		return "", err
	}

	// Lowercase scheme and host
	u.Scheme = strings.ToLower(u.Scheme)
	u.Host = strings.ToLower(u.Host)

	// Remove fragment
	u.Fragment = ""

	// Remove default ports
	if (u.Scheme == "http" && strings.HasSuffix(u.Host, ":80")) ||
		(u.Scheme == "https" && strings.HasSuffix(u.Host, ":443")) {
		u.Host = strings.TrimSuffix(u.Host, ":80")
		u.Host = strings.TrimSuffix(u.Host, ":443")
	}

	// Sort query parameters
	if u.RawQuery != "" {
		q := u.Query()
		u.RawQuery = sortQueryParams(q)
	}

	// Remove trailing slash from path (unless path is just "/")
	if u.Path != "/" && strings.HasSuffix(u.Path, "/") {
		u.Path = strings.TrimSuffix(u.Path, "/")
	}

	return u.String(), nil
}

// sortQueryParams sorts query parameters alphabetically by key.
// For keys with multiple values, values are sorted alphabetically as well.
func sortQueryParams(q url.Values) string {
	keys := make([]string, 0, len(q))
	for k := range q {
		keys = append(keys, k)
	}
	sort.Strings(keys)

	var parts []string
	for _, k := range keys {
		values := q[k]
		sort.Strings(values) // Sort values for the same key
		for _, v := range values {
			parts = append(parts, url.QueryEscape(k)+"="+url.QueryEscape(v))
		}
	}
	return strings.Join(parts, "&")
}

// HashURL generates a SHA256 hash of a normalized URL.
// Returns a 64-character hex string.
//
// Example:
//   Input:  "https://example.com/api/users?id=123"
//   Output: "5d41402abc4b2a76b9719d911017c592..."
func HashURL(normalizedURL string) string {
	hash := sha256.Sum256([]byte(normalizedURL))
	return hex.EncodeToString(hash[:])
}

// NormalizeAndHash is a convenience function that combines NormalizeURL and HashURL.
// Returns the normalized URL and its hash, or an error if normalization fails.
func NormalizeAndHash(rawURL string) (normalized string, hash string, err error) {
	normalized, err = NormalizeURL(rawURL)
	if err != nil {
		return "", "", err
	}
	hash = HashURL(normalized)
	return normalized, hash, nil
}


package dedup

import (
	"testing"
)

// TestNormalizeURL tests URL normalization logic
func TestNormalizeURL(t *testing.T) {
	tests := []struct {
		name     string
		input    string
		expected string
		wantErr  bool
	}{
		{
			name:     "Lowercase scheme and host",
			input:    "HTTPS://Example.COM/path",
			expected: "https://example.com/path",
			wantErr:  false,
		},
		{
			name:     "Remove fragment",
			input:    "https://example.com/page#section",
			expected: "https://example.com/page",
			wantErr:  false,
		},
		{
			name:     "Sort query parameters",
			input:    "https://example.com/api?z=1&a=2&m=3",
			expected: "https://example.com/api?a=2&m=3&z=1",
			wantErr:  false,
		},
		{
			name:     "Remove trailing slash",
			input:    "https://example.com/path/",
			expected: "https://example.com/path",
			wantErr:  false,
		},
		{
			name:     "Keep root slash",
			input:    "https://example.com/",
			expected: "https://example.com/",
			wantErr:  false,
		},
		{
			name:     "Remove default HTTPS port",
			input:    "https://example.com:443/path",
			expected: "https://example.com/path",
			wantErr:  false,
		},
		{
			name:     "Remove default HTTP port",
			input:    "http://example.com:80/path",
			expected: "http://example.com/path",
			wantErr:  false,
		},
		{
			name:     "Keep non-default port",
			input:    "https://example.com:8443/path",
			expected: "https://example.com:8443/path",
			wantErr:  false,
		},
		{
			name:     "Complex URL with all features",
			input:    "HTTPS://Example.COM:443/API/Users?sort=desc&id=123&filter=active#top",
			expected: "https://example.com/API/Users?filter=active&id=123&sort=desc",
			wantErr:  false,
		},
		{
			name:     "URL with special characters in query",
			input:    "https://example.com/search?q=hello%20world&lang=en",
			expected: "https://example.com/search?lang=en&q=hello+world",
			wantErr:  false,
		},
		{
			name:     "Invalid URL (missing scheme)",
			input:    "://example.com",
			expected: "",
			wantErr:  true,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			result, err := NormalizeURL(tt.input)
			
			if tt.wantErr {
				if err == nil {
					t.Errorf("NormalizeURL() expected error but got nil")
				}
				return
			}

			if err != nil {
				t.Errorf("NormalizeURL() unexpected error: %v", err)
				return
			}

			if result != tt.expected {
				t.Errorf("NormalizeURL() = %v, want %v", result, tt.expected)
			}
		})
	}
}

// TestHashURL tests SHA256 hashing
func TestHashURL(t *testing.T) {
	// Test that same input produces same hash
	url1 := "https://example.com/"
	hash1 := HashURL(url1)
	hash2 := HashURL(url1)

	if hash1 != hash2 {
		t.Errorf("HashURL() produced different hashes for same input: %v vs %v", hash1, hash2)
	}

	// Test hash length (SHA256 = 64 hex chars)
	if len(hash1) != 64 {
		t.Errorf("HashURL() length = %d, want 64", len(hash1))
	}

	// Test different inputs produce different hashes
	url3 := "https://different.com/"
	hash3 := HashURL(url3)

	if hash1 == hash3 {
		t.Errorf("HashURL() produced same hash for different inputs")
	}
}

// TestNormalizeAndHash tests the combined function
func TestNormalizeAndHash(t *testing.T) {
	tests := []struct {
		name              string
		input             string
		expectedNormalized string
		wantErr           bool
	}{
		{
			name:              "Valid URL",
			input:             "HTTPS://Example.COM/Path#fragment",
			expectedNormalized: "https://example.com/Path",
			wantErr:           false,
		},
		{
			name:              "Invalid URL (missing scheme)",
			input:             "://example.com",
			expectedNormalized: "",
			wantErr:           true,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			normalized, hash, err := NormalizeAndHash(tt.input)
			
			if tt.wantErr {
				if err == nil {
					t.Errorf("NormalizeAndHash() expected error but got nil")
				}
				return
			}

			if err != nil {
				t.Errorf("NormalizeAndHash() unexpected error: %v", err)
				return
			}

			if normalized != tt.expectedNormalized {
				t.Errorf("NormalizeAndHash() normalized = %v, want %v", normalized, tt.expectedNormalized)
			}

			if len(hash) != 64 {
				t.Errorf("NormalizeAndHash() hash length = %d, want 64", len(hash))
			}
		})
	}
}

// TestDeduplication tests that identical URLs produce identical hashes
func TestDeduplication(t *testing.T) {
	// These URLs should all normalize to the same URL and produce the same hash
	duplicates := []string{
		"https://example.com/api/users?id=123&sort=asc",
		"HTTPS://EXAMPLE.COM/api/users?sort=asc&id=123",
		"https://example.com:443/api/users?id=123&sort=asc#section",
		"https://example.com/api/users?sort=asc&id=123",
	}

	var hashes []string
	var normalized []string

	for _, url := range duplicates {
		norm, hash, err := NormalizeAndHash(url)
		if err != nil {
			t.Fatalf("NormalizeAndHash(%s) unexpected error: %v", url, err)
		}
		hashes = append(hashes, hash)
		normalized = append(normalized, norm)
	}

	// All hashes should be identical
	for i := 1; i < len(hashes); i++ {
		if hashes[i] != hashes[0] {
			t.Errorf("Duplicate URLs produced different hashes:\n  URL 0: %s → %s (hash: %s)\n  URL %d: %s → %s (hash: %s)",
				duplicates[0], normalized[0], hashes[0],
				i, duplicates[i], normalized[i], hashes[i])
		}
	}

	// All normalized URLs should be identical
	expectedNormalized := "https://example.com/api/users?id=123&sort=asc"
	for i, norm := range normalized {
		if norm != expectedNormalized {
			t.Errorf("URL %d normalized incorrectly:\n  Input: %s\n  Got: %s\n  Want: %s",
				i, duplicates[i], norm, expectedNormalized)
		}
	}
}

// BenchmarkNormalizeURL benchmarks URL normalization
func BenchmarkNormalizeURL(b *testing.B) {
	url := "HTTPS://Example.COM:443/api/users?sort=desc&id=123&filter=active#section"
	
	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		_, _ = NormalizeURL(url)
	}
}

// BenchmarkHashURL benchmarks SHA256 hashing
func BenchmarkHashURL(b *testing.B) {
	url := "https://example.com/api/users?filter=active&id=123&sort=desc"
	
	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		_ = HashURL(url)
	}
}

// BenchmarkNormalizeAndHash benchmarks the combined operation
func BenchmarkNormalizeAndHash(b *testing.B) {
	url := "HTTPS://Example.COM:443/api/users?sort=desc&id=123&filter=active#section"
	
	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		_, _, _ = NormalizeAndHash(url)
	}
}


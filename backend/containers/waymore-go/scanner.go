package main

import (
	"bufio"
	"fmt"
	"log"
	"os"
	"os/exec"
	"path/filepath"
	"strconv"
	"strings"
	"time"
)

// WaymoreScanner wraps the waymore Python tool as a subprocess
type WaymoreScanner struct {
	ScanJobID  string
	AssetID    string
	ConfigPath string
	Limit      int
	Providers  []string
	Timeout    int // Timeout in seconds
}

// NewWaymoreScanner creates a new scanner instance
func NewWaymoreScanner(scanJobID, assetID string) *WaymoreScanner {
	limit := getEnvInt("WAYMORE_LIMIT", 5000)
	timeout := getEnvInt("WAYMORE_TIMEOUT", 600) // 10 minutes default

	// Parse providers from environment or use defaults
	// Note: waymore uses 'otx' for AlienVault OTX, not 'alienvault'
	providers := []string{"wayback", "commoncrawl", "otx", "urlscan", "virustotal"}
	if providersEnv := os.Getenv("WAYMORE_PROVIDERS"); providersEnv != "" {
		providers = strings.Split(providersEnv, ",")
		for i, p := range providers {
			providers[i] = strings.TrimSpace(p)
		}
	}

	return &WaymoreScanner{
		ScanJobID:  scanJobID,
		AssetID:    assetID,
		ConfigPath: getEnv("WAYMORE_CONFIG", "/app/config.yml"),
		Limit:      limit,
		Providers:  providers,
		Timeout:    timeout,
	}
}

// ScanDomain runs waymore for a single domain and returns discovered URLs
func (s *WaymoreScanner) ScanDomain(domain string) ([]DiscoveredURL, error) {
	startTime := time.Now()
	log.Printf("   🔍 Running waymore for: %s", domain)
	log.Printf("      Limit: %d URLs, Timeout: %ds", s.Limit, s.Timeout)
	log.Printf("      Providers: %s", strings.Join(s.Providers, ", "))

	// Create temp directory for output
	tmpDir, err := os.MkdirTemp("", "waymore-*")
	if err != nil {
		return nil, fmt.Errorf("failed to create temp dir: %w", err)
	}
	defer os.RemoveAll(tmpDir)

	outputFile := filepath.Join(tmpDir, "urls.txt")

	// Build waymore command
	// waymore -i domain -mode U -oU urls.txt -l 5000 -c config.yml
	args := []string{
		"-i", domain,
		"-mode", "U", // URL mode only (no responses)
		"-oU", outputFile, // Output URLs to file
		"-l", strconv.Itoa(s.Limit),
	}

	// Add config file if it exists
	if _, err := os.Stat(s.ConfigPath); err == nil {
		args = append(args, "-c", s.ConfigPath)
	}

	// Add provider filtering
	if len(s.Providers) > 0 {
		args = append(args, "--providers", strings.Join(s.Providers, ","))
	}

	log.Printf("      Command: waymore %s", strings.Join(args, " "))

	// Execute waymore with timeout
	cmd := exec.Command("waymore", args...)
	cmd.Dir = tmpDir

	// Set environment for API keys (passed through from container env)
	cmd.Env = append(os.Environ(),
		fmt.Sprintf("HOME=%s", tmpDir), // waymore uses HOME for cache
	)

	// Run with timeout
	done := make(chan error, 1)
	go func() {
		output, err := cmd.CombinedOutput()
		// ALWAYS log output for debugging - waymore may fail silently
		if len(output) > 0 {
			// Truncate long output for logging
			outputStr := string(output)
			if len(outputStr) > 2000 {
				outputStr = outputStr[:2000] + "... (truncated)"
			}
			log.Printf("      📝 waymore output:\n%s", outputStr)
		}
		if err != nil {
			log.Printf("      ⚠️  waymore exited with error: %v", err)
		}
		done <- err
	}()

	// Wait for completion or timeout
	select {
	case err := <-done:
		if err != nil {
			// Log but don't fail - waymore may have produced partial results
			log.Printf("      ⚠️  waymore command failed: %v", err)
		}
		// Also check if output file exists and log its size
		if info, statErr := os.Stat(outputFile); statErr == nil {
			log.Printf("      📁 Output file size: %d bytes", info.Size())
		} else {
			log.Printf("      ⚠️  Output file not found: %v", statErr)
		}
	case <-time.After(time.Duration(s.Timeout) * time.Second):
		if cmd.Process != nil {
			cmd.Process.Kill()
		}
		log.Printf("      ⚠️  waymore timed out after %ds", s.Timeout)
	}

	// Parse output file
	urls, err := s.parseOutputFile(outputFile, domain)
	if err != nil {
		return nil, fmt.Errorf("failed to parse output: %w", err)
	}

	duration := time.Since(startTime)
	log.Printf("      ✅ Discovered %d URLs in %s", len(urls), duration.Round(time.Second))

	return urls, nil
}

// parseOutputFile reads waymore's output and creates structured URL records
func (s *WaymoreScanner) parseOutputFile(filePath, parentDomain string) ([]DiscoveredURL, error) {
	var urls []DiscoveredURL

	file, err := os.Open(filePath)
	if err != nil {
		if os.IsNotExist(err) {
			// No output file = no URLs found
			log.Printf("      ℹ️  No output file generated (no URLs found)")
			return urls, nil
		}
		return nil, err
	}
	defer file.Close()

	scanner := bufio.NewScanner(file)
	now := time.Now().UTC().Format(time.RFC3339)

	// Track unique URLs to avoid duplicates from waymore output
	seen := make(map[string]bool)

	for scanner.Scan() {
		line := strings.TrimSpace(scanner.Text())
		if line == "" || strings.HasPrefix(line, "#") {
			continue
		}

		// Skip if already seen
		if seen[line] {
			continue
		}
		seen[line] = true

		// Determine source from URL pattern (if identifiable)
		source := s.determineSource(line)

		urls = append(urls, DiscoveredURL{
			URL:          line,
			ParentDomain: parentDomain,
			Source:       source,
			AssetID:      s.AssetID,
			ScanJobID:    s.ScanJobID,
			DiscoveredAt: now,
			Metadata: map[string]string{
				"tool":    "waymore",
				"version": "1.0",
			},
		})
	}

	if err := scanner.Err(); err != nil {
		return nil, fmt.Errorf("error reading output file: %w", err)
	}

	return urls, nil
}

// determineSource attempts to identify which archive source a URL came from
// Note: waymore aggregates results, so we mark as "waymore" by default
func (s *WaymoreScanner) determineSource(url string) string {
	// In waymore's output, URLs are the actual target URLs, not archive URLs
	// The source information is not preserved in the output file
	// So we use "waymore" as the aggregated source
	return "waymore"
}

// getEnv returns an environment variable value or a default
func getEnv(key, defaultValue string) string {
	if value := os.Getenv(key); value != "" {
		return value
	}
	return defaultValue
}

// getEnvInt returns an integer environment variable or a default
func getEnvInt(key string, defaultValue int) int {
	if value := os.Getenv(key); value != "" {
		if intValue, err := strconv.Atoi(value); err == nil {
			return intValue
		}
	}
	return defaultValue
}

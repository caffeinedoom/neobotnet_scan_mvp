package main

import (
	"log"
	"time"

	"github.com/projectdiscovery/goflags"
	"github.com/projectdiscovery/httpx/runner"
)

// ProbeURL performs HTTP probing for a single URL using httpx SDK
// Returns probe result with all extracted metadata
func ProbeURL(targetURL string) *ProbeResult {
	result := &ProbeResult{
		URL:           targetURL,
		IsAlive:       false,
		Technologies:  []string{},
		RedirectChain: []int{},
	}

	startTime := time.Now()

	// Configure httpx options for single URL probe
	options := runner.Options{
		Methods:         "GET",
		InputTargetHost: goflags.StringSlice([]string{targetURL}),

		// Enable important probes
		TechDetect:         true,   // Technology detection
		StatusCode:         true,   // Status codes
		ExtractTitle:       true,   // Page titles
		OutputServerHeader: true,   // Server headers
		OutputCDN:          "true", // CDN detection
		Location:           true,   // Redirect location
		ContentLength:      true,   // Response size

		// Redirect handling
		FollowRedirects: true,
		MaxRedirects:    10,

		// Performance - single URL, be patient
		Threads: 1,
		Timeout: 15, // 15 seconds timeout
		Retries: 2,

		// Silent mode
		Silent: true,

		// Result handler
		OnResult: func(r runner.Result) {
			if r.Err != nil {
				result.Error = r.Err
				return
			}

			// URL is alive if we got a response
			result.IsAlive = true
			result.ResponseTimeMs = int(time.Since(startTime).Milliseconds())

			// Status code
			if r.StatusCode > 0 {
				result.StatusCode = r.StatusCode
			}

			// Title
			if r.Title != "" {
				result.Title = r.Title
			}

			// Content type
			if r.ContentType != "" {
				result.ContentType = r.ContentType
			}

			// Content length
			if r.ContentLength > 0 {
				result.ContentLength = r.ContentLength
			}

			// Final URL (after redirects)
			if r.FinalURL != "" {
				result.FinalURL = r.FinalURL
			}

			// Web server
			if r.WebServer != "" {
				result.Webserver = r.WebServer
			}

			// Technologies
			if len(r.Technologies) > 0 {
				result.Technologies = r.Technologies
			}

			// Redirect chain
			if len(r.ChainStatusCodes) > 0 {
				result.RedirectChain = r.ChainStatusCodes
			}
		},
	}

	// Validate options
	if err := options.ValidateOptions(); err != nil {
		result.Error = err
		return result
	}

	// Create httpx runner
	httpxRunner, err := runner.New(&options)
	if err != nil {
		result.Error = err
		return result
	}
	defer httpxRunner.Close()

	// Run enumeration (blocks until complete)
	httpxRunner.RunEnumeration()

	return result
}

// ProbeURLBatch probes multiple URLs and returns results
// Uses goroutines for parallel probing
func ProbeURLBatch(urls []string, concurrency int) []*ProbeResult {
	results := make([]*ProbeResult, len(urls))

	// Simple sequential probing for now
	// TODO: Implement concurrent probing with semaphore
	for i, url := range urls {
		log.Printf("  🔍 Probing [%d/%d]: %s", i+1, len(urls), url)
		results[i] = ProbeURL(url)

		if results[i].IsAlive {
			log.Printf("    ✅ %d %s", results[i].StatusCode, results[i].ContentType)
		} else if results[i].Error != nil {
			log.Printf("    ❌ Error: %v", results[i].Error)
		} else {
			log.Printf("    ⚠️ No response")
		}
	}

	return results
}


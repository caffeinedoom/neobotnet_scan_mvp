package main

import (
	"fmt"
	"log"
	"strings"
	"time"

	"github.com/miekg/dns"
	"github.com/projectdiscovery/dnsx/libs/dnsx"
	"github.com/projectdiscovery/retryabledns"
	"golang.org/x/net/publicsuffix"
)

// resolveDomains performs DNS resolution for multiple domains
func resolveDomains(domains []string, dnsxClient *dnsx.DNSX) ([]DNSRecord, error) {
	var allRecords []DNSRecord
	resolvedAt := time.Now().UTC().Format(time.RFC3339)

	log.Printf("🔍 Starting DNS resolution for %d domains\n", len(domains))

	for i, domain := range domains {
		domain = strings.TrimSpace(domain)
		if domain == "" {
			continue
		}

		log.Printf("[%d/%d] Querying: %s", i+1, len(domains), domain)

		// Query multiple record types at once
		dnsData, err := dnsxClient.QueryMultiple(domain)
		if err != nil {
			log.Printf("  ⚠️  Error querying %s: %v", domain, err)
			continue
		}

		// Extract parent domain for denormalized storage
		parentDomain := extractParentDomain(domain)

		// Process all record types
		// Note: Sequential mode doesn't have scan/batch/asset IDs, so pass empty strings
		records := processDNSData(domain, parentDomain, dnsData, resolvedAt, "", "", "")
		allRecords = append(allRecords, records...)

		if len(records) > 0 {
			log.Printf("  ✅ Found %d DNS records", len(records))
		} else {
			log.Printf("  ⚠️  No DNS records found")
		}
	}

	log.Printf("📊 Total DNS records found: %d\n", len(allRecords))
	return allRecords, nil
}

// processDNSData converts dnsx DNS data into DNSRecord structs
func processDNSData(subdomain, parentDomain string, dnsData *retryabledns.DNSData, resolvedAt string, scanJobID string, batchScanID string, assetID string) []DNSRecord {
	var records []DNSRecord

	// Convert TTL to pointer (nullable)
	var ttlPtr *int
	if dnsData.TTL > 0 {
		ttl := int(dnsData.TTL)
		ttlPtr = &ttl
	}

	// Process A records (IPv4)
	if len(dnsData.A) > 0 {
		log.Printf("  📌 A records: %d found", len(dnsData.A))
		for _, ip := range dnsData.A {
			record := DNSRecord{
				Subdomain:    subdomain,
				ParentDomain: parentDomain,
				RecordType:   "A",
				RecordValue:  ip,
				TTL:          ttlPtr,
				ResolvedAt:   resolvedAt,
				// 🔧 FIX: Add foreign keys for proper database relationships
				ScanJobID:   scanJobID,
				BatchScanID: batchScanID,
				AssetID:     assetID,
			}
			records = append(records, record)
			log.Printf("     → %s", ip)
		}
	}

	// Process AAAA records (IPv6)
	if len(dnsData.AAAA) > 0 {
		log.Printf("  📌 AAAA records: %d found", len(dnsData.AAAA))
		for _, ip := range dnsData.AAAA {
			record := DNSRecord{
				Subdomain:    subdomain,
				ParentDomain: parentDomain,
				RecordType:   "AAAA",
				RecordValue:  ip,
				TTL:          ttlPtr,
				ResolvedAt:   resolvedAt,
				ScanJobID:    scanJobID,
				BatchScanID:  batchScanID,
				AssetID:      assetID,
			}
			records = append(records, record)
			log.Printf("     → %s", ip)
		}
	}

	// Process CNAME records
	if len(dnsData.CNAME) > 0 {
		log.Printf("  📌 CNAME records: %d found", len(dnsData.CNAME))
		for _, cname := range dnsData.CNAME {
			record := DNSRecord{
				Subdomain:    subdomain,
				ParentDomain: parentDomain,
				RecordType:   "CNAME",
				RecordValue:  cname,
				TTL:          ttlPtr,
				ResolvedAt:   resolvedAt,
				ScanJobID:    scanJobID,
				BatchScanID:  batchScanID,
				AssetID:      assetID,
			}
			records = append(records, record)
			log.Printf("     → %s", cname)
		}
	}

	// Process MX records
	if len(dnsData.MX) > 0 {
		log.Printf("  📌 MX records: %d found", len(dnsData.MX))
		for _, mx := range dnsData.MX {
			// MX format from dnsx: "priority:hostname"
			// Example: "10:mail.example.com."
			priority, mxHost := parseMXRecord(mx)

			record := DNSRecord{
				Subdomain:    subdomain,
				ParentDomain: parentDomain,
				RecordType:   "MX",
				RecordValue:  mxHost,
				Priority:     priority,
				TTL:          ttlPtr,
				ResolvedAt:   resolvedAt,
				ScanJobID:    scanJobID,
				BatchScanID:  batchScanID,
				AssetID:      assetID,
			}
			records = append(records, record)
			if priority != nil {
				log.Printf("     → [%d] %s", *priority, mxHost)
			} else {
				log.Printf("     → %s", mxHost)
			}
		}
	}

	// Process TXT records
	if len(dnsData.TXT) > 0 {
		log.Printf("  📌 TXT records: %d found", len(dnsData.TXT))
		for _, txt := range dnsData.TXT {
			// TXT records can be very long (SPF, DKIM, etc.)
			displayValue := txt
			if len(txt) > 100 {
				displayValue = txt[:100] + "..."
			}

			record := DNSRecord{
				Subdomain:    subdomain,
				ParentDomain: parentDomain,
				RecordType:   "TXT",
				RecordValue:  txt,
				TTL:          ttlPtr,
				ResolvedAt:   resolvedAt,
				ScanJobID:    scanJobID,
				BatchScanID:  batchScanID,
				AssetID:      assetID,
			}
			records = append(records, record)
			log.Printf("     → %s", displayValue)
		}
	}

	return records
}

// parseMXRecord parses MX record in format "priority:hostname" from dnsx
func parseMXRecord(mx string) (*int, string) {
	parts := strings.SplitN(mx, ":", 2)

	if len(parts) == 2 {
		var priority int
		if _, err := fmt.Sscanf(parts[0], "%d", &priority); err == nil {
			// Remove trailing dot from hostname if present
			hostname := strings.TrimSuffix(parts[1], ".")
			return &priority, hostname
		}
	}

	// Fallback: return entire string as hostname with nil priority
	hostname := strings.TrimSuffix(mx, ".")
	return nil, hostname
}

// extractParentDomain extracts the parent domain from a subdomain
// Examples:
//   - "api.example.com" → "example.com"
//   - "www.api.example.com" → "example.com"
//   - "example.com" → "example.com"
//   - "test.co.uk" → "test.co.uk"
func extractParentDomain(subdomain string) string {
	// Use publicsuffix library for accurate TLD handling
	etld1, err := publicsuffix.EffectiveTLDPlusOne(subdomain)
	if err != nil {
		// Fallback: simple split logic for cases where publicsuffix fails
		parts := strings.Split(subdomain, ".")
		if len(parts) >= 2 {
			return strings.Join(parts[len(parts)-2:], ".")
		}
		return subdomain
	}
	return etld1
}

// initializeDNSXClient creates and configures the dnsx client
func initializeDNSXClient() (*dnsx.DNSX, error) {
	// Configure dnsx options
	dnsxOptions := dnsx.Options{
		BaseResolvers: dnsx.DefaultResolvers,
		MaxRetries:    3,
		QuestionTypes: []uint16{
			dns.TypeA,     // IPv4
			dns.TypeAAAA,  // IPv6
			dns.TypeCNAME, // Canonical names
			dns.TypeMX,    // Mail exchange
			dns.TypeTXT,   // Text records
		},
		OutputCDN: false, // CDN detection disabled per user requirement
	}

	log.Println("🔧 Initializing DNSX client...")
	log.Printf("  • Resolvers: %v", dnsxOptions.BaseResolvers)
	log.Printf("  • Max Retries: %d", dnsxOptions.MaxRetries)
	log.Printf("  • Query Types: A, AAAA, CNAME, MX, TXT")
	log.Printf("  • CDN Detection: Disabled")

	dnsxClient, err := dnsx.New(dnsxOptions)
	if err != nil {
		return nil, fmt.Errorf("failed to create dnsx client: %v", err)
	}

	log.Println("✅ DNSX client initialized successfully")
	return dnsxClient, nil
}

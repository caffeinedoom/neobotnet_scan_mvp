#!/usr/bin/env python3
"""
Migration script to fix corrupted subdomain and parent_domain in http_probes table.

PROBLEM:
  The httpx-go scanner's extractParentDomain function was receiving IP addresses
  from r.Host instead of hostnames. This corrupted both columns:
  - subdomain: contains IP addresses (e.g., "67.202.6.174")
  - parent_domain: contains partial IPs (e.g., "6.174")

SOLUTION:
  Extract correct values from the URL column, which is clean.

SAFETY:
  - Uses batch updates to avoid memory issues
  - Verifies results after each batch
  - Can be run multiple times safely (idempotent)

Usage:
  python run_fix_http_probes.py --dry-run    # Preview changes without applying
  python run_fix_http_probes.py --apply      # Apply the migration
"""

import argparse
import re
from urllib.parse import urlparse
from supabase import create_client

# Configuration
SUPABASE_URL = 'https://zsxbihewnvnhxoavzkbh.supabase.co'
SUPABASE_SERVICE_KEY = 'sb_secret_-bbEmDOJ4Tk-pqEgFDkY6A_X1p0w59k'
BATCH_SIZE = 500


def extract_hostname(url: str) -> str:
    """Extract hostname from URL."""
    try:
        parsed = urlparse(url)
        return parsed.hostname or ''
    except Exception:
        return ''


def extract_apex_domain(hostname: str) -> str:
    """
    Extract apex/parent domain from hostname.
    Simple approach: take last 2 parts for common TLDs.
    """
    if not hostname:
        return ''
    parts = hostname.split('.')
    if len(parts) >= 2:
        return '.'.join(parts[-2:])
    return hostname


def is_corrupted(parent_domain: str) -> bool:
    """Check if parent_domain looks like a partial IP (e.g., '6.174')."""
    if not parent_domain:
        return False
    return bool(re.match(r'^\d+\.\d+$', parent_domain))


def get_corrupted_count(supabase) -> int:
    """Count records with corrupted parent_domain."""
    # Using regexp pattern via PostgREST
    result = supabase.table('http_probes').select('id', count='exact').execute()
    total = result.count or 0
    
    # Fetch a sample to estimate corruption rate
    sample = supabase.table('http_probes').select('parent_domain').limit(1000).execute()
    corrupted = sum(1 for row in sample.data if is_corrupted(row.get('parent_domain', '')))
    
    # Estimate total corrupted
    if len(sample.data) > 0:
        estimated = int((corrupted / len(sample.data)) * total)
        return estimated
    return 0


def dry_run(supabase):
    """Preview what changes would be made without applying them."""
    print("=" * 60)
    print("DRY RUN - No changes will be made")
    print("=" * 60)
    
    # Get total count
    result = supabase.table('http_probes').select('id', count='exact').execute()
    total = result.count or 0
    print(f"\nTotal http_probes records: {total:,}")
    
    # Get sample of corrupted records
    sample = supabase.table('http_probes').select(
        'id, url, subdomain, parent_domain'
    ).limit(10).execute()
    
    corrupted_sample = [r for r in sample.data if is_corrupted(r.get('parent_domain', ''))]
    print(f"\nSample of corrupted records ({len(corrupted_sample)} of 10):")
    print("-" * 60)
    
    for row in corrupted_sample[:5]:
        url = row['url']
        new_subdomain = extract_hostname(url)
        new_parent_domain = extract_apex_domain(new_subdomain)
        
        print(f"ID: {row['id']}")
        print(f"  URL: {url}")
        print(f"  subdomain: '{row['subdomain']}' → '{new_subdomain}'")
        print(f"  parent_domain: '{row['parent_domain']}' → '{new_parent_domain}'")
        print()
    
    # Estimate total corrupted
    estimated_corrupted = get_corrupted_count(supabase)
    print(f"Estimated corrupted records: {estimated_corrupted:,} ({(estimated_corrupted/total)*100:.1f}%)")
    
    print("\n" + "=" * 60)
    print("To apply these changes, run with --apply flag")
    print("=" * 60)


def apply_migration(supabase):
    """Apply the migration to fix corrupted records."""
    print("=" * 60)
    print("APPLYING MIGRATION")
    print("=" * 60)
    
    # Get total count
    result = supabase.table('http_probes').select('id', count='exact').execute()
    total = result.count or 0
    print(f"\nTotal http_probes records: {total:,}")
    
    # Process in batches
    offset = 0
    fixed_count = 0
    error_count = 0
    
    while True:
        # Fetch batch
        batch = supabase.table('http_probes').select(
            'id, url, subdomain, parent_domain'
        ).range(offset, offset + BATCH_SIZE - 1).execute()
        
        if not batch.data:
            break
        
        print(f"\nProcessing batch {offset // BATCH_SIZE + 1} (records {offset + 1}-{offset + len(batch.data)})...")
        
        # Filter corrupted records
        for row in batch.data:
            if not is_corrupted(row.get('parent_domain', '')):
                continue
            
            url = row['url']
            new_subdomain = extract_hostname(url)
            new_parent_domain = extract_apex_domain(new_subdomain)
            
            if not new_subdomain or not new_parent_domain:
                print(f"  WARNING: Could not extract from URL: {url}")
                error_count += 1
                continue
            
            try:
                # Update record
                supabase.table('http_probes').update({
                    'subdomain': new_subdomain,
                    'parent_domain': new_parent_domain
                }).eq('id', row['id']).execute()
                fixed_count += 1
            except Exception as e:
                print(f"  ERROR updating {row['id']}: {e}")
                error_count += 1
        
        offset += BATCH_SIZE
        print(f"  Fixed: {fixed_count:,} | Errors: {error_count}")
        
        # Safety check
        if offset > total + BATCH_SIZE:
            break
    
    print("\n" + "=" * 60)
    print("MIGRATION COMPLETE")
    print("=" * 60)
    print(f"  Total records processed: {total:,}")
    print(f"  Records fixed: {fixed_count:,}")
    print(f"  Errors: {error_count}")
    
    # Verification
    print("\nVerifying results...")
    remaining_corrupted = get_corrupted_count(supabase)
    print(f"  Remaining corrupted records: {remaining_corrupted}")
    
    if remaining_corrupted == 0:
        print("\n✓ Migration successful! All records have been fixed.")
    else:
        print(f"\n⚠ Warning: {remaining_corrupted} records may still be corrupted.")


def main():
    parser = argparse.ArgumentParser(description='Fix http_probes subdomain/parent_domain')
    parser.add_argument('--dry-run', action='store_true', help='Preview changes without applying')
    parser.add_argument('--apply', action='store_true', help='Apply the migration')
    args = parser.parse_args()
    
    if not args.dry_run and not args.apply:
        print("Please specify --dry-run or --apply")
        print("  --dry-run: Preview changes without applying")
        print("  --apply: Apply the migration")
        return
    
    # Connect to Supabase
    supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
    
    if args.dry_run:
        dry_run(supabase)
    elif args.apply:
        confirm = input("This will modify the database. Type 'yes' to confirm: ")
        if confirm.lower() == 'yes':
            apply_migration(supabase)
        else:
            print("Migration cancelled.")


if __name__ == '__main__':
    main()

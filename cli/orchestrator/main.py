#!/usr/bin/env python3
"""
NeoBot-Net Scan Orchestrator

This script runs inside an ECS task (in the VPC) and orchestrates the scan pipeline.
It receives inputs via environment variables and calls the existing scan_pipeline.py.

Environment Variables:
    PROGRAM_NAME: Name of the program (asset) to scan
    DOMAINS: Comma-separated list of domains (optional if program exists)
    MODULES: Comma-separated list of modules (default: subfinder,dnsx,httpx)
    
    # Injected by ECS task definition:
    SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, REDIS_HOST, etc.
"""
import os
import sys
import asyncio
import logging
from datetime import datetime
from typing import List, Optional
import uuid

# Add backend to Python path
sys.path.insert(0, '/app')

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)
logger = logging.getLogger("orchestrator")


async def ensure_program_exists(
    supabase_client,
    program_name: str,
    domains: List[str]
) -> str:
    """
    Find existing program or create a new one.
    
    Args:
        supabase_client: Supabase service client
        program_name: Name of the program
        domains: List of domains to add
        
    Returns:
        Asset ID (UUID string)
    """
    # Try to find existing program by name
    result = supabase_client.table('assets').select('id').eq('name', program_name).execute()
    
    if result.data and len(result.data) > 0:
        asset_id = result.data[0]['id']
        logger.info(f"📋 Found existing program: {program_name} (ID: {asset_id})")
        
        # Add any new domains
        if domains:
            await add_domains_to_program(supabase_client, asset_id, domains)
        
        return asset_id
    
    # Create new program
    logger.info(f"🆕 Creating new program: {program_name}")
    
    # Use a system user ID for CLI-created programs
    # In LEAN model, user_id is less important since all data is public
    system_user_id = os.environ.get('OPERATOR_USER_ID', '00000000-0000-0000-0000-000000000000')
    
    asset_data = {
        'id': str(uuid.uuid4()),
        'user_id': system_user_id,
        'name': program_name,
        'description': f'Created via CLI on {datetime.utcnow().isoformat()}',
        'is_active': True,
        'priority': 3,  # Medium priority
        'tags': ['cli-created'],
        'created_at': datetime.utcnow().isoformat(),
        'updated_at': datetime.utcnow().isoformat()
    }
    
    insert_result = supabase_client.table('assets').insert(asset_data).execute()
    
    if not insert_result.data:
        raise RuntimeError(f"Failed to create program: {program_name}")
    
    asset_id = insert_result.data[0]['id']
    logger.info(f"✅ Created program: {program_name} (ID: {asset_id})")
    
    # Add domains
    if domains:
        await add_domains_to_program(supabase_client, asset_id, domains)
    
    return asset_id


async def add_domains_to_program(
    supabase_client,
    asset_id: str,
    domains: List[str]
):
    """Add domains to a program (skips existing)."""
    
    # Get existing domains
    existing = supabase_client.table('apex_domains').select('domain').eq('asset_id', asset_id).execute()
    existing_domains = {d['domain'].lower() for d in (existing.data or [])}
    
    # Filter to only new domains
    new_domains = [d for d in domains if d.lower() not in existing_domains]
    
    if not new_domains:
        logger.info(f"📋 All {len(domains)} domains already exist for this program")
        return
    
    # Insert new domains
    domain_records = [
        {
            'id': str(uuid.uuid4()),
            'asset_id': asset_id,
            'domain': domain.lower().strip(),
            'is_active': True,
            'created_at': datetime.utcnow().isoformat(),
            'updated_at': datetime.utcnow().isoformat()
        }
        for domain in new_domains
    ]
    
    supabase_client.table('apex_domains').insert(domain_records).execute()
    logger.info(f"✅ Added {len(new_domains)} new domains (skipped {len(domains) - len(new_domains)} existing)")


async def run_scan_pipeline(
    asset_id: str,
    modules: List[str],
    user_id: str
) -> dict:
    """
    Execute the scan pipeline using existing backend code.
    
    Args:
        asset_id: UUID of the asset to scan
        modules: List of module names
        user_id: User ID for the scan
        
    Returns:
        Pipeline result dictionary
    """
    from app.services.scan_pipeline import ScanPipeline
    from app.schemas.assets import EnhancedAssetScanRequest
    
    # Create scan request
    scan_request = EnhancedAssetScanRequest(
        modules=modules,
        active_domains_only=True
    )
    
    # Create pipeline and execute
    pipeline = ScanPipeline()
    
    result = await pipeline.execute_pipeline(
        asset_id=asset_id,
        modules=modules,
        scan_request=scan_request,
        user_id=user_id
    )
    
    return result


async def main():
    """Main orchestrator entry point."""
    
    logger.info("=" * 60)
    logger.info("🚀 NeoBot-Net Scan Orchestrator Starting")
    logger.info("=" * 60)
    
    # Read environment variables
    program_name = os.environ.get('PROGRAM_NAME')
    domains_str = os.environ.get('DOMAINS', '')
    modules_str = os.environ.get('MODULES', 'subfinder,dnsx,httpx')
    
    if not program_name:
        logger.error("❌ PROGRAM_NAME environment variable is required")
        sys.exit(1)
    
    # Parse domains and modules
    domains = [d.strip() for d in domains_str.split(',') if d.strip()]
    modules = [m.strip() for m in modules_str.split(',') if m.strip()]
    
    logger.info(f"📋 Program: {program_name}")
    logger.info(f"🌐 Domains: {domains if domains else '(use existing)'}")
    logger.info(f"🔧 Modules: {modules}")
    
    # Initialize Supabase client
    from app.core.supabase_client import supabase_client
    client = supabase_client.service_client
    
    # Ensure program exists and get ID
    asset_id = await ensure_program_exists(client, program_name, domains)
    
    # Get operator user ID
    user_id = os.environ.get('OPERATOR_USER_ID', '00000000-0000-0000-0000-000000000000')
    
    # Run the scan pipeline
    logger.info("=" * 60)
    logger.info("🌊 Starting Scan Pipeline")
    logger.info("=" * 60)
    
    start_time = datetime.utcnow()
    
    try:
        result = await run_scan_pipeline(
            asset_id=asset_id,
            modules=modules,
            user_id=user_id
        )
        
        duration = (datetime.utcnow() - start_time).total_seconds()
        
        logger.info("=" * 60)
        logger.info("✅ Scan Pipeline Complete!")
        logger.info(f"   Duration: {duration:.1f}s")
        logger.info(f"   Successful modules: {result.get('successful_modules', 'N/A')}")
        logger.info(f"   Total modules: {result.get('total_modules', 'N/A')}")
        logger.info("=" * 60)
        
    except Exception as e:
        duration = (datetime.utcnow() - start_time).total_seconds()
        logger.error("=" * 60)
        logger.error(f"❌ Scan Pipeline Failed after {duration:.1f}s")
        logger.error(f"   Error: {str(e)}")
        logger.error("=" * 60)
        raise


if __name__ == "__main__":
    asyncio.run(main())


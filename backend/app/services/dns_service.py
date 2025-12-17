"""
DNS Records Service

This service handles all business logic for querying and managing DNS records
discovered by the DNSX module. It provides methods for filtering, pagination,
and retrieval of DNS resolution data.

Key Features:
- Query DNS records by asset or subdomain
- Flexible filtering (record type, date ranges, scan metadata)
- Protected pagination for large datasets (10k+ records)
- Performance-optimized queries using indexed columns

Design Decisions:
- Subdomain queries use subdomain_name (string) for better scalability
- Simple AND filtering only (no OR logic for MVP)
- Protective limits to prevent performance issues with deep pagination
- Authorization handled at API layer (follows existing pattern)
"""

import logging
from datetime import datetime
from typing import List, Dict, Any, Optional
from uuid import UUID

from ..core.supabase_client import supabase_client
from ..schemas.dns import DNSRecord, DNSRecordType
from collections import defaultdict


class DNSService:
    """Service for managing DNS records and queries."""
    
    # Protective pagination constants for performance with 10k+ records
    MAX_LIMIT = 1000      # Maximum records per page
    DEFAULT_LIMIT = 50    # Default if not specified
    MAX_OFFSET = 5000     # Maximum offset to prevent deep pagination
    LARGE_RESULT_THRESHOLD = 10000  # Threshold for warning message
    
    def __init__(self):
        """Initialize DNS service with Supabase client and logging."""
        self.supabase = supabase_client.service_client  # Use service role for backend operations
        self.logger = logging.getLogger(__name__)
        self.logger.info("DNSService initialized")
    
    # ================================================================
    # Validation Methods
    # ================================================================
    
    def _validate_pagination(self, limit: Optional[int], offset: Optional[int]) -> tuple[int, int]:
        """
        Validate and sanitize pagination parameters.
        
        Args:
            limit: Requested records per page
            offset: Requested offset
            
        Returns:
            tuple: (validated_limit, validated_offset)
            
        Raises:
            ValueError: If offset exceeds MAX_OFFSET
        """
        # Validate limit
        if limit is None or limit <= 0:
            limit = self.DEFAULT_LIMIT
        elif limit > self.MAX_LIMIT:
            limit = self.MAX_LIMIT
            
        # Validate offset
        if offset is None or offset < 0:
            offset = 0
        elif offset > self.MAX_OFFSET:
            raise ValueError(
                f"Offset {offset} exceeds maximum allowed offset of {self.MAX_OFFSET}. "
                f"Please use filters to narrow your query instead of deep pagination."
            )
            
        return limit, offset
    
    def _validate_record_type(self, record_type: Optional[str]) -> Optional[str]:
        """
        Validate record_type filter.
        
        Args:
            record_type: Record type to validate
            
        Returns:
            Validated record type or None
            
        Raises:
            ValueError: If record type is invalid
        """
        if record_type is None:
            return None
            
        # Check if valid DNSRecordType
        valid_types = [t.value for t in DNSRecordType]
        if record_type not in valid_types:
            raise ValueError(
                f"Invalid record_type '{record_type}'. "
                f"Valid types: {', '.join(valid_types)}"
            )
            
        return record_type
    
    def _validate_date_filter(self, date_str: Optional[str], field_name: str) -> Optional[str]:
        """
        Validate date filter (ISO format).
        
        Args:
            date_str: Date string to validate (ISO format)
            field_name: Name of the field for error messages
            
        Returns:
            Validated date string or None
            
        Raises:
            ValueError: If date format is invalid
        """
        if date_str is None:
            return None
            
        try:
            # Attempt to parse to validate format
            datetime.fromisoformat(date_str.replace('Z', '+00:00'))
            return date_str
        except ValueError:
            raise ValueError(
                f"Invalid {field_name} format. "
                f"Expected ISO format (e.g., '2025-11-01T00:00:00Z'), got: {date_str}"
            )
    
    # ================================================================
    # Query Builder (DRY Principle)
    # ================================================================
    
    def _build_dns_query(
        self,
        base_query,
        filters: Optional[Dict[str, Any]] = None
    ):
        """
        Build DNS query with filters applied (DRY helper method).
        
        This method applies filters dynamically based on provided parameters,
        using Supabase query chaining. All filters use AND logic.
        
        Args:
            base_query: Base Supabase query to build upon
            filters: Dictionary of filter parameters (optional)
                - record_type: Filter by DNS record type
                - resolved_after: Filter by resolution date (>=)
                - resolved_before: Filter by resolution date (<=)
                - scan_job_id: Filter by scan job UUID
                - batch_scan_id: Filter by batch scan UUID
                
        Returns:
            Query with filters applied
        """
        if filters is None:
            return base_query
            
        query = base_query
        
        # Filter by record_type (indexed column)
        if filters.get('record_type'):
            query = query.eq('record_type', filters['record_type'])
            
        # Filter by resolved_after (date range - indexed column)
        if filters.get('resolved_after'):
            query = query.gte('resolved_at', filters['resolved_after'])
            
        # Filter by resolved_before (date range - indexed column)
        if filters.get('resolved_before'):
            query = query.lte('resolved_at', filters['resolved_before'])
            
        # Filter by scan_job_id (indexed column)
        if filters.get('scan_job_id'):
            query = query.eq('scan_job_id', str(filters['scan_job_id']))
            
        # Filter by batch_scan_id (indexed column)
        if filters.get('batch_scan_id'):
            query = query.eq('batch_scan_id', str(filters['batch_scan_id']))
            
        return query
    
    # ================================================================
    # Core Query Methods
    # ================================================================
    
    async def get_dns_records_by_asset(
        self,
        asset_id: UUID,
        record_type: Optional[str] = None,
        resolved_after: Optional[str] = None,
        resolved_before: Optional[str] = None,
        scan_job_id: Optional[UUID] = None,
        batch_scan_id: Optional[UUID] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Get DNS records for a specific asset with filtering and pagination.
        
        This is the primary method for retrieving DNS records. It queries by asset_id
        (which is indexed) and applies optional filters using AND logic.
        
        Args:
            asset_id: UUID of the asset
            record_type: Filter by DNS record type (A, AAAA, CNAME, MX, TXT)
            resolved_after: Filter by resolution date (ISO format, >= comparison)
            resolved_before: Filter by resolution date (ISO format, <= comparison)
            scan_job_id: Filter by specific scan job UUID
            batch_scan_id: Filter by specific batch scan UUID
            limit: Records per page (default: 50, max: 1000)
            offset: Pagination offset (default: 0, max: 5000)
            
        Returns:
            Dictionary containing:
                - dns_records: List[DNSRecord] - List of DNS record objects
                - total_count: int - Total matching records
                - limit: int - Applied limit
                - offset: int - Applied offset
                - warning: Optional[str] - Warning message for large result sets
                
        Raises:
            ValueError: If filters or pagination parameters are invalid
            
        Example:
            records = await dns_service.get_dns_records_by_asset(
                asset_id=UUID("c1806931-57d0-4f91-9398-e0978d89fb2f"),
                record_type="A",
                limit=100
            )
        """
        try:
            # Validate inputs
            limit, offset = self._validate_pagination(limit, offset)
            record_type = self._validate_record_type(record_type)
            resolved_after = self._validate_date_filter(resolved_after, 'resolved_after')
            resolved_before = self._validate_date_filter(resolved_before, 'resolved_before')
            
            self.logger.info(f"Querying DNS records for asset {asset_id} (limit={limit}, offset={offset})")
            
            # Build filters dictionary
            filters = {
                'record_type': record_type,
                'resolved_after': resolved_after,
                'resolved_before': resolved_before,
                'scan_job_id': scan_job_id,
                'batch_scan_id': batch_scan_id
            }
            
            # Remove None values
            filters = {k: v for k, v in filters.items() if v is not None}
            
            # Build base query (asset_id is indexed)
            base_query = self.supabase.table('dns_records').select('*', count='exact').eq('asset_id', str(asset_id))
            
            # Apply filters using query builder
            query = self._build_dns_query(base_query, filters)
            
            # Apply pagination and ordering
            query = query.order('resolved_at', desc=True).range(offset, offset + limit - 1)
            
            # Execute query
            response = query.execute()
            
            total_count = response.count if response.count is not None else 0
            records = [DNSRecord(**record) for record in response.data] if response.data else []
            
            self.logger.info(f"Found {total_count} DNS records for asset {asset_id} (returned {len(records)})")
            
            # Build result with warning if needed
            result = {
                'dns_records': records,
                'total_count': total_count,
                'limit': limit,
                'offset': offset
            }
            
            # Add warning for large result sets without filters
            if total_count > self.LARGE_RESULT_THRESHOLD and not filters:
                result['warning'] = (
                    f"Large result set ({total_count} records). "
                    f"Consider filtering by record_type or date range for better performance."
                )
            
            return result
            
        except ValueError:
            # Re-raise validation errors
            raise
        except Exception as e:
            self.logger.error(f"Error fetching DNS records for asset {asset_id}: {str(e)}")
            raise
    
    async def get_dns_records_by_subdomain(
        self,
        asset_id: UUID,
        subdomain_name: str,
        record_type: Optional[str] = None,
        resolved_after: Optional[str] = None,
        resolved_before: Optional[str] = None,
        scan_job_id: Optional[UUID] = None,
        batch_scan_id: Optional[UUID] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Get DNS records for a specific subdomain within an asset.
        
        This method queries by subdomain name (string) rather than subdomain_id for
        better scalability. Both asset_id and subdomain are indexed columns.
        
        Args:
            asset_id: UUID of the asset (for scope isolation)
            subdomain_name: Full subdomain name (e.g., "api.epicgames.com")
            record_type: Filter by DNS record type (A, AAAA, CNAME, MX, TXT)
            resolved_after: Filter by resolution date (ISO format, >= comparison)
            resolved_before: Filter by resolution date (ISO format, <= comparison)
            scan_job_id: Filter by specific scan job UUID
            batch_scan_id: Filter by specific batch scan UUID
            limit: Records per page (default: 50, max: 1000)
            offset: Pagination offset (default: 0, max: 5000)
            
        Returns:
            Dictionary containing:
                - dns_records: List[DNSRecord] - List of DNS record objects
                - total_count: int - Total matching records
                - limit: int - Applied limit
                - offset: int - Applied offset
                
        Raises:
            ValueError: If filters or pagination parameters are invalid
            
        Example:
            records = await dns_service.get_dns_records_by_subdomain(
                asset_id=UUID("c1806931-57d0-4f91-9398-e0978d89fb2f"),
                subdomain_name="api.epicgames.com",
                record_type="A"
            )
        """
        try:
            # Validate inputs
            limit, offset = self._validate_pagination(limit, offset)
            record_type = self._validate_record_type(record_type)
            resolved_after = self._validate_date_filter(resolved_after, 'resolved_after')
            resolved_before = self._validate_date_filter(resolved_before, 'resolved_before')
            
            self.logger.info(f"Querying DNS records for subdomain '{subdomain_name}' in asset {asset_id}")
            
            # Build filters dictionary
            filters = {
                'record_type': record_type,
                'resolved_after': resolved_after,
                'resolved_before': resolved_before,
                'scan_job_id': scan_job_id,
                'batch_scan_id': batch_scan_id
            }
            
            # Remove None values
            filters = {k: v for k, v in filters.items() if v is not None}
            
            # Build base query (both asset_id and subdomain are indexed)
            base_query = (self.supabase.table('dns_records')
                         .select('*', count='exact')
                         .eq('asset_id', str(asset_id))
                         .eq('subdomain', subdomain_name))
            
            # Apply filters using query builder
            query = self._build_dns_query(base_query, filters)
            
            # Apply pagination and ordering
            query = query.order('resolved_at', desc=True).range(offset, offset + limit - 1)
            
            # Execute query
            response = query.execute()
            
            total_count = response.count if response.count is not None else 0
            records = [DNSRecord(**record) for record in response.data] if response.data else []
            
            self.logger.info(f"Found {total_count} DNS records for subdomain '{subdomain_name}' (returned {len(records)})")
            
            return {
                'dns_records': records,
                'total_count': total_count,
                'limit': limit,
                'offset': offset
            }
            
        except ValueError:
            # Re-raise validation errors
            raise
        except Exception as e:
            self.logger.error(f"Error fetching DNS records for subdomain '{subdomain_name}': {str(e)}")
            raise
    
    async def get_dns_record_by_id(self, record_id: UUID) -> Optional[DNSRecord]:
        """
        Get a single DNS record by its ID.
        
        This method retrieves a specific DNS record without any filtering.
        Authorization should be handled at the API layer to ensure the user
        owns the associated asset.
        
        Args:
            record_id: UUID of the DNS record
            
        Returns:
            DNSRecord object if found, None otherwise
            
        Raises:
            Exception: If database error occurs
            
        Example:
            record = await dns_service.get_dns_record_by_id(
                UUID("550e8400-e29b-41d4-a716-446655440000")
            )
        """
        try:
            self.logger.info(f"Fetching DNS record {record_id}")
            
            response = (self.supabase.table('dns_records')
                       .select('*')
                       .eq('id', str(record_id))
                       .execute())
            
            if response.data and len(response.data) > 0:
                self.logger.info(f"Found DNS record {record_id}")
                return DNSRecord(**response.data[0])
            else:
                self.logger.info(f"DNS record {record_id} not found")
                return None
                
        except Exception as e:
            self.logger.error(f"Error fetching DNS record {record_id}: {str(e)}")
            raise
    
    async def get_user_dns_records_paginated(
        self,
        user_id: UUID = None,  # Kept for API compatibility but ignored (LEAN architecture)
        page: int = 1,
        per_page: int = 50,
        asset_id: Optional[UUID] = None,
        parent_domain: Optional[str] = None,
        record_type: Optional[str] = None,
        search: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get all DNS records with pagination and filtering.
        
        LEAN Architecture: All authenticated users see ALL data.
        The user_id parameter is kept for API compatibility but ignored.
        
        Query Strategy:
        - JOIN dns_records with assets to get asset_name
        - Apply filters: asset_id, parent_domain, record_type, search
        - Calculate statistics: total_assets, record_type_breakdown
        - Return paginated results with metadata
        
        Args:
            user_id: Kept for API compatibility but ignored (LEAN architecture)
            page: Page number (1-indexed)
            per_page: Records per page (max 100)
            asset_id: Optional filter by specific asset UUID
            parent_domain: Optional filter by parent domain
            record_type: Optional filter by DNS record type
            search: Optional search term (searches subdomain name)
            
        Returns:
            Dictionary containing:
                - dns_records: List[DNSRecordWithAssetInfo] - DNS records with asset names
                - pagination: Pagination metadata (total, page, per_page, etc.)
                - filters: Applied filters
                - stats: Statistics (total_assets, filtered_count, record_type_breakdown)
                
        Raises:
            ValueError: If pagination or filter parameters are invalid
            
        Example:
            result = await dns_service.get_user_dns_records_paginated(
                page=1,
                per_page=50,
                record_type="A",
                search="api"
            )
        """
        try:
            # Validate pagination
            page = max(1, page)
            per_page = min(max(1, per_page), 100)  # Cap at 100
            offset = (page - 1) * per_page
            
            # Validate record_type if provided
            if record_type:
                record_type = self._validate_record_type(record_type)
            
            self.logger.info(
                f"Fetching DNS records (page={page}, per_page={per_page}, "
                f"asset_id={asset_id}, parent_domain={parent_domain}, record_type={record_type}, search={search})"
            )
            
            # LEAN Architecture: Get ALL assets (no user_id filter)
            assets_response = (self.supabase.table('assets')
                              .select('id, name')
                              .execute())
            
            if not assets_response.data:
                # No assets in system, return empty result
                self.logger.info("No assets found in system")
                return {
                    'dns_records': [],
                    'pagination': {
                        'total': 0,
                        'page': 1,
                        'per_page': per_page,
                        'total_pages': 1,
                        'has_next': False,
                        'has_prev': False
                    },
                    'filters': {
                        'asset_id': str(asset_id) if asset_id else None,
                        'parent_domain': parent_domain,
                        'record_type': record_type,
                        'search': search
                    },
                    'stats': {
                        'total_assets': 0,
                        'filtered_count': 0,
                        'record_type_breakdown': {}
                    }
                }
            
            # Build asset_id -> asset_name mapping
            asset_map = {asset['id']: asset['name'] for asset in assets_response.data}
            all_asset_ids = list(asset_map.keys())
            
            # Step 2: Build DNS query for ALL assets
            query = (self.supabase.table('dns_records')
                    .select('*', count='exact')
                    .in_('asset_id', all_asset_ids))
            
            # Apply additional filters
            if asset_id:
                query = query.eq('asset_id', str(asset_id))
            
            if parent_domain:
                query = query.eq('parent_domain', parent_domain)
            
            if record_type:
                query = query.eq('record_type', record_type)
            
            if search:
                # Search in subdomain name (case-insensitive)
                query = query.ilike('subdomain', f'%{search}%')
            
            # Step 3: Get total count (for pagination metadata)
            count_query = query
            count_response = count_query.execute()
            total_count = count_response.count if count_response.count is not None else 0
            
            # Step 4: Apply pagination and ordering
            query = query.order('resolved_at', desc=True).range(offset, offset + per_page - 1)
            
            # Execute paginated query
            response = query.execute()
            
            # Step 5: Enrich DNS records with asset names
            dns_records = []
            for record in response.data:
                # Add asset_name from our asset_map
                asset_name = asset_map.get(record['asset_id'], 'Unknown')
                dns_records.append({
                    'id': record['id'],
                    'subdomain': record['subdomain'],
                    'parent_domain': record['parent_domain'],
                    'record_type': record['record_type'],
                    'record_value': record['record_value'],
                    'ttl': record.get('ttl'),
                    'priority': record.get('priority'),
                    'resolved_at': record['resolved_at'],
                    'cloud_provider': record.get('cloud_provider'),
                    'scan_job_id': record.get('scan_job_id'),
                    'batch_scan_id': record.get('batch_scan_id'),
                    'asset_id': record['asset_id'],
                    'created_at': record['created_at'],
                    'updated_at': record['updated_at'],
                    'asset_name': asset_name
                })
            
            # Step 6: Calculate statistics
            # Determine which assets have DNS records (filtered)
            unique_asset_ids = set()
            for record in response.data:
                unique_asset_ids.add(record['asset_id'])
            
            total_assets = len(unique_asset_ids) if asset_id is None else 1
            
            # Get record type breakdown
            record_type_breakdown = {}
            for record in response.data:
                rt = record['record_type']
                record_type_breakdown[rt] = record_type_breakdown.get(rt, 0) + 1
            
            # Build pagination metadata
            total_pages = (total_count + per_page - 1) // per_page if total_count > 0 else 1
            
            pagination = {
                'total': total_count,
                'page': page,
                'per_page': per_page,
                'total_pages': total_pages,
                'has_next': page < total_pages,
                'has_prev': page > 1
            }
            
            # Build filters metadata
            filters_metadata = {
                'asset_id': str(asset_id) if asset_id else None,
                'parent_domain': parent_domain,
                'record_type': record_type,
                'search': search
            }
            
            # Build stats
            stats = {
                'total_assets': total_assets,
                'filtered_count': total_count,
                'record_type_breakdown': record_type_breakdown
            }
            
            self.logger.info(
                f"Returning {len(dns_records)} DNS records (total: {total_count}, page: {page}/{total_pages})"
            )
            
            return {
                'dns_records': dns_records,
                'pagination': pagination,
                'filters': filters_metadata,
                'stats': stats
            }
            
        except ValueError:
            # Re-raise validation errors
            raise
        except Exception as e:
            self.logger.error(f"Error fetching DNS records: {str(e)}")
            raise
    
    async def get_user_dns_records_paginated_grouped(
        self,
        user_id: UUID = None,  # Kept for API compatibility but ignored (LEAN architecture)
        page: int = 1,
        per_page: int = 50,
        asset_id: Optional[UUID] = None,
        parent_domain: Optional[str] = None,
        record_type: Optional[str] = None,
        search: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get DNS records grouped by subdomain for elegant UI display.
        
        LEAN Architecture: All authenticated users see ALL data.
        
        This method aggregates all DNS records by subdomain and organizes
        them by record type (A, AAAA, CNAME, MX, TXT). Pagination is applied
        to the subdomain count, not individual record count.
        
        Query Strategy:
        1. Fetch all DNS records for user with filters (no pagination yet)
        2. Group records by subdomain in memory (Python aggregation)
        3. Organize records by type within each subdomain
        4. Sort grouped subdomains by last_resolved (most recent first)
        5. Apply pagination to grouped subdomains
        6. Return structured grouped data
        
        Args:
            user_id: UUID of the user
            page: Page number (1-indexed)
            per_page: Subdomains per page (not record count)
            asset_id: Optional filter by asset UUID
            parent_domain: Optional filter by parent domain
            record_type: Optional filter by DNS record type
            search: Optional search term (subdomain name)
            
        Returns:
            Dictionary containing:
                - grouped_records: List[GroupedDNSRecord] - Subdomains with grouped DNS
                - pagination: Pagination metadata (total = subdomain count)
                - filters: Applied filters
                - stats: total_subdomains, total_dns_records, record_type_breakdown
                
        Example:
            result = await dns_service.get_user_dns_records_paginated_grouped(
                user_id=UUID("..."),
                page=1,
                per_page=50,
                record_type="A",
                search="api"
            )
        """
        try:
            # Validate pagination
            page = max(1, page)
            per_page = min(max(1, per_page), 100)  # Cap at 100 subdomains per page
            
            # Validate record_type if provided
            if record_type:
                record_type = self._validate_record_type(record_type)
            
            self.logger.info(
                f"Fetching grouped DNS records (page={page}, per_page={per_page}, "
                f"asset_id={asset_id}, parent_domain={parent_domain}, record_type={record_type}, search={search})"
            )
            
            # LEAN Architecture: Get ALL assets (no user_id filter)
            assets_response = (self.supabase.table('assets')
                              .select('id, name')
                              .execute())
            
            if not assets_response.data:
                # No assets in system, return empty result
                return {
                    'grouped_records': [],
                    'pagination': {
                        'total': 0,
                        'page': 1,
                        'per_page': per_page,
                        'total_pages': 1,
                        'has_next': False,
                        'has_prev': False
                    },
                    'filters': {
                        'asset_id': str(asset_id) if asset_id else None,
                        'parent_domain': parent_domain,
                        'record_type': record_type,
                        'search': search
                    },
                    'stats': {
                        'total_subdomains': 0,
                        'total_dns_records': 0,
                        'total_assets': 0,
                        'record_type_breakdown': {}
                    }
                }
            
            # Build asset_id -> asset_name mapping
            asset_map = {asset['id']: asset['name'] for asset in assets_response.data}
            all_asset_ids = list(asset_map.keys())
            
            # Step 2: Fetch ALL DNS records with filters (no pagination yet - we paginate after grouping)
            query = (self.supabase.table('dns_records')
                    .select('*')
                    .in_('asset_id', all_asset_ids))
            
            # Apply filters
            if asset_id:
                query = query.eq('asset_id', str(asset_id))
            
            if parent_domain:
                query = query.eq('parent_domain', parent_domain)
            
            if record_type:
                query = query.eq('record_type', record_type)
            
            if search:
                query = query.ilike('subdomain', f'%{search}%')
            
            # Order by resolved_at for consistency
            query = query.order('resolved_at', desc=True)
            
            # Execute query (fetch all matching records)
            response = query.execute()
            
            if not response.data:
                # No records found
                return {
                    'grouped_records': [],
                    'pagination': {
                        'total': 0,
                        'page': 1,
                        'per_page': per_page,
                        'total_pages': 1,
                        'has_next': False,
                        'has_prev': False
                    },
                    'filters': {
                        'asset_id': str(asset_id) if asset_id else None,
                        'parent_domain': parent_domain,
                        'record_type': record_type,
                        'search': search
                    },
                    'stats': {
                        'total_subdomains': 0,
                        'total_dns_records': 0,
                        'total_assets': len(all_asset_ids) if asset_id is None else 1,
                        'record_type_breakdown': {}
                    }
                }
            
            # Step 3: Group records by subdomain
            # Structure: {subdomain: {metadata, records_by_type: {A: [], AAAA: [], ...}}}
            grouped = defaultdict(lambda: {
                'subdomain': '',
                'parent_domain': '',
                'asset_name': '',
                'asset_id': '',
                'total_records': 0,
                'last_resolved': None,
                'records_by_type': {
                    'A': [],
                    'AAAA': [],
                    'CNAME': [],
                    'MX': [],
                    'TXT': []
                }
            })
            
            total_dns_records = 0
            record_type_breakdown = defaultdict(int)
            
            for record in response.data:
                subdomain_key = record['subdomain']
                record_type_key = record['record_type']
                
                # Initialize subdomain metadata (first record for this subdomain)
                if not grouped[subdomain_key]['subdomain']:
                    grouped[subdomain_key]['subdomain'] = record['subdomain']
                    grouped[subdomain_key]['parent_domain'] = record['parent_domain']
                    grouped[subdomain_key]['asset_name'] = asset_map.get(record['asset_id'], 'Unknown')
                    grouped[subdomain_key]['asset_id'] = record['asset_id']
                    grouped[subdomain_key]['last_resolved'] = record['resolved_at']
                
                # Update last_resolved if this record is more recent
                if record['resolved_at'] > grouped[subdomain_key]['last_resolved']:
                    grouped[subdomain_key]['last_resolved'] = record['resolved_at']
                
                # Add record to appropriate type list
                record_detail = {
                    'id': record['id'],
                    'record_value': record['record_value'],
                    'ttl': record.get('ttl'),
                    'priority': record.get('priority'),
                    'resolved_at': record['resolved_at'],
                    'cloud_provider': record.get('cloud_provider')
                }
                
                grouped[subdomain_key]['records_by_type'][record_type_key].append(record_detail)
                grouped[subdomain_key]['total_records'] += 1
                
                total_dns_records += 1
                record_type_breakdown[record_type_key] += 1
            
            # Step 4: Convert to list and sort by last_resolved (most recent first)
            grouped_list = list(grouped.values())
            grouped_list.sort(key=lambda x: x['last_resolved'], reverse=True)
            
            # Step 5: Apply pagination to grouped subdomains
            total_subdomains = len(grouped_list)
            total_pages = (total_subdomains + per_page - 1) // per_page if total_subdomains > 0 else 1
            
            # Calculate offset for current page
            offset = (page - 1) * per_page
            paginated_grouped = grouped_list[offset:offset + per_page]
            
            # Step 6: Build pagination metadata
            pagination = {
                'total': total_subdomains,
                'page': page,
                'per_page': per_page,
                'total_pages': total_pages,
                'has_next': page < total_pages,
                'has_prev': page > 1
            }
            
            # Build filters metadata
            filters_metadata = {
                'asset_id': str(asset_id) if asset_id else None,
                'parent_domain': parent_domain,
                'record_type': record_type,
                'search': search
            }
            
            # Build stats
            stats = {
                'total_subdomains': total_subdomains,
                'total_dns_records': total_dns_records,
                'total_assets': len(all_asset_ids) if asset_id is None else 1,
                'record_type_breakdown': dict(record_type_breakdown)
            }
            
            self.logger.info(
                f"Returning {len(paginated_grouped)} grouped subdomains "
                f"(total: {total_subdomains}, page: {page}/{total_pages})"
            )
            
            return {
                'grouped_records': paginated_grouped,
                'pagination': pagination,
                'filters': filters_metadata,
                'stats': stats
            }
            
        except ValueError:
            # Re-raise validation errors
            raise
        except Exception as e:
            self.logger.error(f"Error fetching grouped DNS records: {str(e)}")
            raise


# Create singleton instance
dns_service = DNSService()

"""
Stream Coordinator Service

Manages Redis Streams-based scan pipelines for real-time processing.
Coordinates producer (Subfinder) and consumer (DNSx) launches, monitors
stream health, and handles completion detection.

Author: Pluckware Development Team
Date: November 8, 2025
"""

import asyncio
import logging
import uuid
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import redis.asyncio as redis

from app.core.config import settings
from app.schemas.batch import BatchScanJob

logger = logging.getLogger(__name__)


class StreamCoordinator:
    """
    Coordinates Redis Streams-based scan pipelines.
    
    Responsibilities:
    - Generate unique stream keys for scan jobs
    - Manage consumer group lifecycle
    - Monitor stream health and progress
    - Detect completion markers
    - Clean up streams after completion
    """
    
    def __init__(self):
        self.redis_client: Optional[redis.Redis] = None
        
    async def get_redis(self) -> redis.Redis:
        """Get or create async Redis connection."""
        if not self.redis_client:
            try:
                self.redis_client = redis.Redis(
                    host=getattr(settings, 'redis_host', 'localhost'),
                    port=getattr(settings, 'redis_port', 6379),
                    decode_responses=True,
                    socket_timeout=10,
                    socket_connect_timeout=10
                )
                await self.redis_client.ping()
                logger.info("✅ StreamCoordinator: Redis connection established")
            except Exception as e:
                logger.error(f"❌ StreamCoordinator: Redis connection failed: {str(e)}")
                raise
        return self.redis_client
    
    def generate_stream_key(self, scan_job_id: str, producer_module: str) -> str:
        """
        Generate unique stream key for a scan job.
        
        Format: scan:{scan_job_id}:{producer_module}:output
        Example: scan:c1806931-57d0-4f91-9398-e0978d89fb2f:subfinder:output
        
        Args:
            scan_job_id: Unique scan job identifier
            producer_module: Name of producer module (e.g., "subfinder")
            
        Returns:
            Redis Stream key
        """
        stream_key = f"scan:{scan_job_id}:{producer_module}:output"
        logger.info(f"📋 Generated stream key: {stream_key}")
        return stream_key
    
    def generate_consumer_group_name(self, consumer_module: str) -> str:
        """
        Generate consumer group name for a module.
        
        Format: {consumer_module}-consumers
        Example: dnsx-consumers
        
        Args:
            consumer_module: Name of consumer module (e.g., "dnsx")
            
        Returns:
            Consumer group name
        """
        return f"{consumer_module}-consumers"
    
    def generate_consumer_name(self, consumer_module: str, task_id: Optional[str] = None) -> str:
        """
        Generate unique consumer name for a task.
        
        Format: {consumer_module}-{task_id or uuid}
        Example: dnsx-abc123 or dnsx-uuid
        
        Args:
            consumer_module: Name of consumer module (e.g., "dnsx")
            task_id: Optional ECS task ID (will generate UUID if not provided)
            
        Returns:
            Unique consumer name
        """
        if not task_id:
            task_id = str(uuid.uuid4())[:8]
        return f"{consumer_module}-{task_id}"
    
    async def create_consumer_group(
        self, 
        stream_key: str, 
        consumer_group_name: str
    ) -> bool:
        """
        Create consumer group for a stream (idempotent).
        
        Creates the consumer group starting from the beginning (ID "0").
        If the group already exists, returns success without error.
        
        Args:
            stream_key: Redis Stream key
            consumer_group_name: Consumer group name
            
        Returns:
            True if successful, False otherwise
        """
        try:
            redis_client = await self.get_redis()
            
            # XGROUP CREATE with MKSTREAM (creates stream if doesn't exist)
            await redis_client.execute_command(
                'XGROUP', 'CREATE', stream_key, consumer_group_name, '0', 'MKSTREAM'
            )
            
            logger.info(f"✅ Consumer group created: {consumer_group_name} for stream {stream_key}")
            return True
            
        except redis.ResponseError as e:
            # BUSYGROUP means group already exists - this is fine (idempotent)
            if 'BUSYGROUP' in str(e):
                logger.info(f"✅ Consumer group already exists: {consumer_group_name}")
                return True
            else:
                logger.error(f"❌ Failed to create consumer group: {str(e)}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Unexpected error creating consumer group: {str(e)}")
            return False
    
    async def get_stream_info(self, stream_key: str) -> Optional[Dict[str, Any]]:
        """
        Get stream information (length, consumer groups, etc.).
        
        Args:
            stream_key: Redis Stream key
            
        Returns:
            Dictionary with stream info or None if stream doesn't exist
        """
        try:
            redis_client = await self.get_redis()
            
            # Get stream length
            stream_length = await redis_client.xlen(stream_key)
            
            # Get consumer groups
            try:
                groups_info = await redis_client.execute_command('XINFO', 'GROUPS', stream_key)
                # Parse groups info (comes as flat list)
                groups = []
                if groups_info:
                    for i in range(0, len(groups_info), 2):
                        group_data = {}
                        group_details = groups_info[i + 1]
                        for j in range(0, len(group_details), 2):
                            key = group_details[j].decode() if isinstance(group_details[j], bytes) else group_details[j]
                            value = group_details[j + 1]
                            group_data[key] = value
                        groups.append(group_data)
            except:
                groups = []
            
            return {
                "stream_key": stream_key,
                "length": stream_length,
                "groups": groups,
                "exists": stream_length >= 0
            }
            
        except Exception as e:
            logger.error(f"❌ Failed to get stream info: {str(e)}")
            return None
    
    async def check_completion_marker(self, stream_key: str) -> bool:
        """
        Check if completion marker exists in stream.
        
        Reads the last message in the stream and checks if it's a completion marker
        (type: "completion").
        
        Args:
            stream_key: Redis Stream key
            
        Returns:
            True if completion marker found, False otherwise
        """
        try:
            redis_client = await self.get_redis()
            
            # Read last message from stream (XREVRANGE with COUNT 1)
            messages = await redis_client.xrevrange(stream_key, count=1)
            
            if not messages:
                return False
            
            # Check if last message is completion marker
            message_id, message_data = messages[0]
            message_type = message_data.get('type', '')
            
            is_completion = message_type == 'completion'
            
            if is_completion:
                logger.info(f"🏁 Completion marker found in stream: {stream_key}")
                total_results = message_data.get('total_results', 'unknown')
                logger.info(f"   Total results: {total_results}")
            
            return is_completion
            
        except Exception as e:
            logger.error(f"❌ Failed to check completion marker: {str(e)}")
            return False
    
    async def get_pending_count(
        self, 
        stream_key: str, 
        consumer_group_name: str
    ) -> Optional[int]:
        """
        Get count of pending (unacknowledged) messages in consumer group.
        
        Args:
            stream_key: Redis Stream key
            consumer_group_name: Consumer group name
            
        Returns:
            Number of pending messages, or None if error
        """
        try:
            redis_client = await self.get_redis()
            
            # XPENDING summary
            pending_info = await redis_client.execute_command(
                'XPENDING', stream_key, consumer_group_name
            )
            
            if not pending_info or len(pending_info) == 0:
                return 0
            
            # First element is pending count
            pending_count = pending_info[0]
            
            logger.debug(f"📊 Pending messages in {consumer_group_name}: {pending_count}")
            return pending_count
            
        except Exception as e:
            logger.error(f"❌ Failed to get pending count: {str(e)}")
            return None
    
    async def monitor_stream_progress(
        self,
        stream_key: str,
        consumer_group_name: str,
        check_interval: int = 5,
        timeout: int = 3600
    ) -> Dict[str, Any]:
        """
        Monitor stream processing progress until completion.
        
        Continuously checks for:
        1. Completion marker in stream
        2. No pending messages in consumer group
        3. Timeout exceeded
        
        Args:
            stream_key: Redis Stream key to monitor
            consumer_group_name: Consumer group to check
            check_interval: Seconds between checks (default: 5)
            timeout: Max time to wait in seconds (default: 3600 = 1 hour)
            
        Returns:
            Dictionary with completion status and statistics
        """
        start_time = datetime.now()
        max_wait = timedelta(seconds=timeout)
        
        logger.info(f"🔍 Monitoring stream progress: {stream_key}")
        logger.info(f"   Consumer group: {consumer_group_name}")
        logger.info(f"   Check interval: {check_interval}s, Timeout: {timeout}s")
        
        while True:
            # Check timeout
            elapsed = datetime.now() - start_time
            if elapsed > max_wait:
                logger.warning(f"⚠️  Stream monitoring timeout ({timeout}s) exceeded")
                return {
                    "status": "timeout",
                    "elapsed_seconds": elapsed.total_seconds(),
                    "stream_key": stream_key
                }
            
            # Check for completion marker
            has_completion = await self.check_completion_marker(stream_key)
            
            # Check pending messages
            pending_count = await self.get_pending_count(stream_key, consumer_group_name)
            
            # Get stream info
            stream_info = await self.get_stream_info(stream_key)
            stream_length = stream_info.get('length', 0) if stream_info else 0
            
            logger.info(
                f"📊 Progress check: completion={has_completion}, "
                f"pending={pending_count}, stream_length={stream_length}, "
                f"elapsed={int(elapsed.total_seconds())}s"
            )
            
            # Check if processing is complete
            if has_completion and (pending_count == 0 or pending_count is None):
                logger.info(f"✅ Stream processing complete: {stream_key}")
                return {
                    "status": "complete",
                    "elapsed_seconds": elapsed.total_seconds(),
                    "stream_key": stream_key,
                    "stream_length": stream_length,
                    "pending_count": pending_count
                }
            
            # Wait before next check
            await asyncio.sleep(check_interval)
    
    async def cleanup_stream(
        self,
        stream_key: str,
        delete_stream: bool = False
    ) -> bool:
        """
        Clean up stream resources after completion.
        
        Optionally deletes the stream. By default, keeps the stream for debugging.
        
        Args:
            stream_key: Redis Stream key
            delete_stream: If True, delete the stream (default: False)
            
        Returns:
            True if successful, False otherwise
        """
        try:
            redis_client = await self.get_redis()
            
            if delete_stream:
                # Delete the entire stream
                await redis_client.delete(stream_key)
                logger.info(f"🧹 Stream deleted: {stream_key}")
            else:
                # Just log that we're keeping the stream
                logger.info(f"💾 Stream retained for debugging: {stream_key}")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to cleanup stream: {str(e)}")
            return False
    
    async def close(self):
        """Close Redis connection."""
        if self.redis_client:
            await self.redis_client.close()
            logger.info("🔌 StreamCoordinator: Redis connection closed")


# Singleton instance
stream_coordinator = StreamCoordinator()

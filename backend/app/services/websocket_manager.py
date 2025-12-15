"""
WebSocket Manager for Real-time Batch Progress Updates
====================================================

Manages WebSocket connections and provides real-time progress updates
for batch scan operations using Redis pub/sub for scalability.
"""

import asyncio
import json
import logging
from typing import Dict, Set, List, Optional, Any
import redis.asyncio as redis
from redis.exceptions import ConnectionError, TimeoutError, RedisError
from ..core.config import settings
from ..utils.json_encoder import safe_json_dumps

logger = logging.getLogger(__name__)

class BatchProgressNotifier:
    """
    Environment-aware Redis-based batch progress notifier for WebSocket communication.
    
    Automatically handles connection differences between:
    - Local development (localhost Redis)
    - Cloud production (ElastiCache in VPC)
    """
    
    def __init__(self):
        self.redis_client: Optional[redis.Redis] = None
        self.is_connected = False
        self.connection_attempts = 0
        self.max_retries = 3 if settings.is_local_environment else 5
        
    async def initialize_redis(self):
        """
        Initialize Redis connection with environment-aware configuration and retry logic.
        """
        logger.info(f"🔄 Initializing Redis connection for {settings.environment} environment...")
        logger.info(f"🔗 Redis URL: {settings.redis_url}")
        logger.info(f"📍 Environment Detection: Local={settings.is_local_environment}, Cloud={settings.is_cloud_environment}")
        
        for attempt in range(1, self.max_retries + 1):
            try:
                # Create Redis client with environment-appropriate configuration
                if settings.is_local_environment:
                    # Local development - simple connection
                    self.redis_client = redis.from_url(
                        settings.redis_url,
                        socket_timeout=5,
                        socket_connect_timeout=5,
                        decode_responses=True
                    )
                    logger.info("🏠 Using local Redis configuration")
                else:
                    # Cloud environment - use infrastructure configuration (no duplicate params)
                    logger.info(f"🔧 Cloud Redis kwargs: {settings.redis_connection_kwargs}")
                    self.redis_client = redis.Redis(**settings.redis_connection_kwargs)
                    logger.info("☁️  Using cloud Redis configuration (ElastiCache)")
                
                # Test the connection
                await self.redis_client.ping()
                self.is_connected = True
                logger.info(f"✅ Redis connection established successfully (attempt {attempt}/{self.max_retries})")
                
                # Log connection details for debugging
                if settings.is_local_environment:
                    logger.info("🔧 Local Redis: Ready for WebSocket batch progress notifications")
                else:
                    logger.info(f"🔧 Cloud Redis: Connected to {settings.redis_host}:{settings.redis_port}")
                
                return
                
            except (ConnectionError, TimeoutError) as e:
                self.connection_attempts = attempt
                logger.warning(f"⚠️  Redis connection attempt {attempt}/{self.max_retries} failed: {str(e)}")
                
                if attempt < self.max_retries:
                    wait_time = 2 ** attempt  # Exponential backoff
                    logger.info(f"⏳ Retrying in {wait_time} seconds...")
                    await asyncio.sleep(wait_time)
                else:
                    logger.error(f"❌ Failed to connect to Redis after {self.max_retries} attempts")
                    self.is_connected = False
                    
                    # Provide environment-specific troubleshooting guidance
                    if settings.is_local_environment:
                        logger.error("🔧 Local troubleshooting:")
                        logger.error("   - Ensure Redis is running: redis-server")
                        logger.error("   - Check if Redis is accessible: redis-cli ping")
                        logger.error("   - Verify Docker network configuration")
                    else:
                        logger.error("🔧 Cloud troubleshooting:")
                        logger.error(f"   - Check ElastiCache endpoint: {settings.redis_host}")
                        logger.error("   - Verify VPC security group rules")
                        logger.error("   - Confirm ECS task subnet can reach private subnet")
                    
                    raise e
                    
            except RedisError as e:
                logger.error(f"❌ Redis configuration error: {str(e)}")
                raise e
            except Exception as e:
                logger.error(f"❌ Unexpected error during Redis initialization: {str(e)}")
                raise e

    async def notify_batch_started(self, batch_id: str, user_id: str, batch_info: Dict[str, Any]):
        """Send batch started notification via Redis pub/sub."""
        if not self.is_connected:
            logger.warning("⚠️  Redis not connected, skipping batch started notification")
            return
            
        try:
            message = {
                "type": "batch_started",
                "batch_id": batch_id,
                "user_id": user_id,
                "timestamp": asyncio.get_event_loop().time(),
                "data": batch_info
            }
            
            # Publish to user-specific channel
            channel = f"batch_progress:{user_id}"
            await self.redis_client.publish(channel, safe_json_dumps(message))
            
            logger.info(f"📢 Batch started notification sent: {batch_id} for user {user_id}")
            
        except Exception as e:
            logger.error(f"❌ Failed to send batch started notification: {str(e)}")

    async def notify_batch_progress(self, batch_id: str, user_id: str, progress_data: Dict[str, Any]):
        """
        Send batch progress update via Redis pub/sub.
        
        NOTE (2025-10-07): Currently not actively used in scan workflow.
        Reserved for future multi-module tracking system where intermediate
        progress updates will be useful (e.g., per-module completion status).
        Frontend simplified to only show "Scan Started!" message.
        """
        if not self.is_connected:
            return
            
        try:
            message = {
                "type": "batch_progress",
                "batch_id": batch_id,
                "user_id": user_id,
                "timestamp": asyncio.get_event_loop().time(),
                "data": progress_data
            }
            
            channel = f"batch_progress:{user_id}"
            await self.redis_client.publish(channel, safe_json_dumps(message))
            
        except Exception as e:
            logger.error(f"❌ Failed to send batch progress notification: {str(e)}")

    async def notify_batch_completed(self, batch_id: str, user_id: str, results: Dict[str, Any]):
        """Send batch completion notification via Redis pub/sub."""
        if not self.is_connected:
            logger.warning("⚠️  Redis not connected, skipping batch completed notification")
            return
            
        try:
            message = {
                "type": "batch_completed",
                "batch_id": batch_id,
                "user_id": user_id,
                "timestamp": asyncio.get_event_loop().time(),
                "data": results
            }
            
            channel = f"batch_progress:{user_id}"
            await self.redis_client.publish(channel, safe_json_dumps(message))
            
            logger.info(f"🎉 Batch completed notification sent: {batch_id} for user {user_id}")
            
        except Exception as e:
            logger.error(f"❌ Failed to send batch completed notification: {str(e)}")

    async def notify_batch_failed(self, batch_id: str, user_id: str, error: str):
        """Send batch failure notification via Redis pub/sub."""
        if not self.is_connected:
            logger.warning("⚠️  Redis not connected, skipping batch failed notification")
            return
            
        try:
            message = {
                "type": "batch_failed",
                "batch_id": batch_id,
                "user_id": user_id,
                "timestamp": asyncio.get_event_loop().time(),
                "data": {"error": error}
            }
            
            channel = f"batch_progress:{user_id}"
            await self.redis_client.publish(channel, safe_json_dumps(message))
            
            logger.error(f"💥 Batch failed notification sent: {batch_id} for user {user_id}")
            
        except Exception as e:
            logger.error(f"❌ Failed to send batch failed notification: {str(e)}")

    async def notify_scan_error(self, user_id: str, error_type: str, error_message: str, context: Optional[Dict[str, Any]] = None):
        """Send detailed scan error notification with categorization and context."""
        if not self.is_connected:
            logger.warning("⚠️  Redis not connected, skipping scan error notification")
            return
            
        try:
            # Categorize error for better user experience
            error_category = self._categorize_error(error_type, error_message)
            user_friendly_message = self._get_user_friendly_message(error_category, error_message)
            suggested_actions = self._get_suggested_actions(error_category)
            
            message = {
                "type": "scan_error",
                "user_id": user_id,
                "timestamp": asyncio.get_event_loop().time(),
                "data": {
                    "error_type": error_type,
                    "error_category": error_category,
                    "original_message": error_message,
                    "user_friendly_message": user_friendly_message,
                    "suggested_actions": suggested_actions,
                    "context": context or {},
                    "severity": self._get_error_severity(error_category),
                    "retry_recommended": self._is_retry_recommended(error_category)
                }
            }
            
            channel = f"batch_progress:{user_id}"
            await self.redis_client.publish(channel, safe_json_dumps(message))
            
            logger.error(f"🚨 Scan error notification sent to user {user_id}: {error_category}")
            
        except Exception as e:
            logger.error(f"❌ Failed to send scan error notification: {str(e)}")

    async def notify_container_health_issue(self, user_id: str, container_id: str, health_issue: str, metrics: Dict[str, Any]):
        """Send container health issue notification with performance context."""
        if not self.is_connected:
            logger.warning("⚠️  Redis not connected, skipping health issue notification")
            return
            
        try:
            message = {
                "type": "container_health_issue",
                "user_id": user_id,
                "timestamp": asyncio.get_event_loop().time(),
                "data": {
                    "container_id": container_id,
                    "health_issue": health_issue,
                    "performance_metrics": metrics,
                    "severity": self._assess_health_severity(health_issue, metrics),
                    "recommended_actions": self._get_health_recommendations(health_issue, metrics)
                }
            }
            
            channel = f"batch_progress:{user_id}"
            await self.redis_client.publish(channel, safe_json_dumps(message))
            
            logger.warning(f"🏥 Container health issue notification sent: {container_id}")
            
        except Exception as e:
            logger.error(f"❌ Failed to send health issue notification: {str(e)}")

    async def notify_performance_alert(self, user_id: str, alert_type: str, metrics: Dict[str, Any], threshold_exceeded: str):
        """Send performance alert when thresholds are exceeded."""
        if not self.is_connected:
            logger.warning("⚠️  Redis not connected, skipping performance alert")
            return
            
        try:
            message = {
                "type": "performance_alert",
                "user_id": user_id,
                "timestamp": asyncio.get_event_loop().time(),
                "data": {
                    "alert_type": alert_type,
                    "threshold_exceeded": threshold_exceeded,
                    "current_metrics": metrics,
                    "severity": self._get_performance_severity(alert_type, metrics),
                    "impact_assessment": self._assess_performance_impact(alert_type, metrics),
                    "optimization_suggestions": self._get_optimization_suggestions(alert_type, metrics)
                }
            }
            
            channel = f"batch_progress:{user_id}"
            await self.redis_client.publish(channel, safe_json_dumps(message))
            
            logger.warning(f"⚡ Performance alert sent to user {user_id}: {alert_type}")
            
        except Exception as e:
            logger.error(f"❌ Failed to send performance alert: {str(e)}")

    def _categorize_error(self, error_type: str, error_message: str) -> str:
        """Categorize errors for better user experience."""
        error_message_lower = error_message.lower()
        
        if "timeout" in error_message_lower or "deadline exceeded" in error_message_lower:
            return "timeout"
        elif "connection" in error_message_lower or "network" in error_message_lower:
            return "network"
        elif "rate limit" in error_message_lower or "429" in error_message_lower:
            return "rate_limit"
        elif "authentication" in error_message_lower or "unauthorized" in error_message_lower:
            return "authentication"
        elif "memory" in error_message_lower or "out of memory" in error_message_lower:
            return "resource_exhaustion"
        elif "dns" in error_message_lower or "resolution" in error_message_lower:
            return "dns_resolution"
        elif "invalid" in error_message_lower or "validation" in error_message_lower:
            return "validation"
        elif "database" in error_message_lower or "sql" in error_message_lower:
            return "database"
        else:
            return "unknown"

    def _get_user_friendly_message(self, error_category: str, original_message: str) -> str:
        """Convert technical error messages to user-friendly explanations."""
        messages = {
            "timeout": "The scan took longer than expected to complete. This might be due to a large number of domains or slow network responses.",
            "network": "There was a network connectivity issue while performing the scan. Please check your internet connection.",
            "rate_limit": "The scan was temporarily slowed down due to rate limiting from external services. This is normal for large scans.",
            "authentication": "There was an authentication issue with one of the scanning services. This might affect some results.",
            "resource_exhaustion": "The scanner ran out of available memory or CPU resources. Consider scanning fewer domains at once.",
            "dns_resolution": "Some domains could not be resolved. This might indicate invalid domains or DNS configuration issues.",
            "validation": "There was an issue with the scan configuration or domain format. Please check your input parameters.",
            "database": "There was an issue storing scan results to the database. The scan may have completed but results might be incomplete.",
            "unknown": f"An unexpected error occurred: {original_message[:100]}..."
        }
        return messages.get(error_category, messages["unknown"])

    def _get_suggested_actions(self, error_category: str) -> List[str]:
        """Provide actionable suggestions based on error category."""
        suggestions = {
            "timeout": [
                "Try scanning fewer domains at once",
                "Check if the target domains are responsive",
                "Consider running the scan during off-peak hours"
            ],
            "network": [
                "Check your internet connection",
                "Verify that external scanning services are accessible",
                "Try again in a few minutes"
            ],
            "rate_limit": [
                "Wait a few minutes before retrying",
                "Consider spreading scans across longer time periods",
                "This is normal behavior for large scans"
            ],
            "authentication": [
                "Check your API key configuration",
                "Verify that scanning service credentials are valid",
                "Contact support if the issue persists"
            ],
            "resource_exhaustion": [
                "Reduce the number of domains per scan",
                "Try scanning during off-peak hours",
                "Consider upgrading your plan for more resources"
            ],
            "dns_resolution": [
                "Verify that the domain names are correct",
                "Check if the domains are publicly accessible",
                "Remove any invalid domains from your list"
            ],
            "validation": [
                "Check the format of your domain list",
                "Ensure all domains are valid",
                "Review scan configuration parameters"
            ],
            "database": [
                "Try the scan again",
                "Check if partial results are available",
                "Contact support if the issue persists"
            ],
            "unknown": [
                "Try the scan again",
                "Contact support with the error details",
                "Check our status page for known issues"
            ]
        }
        return suggestions.get(error_category, suggestions["unknown"])

    def _get_error_severity(self, error_category: str) -> str:
        """Determine error severity for appropriate UI treatment."""
        severity_map = {
            "timeout": "medium",
            "network": "high",
            "rate_limit": "low",
            "authentication": "high",
            "resource_exhaustion": "medium",
            "dns_resolution": "low",
            "validation": "medium",
            "database": "high",
            "unknown": "medium"
        }
        return severity_map.get(error_category, "medium")

    def _is_retry_recommended(self, error_category: str) -> bool:
        """Determine if automatic retry is recommended."""
        retry_recommended = {
            "timeout": True,
            "network": True,
            "rate_limit": False,  # Should wait before retry
            "authentication": False,
            "resource_exhaustion": False,
            "dns_resolution": False,
            "validation": False,
            "database": True,
            "unknown": True
        }
        return retry_recommended.get(error_category, False)

    def _assess_health_severity(self, health_issue: str, metrics: Dict[str, Any]) -> str:
        """Assess the severity of container health issues."""
        memory_mb = metrics.get("memory_mb", 0)
        cpu_percent = metrics.get("cpu_percent", 0)
        
        if memory_mb > 2048 or cpu_percent > 90:
            return "high"
        elif memory_mb > 1024 or cpu_percent > 70:
            return "medium"
        else:
            return "low"

    def _get_health_recommendations(self, health_issue: str, metrics: Dict[str, Any]) -> List[str]:
        """Get health-specific recommendations."""
        recommendations = []
        
        memory_mb = metrics.get("memory_mb", 0)
        cpu_percent = metrics.get("cpu_percent", 0)
        
        if memory_mb > 1024:
            recommendations.append("Consider reducing concurrent scan workers")
            recommendations.append("Monitor memory usage during scans")
        
        if cpu_percent > 70:
            recommendations.append("Consider scanning fewer domains simultaneously")
            recommendations.append("Check for resource-intensive operations")
        
        if not recommendations:
            recommendations.append("Monitor container performance metrics")
        
        return recommendations

    def _get_performance_severity(self, alert_type: str, metrics: Dict[str, Any]) -> str:
        """Determine performance alert severity."""
        if alert_type in ["memory_critical", "cpu_critical"]:
            return "high"
        elif alert_type in ["memory_warning", "cpu_warning", "slow_response"]:
            return "medium"
        else:
            return "low"

    def _assess_performance_impact(self, alert_type: str, metrics: Dict[str, Any]) -> str:
        """Assess the impact of performance issues."""
        impact_map = {
            "memory_critical": "Scan may fail or produce incomplete results",
            "cpu_critical": "Scan performance significantly degraded",
            "memory_warning": "Scan performance may be reduced",
            "cpu_warning": "Scan may take longer than expected",
            "slow_response": "Individual domain scans taking longer than normal",
            "rate_limit": "Scan automatically throttled to respect service limits"
        }
        return impact_map.get(alert_type, "Performance impact being monitored")

    def _get_optimization_suggestions(self, alert_type: str, metrics: Dict[str, Any]) -> List[str]:
        """Get performance optimization suggestions."""
        suggestions_map = {
            "memory_critical": [
                "Reduce the number of concurrent workers",
                "Scan fewer domains per batch",
                "Consider upgrading container resources"
            ],
            "cpu_critical": [
                "Reduce scan concurrency",
                "Optimize scan parameters",
                "Consider spreading scans over time"
            ],
            "memory_warning": [
                "Monitor memory usage trends",
                "Consider optimizing scan batch sizes"
            ],
            "cpu_warning": [
                "Monitor CPU usage patterns",
                "Consider reducing worker threads"
            ],
            "slow_response": [
                "Check network connectivity",
                "Monitor external service response times",
                "Consider retry strategies"
            ]
        }
        return suggestions_map.get(alert_type, ["Monitor performance metrics", "Consider optimizing scan parameters"])
            
    async def get_connection_stats(self) -> Dict[str, Any]:
        """Get Redis connection statistics for health monitoring."""
        return {
            "redis_connected": self.is_connected,
            "connection_attempts": self.connection_attempts,
            "environment": settings.environment,
            "redis_host": settings.redis_host if not settings.is_local_environment else "localhost",
            "is_local": settings.is_local_environment,
            "is_cloud": settings.is_cloud_environment
        }

class WebSocketManager:
    """
    WebSocket connection manager with environment-aware Redis integration.
    """
    
    def __init__(self):
        self.active_connections: Dict[str, Set[Any]] = {}  # user_id -> set of websockets
        self.redis_client: Optional[redis.Redis] = None
        self.subscription_tasks: List[asyncio.Task] = []
        
    async def initialize_redis(self):
        """Initialize Redis connection for WebSocket pub/sub."""
        try:
            if settings.is_local_environment:
                # Local development
                self.redis_client = redis.from_url(
                    settings.redis_url,
                    socket_timeout=5,
                    socket_connect_timeout=5,
                    decode_responses=True
                )
            else:
                # Cloud environment
                self.redis_client = redis.Redis(**settings.redis_connection_kwargs)
                
            # Test connection
            await self.redis_client.ping()
            logger.info("✅ WebSocket Redis connection established")
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize WebSocket Redis: {str(e)}")
            self.redis_client = None
            raise e
    
    async def connect(self, websocket: Any, user_id: str):
        """Add a WebSocket connection for a user."""
        if user_id not in self.active_connections:
            self.active_connections[user_id] = set()
        self.active_connections[user_id].add(websocket)
        
        # Start listening for batch progress updates for this user
        if self.redis_client:
            task = asyncio.create_task(self._listen_for_batch_updates(user_id))
            self.subscription_tasks.append(task)
            
    async def disconnect(self, websocket: Any, user_id: str):
        """Remove a WebSocket connection for a user."""
        if user_id in self.active_connections:
            self.active_connections[user_id].discard(websocket)
            if not self.active_connections[user_id]:
                del self.active_connections[user_id]
                
    async def _listen_for_batch_updates(self, user_id: str):
        """Listen for batch progress updates from Redis and forward to WebSocket clients."""
        if not self.redis_client:
            return
            
        try:
            pubsub = self.redis_client.pubsub()
            await pubsub.subscribe(f"batch_progress:{user_id}")
            
            async for message in pubsub.listen():
                if message["type"] == "message":
                    # Forward message to all WebSocket connections for this user
                    if user_id in self.active_connections:
                        disconnected = set()
                        for websocket in self.active_connections[user_id]:
                            try:
                                await websocket.send_text(message["data"])
                            except Exception:
                                disconnected.add(websocket)
                        
                        # Clean up disconnected WebSockets
                        for websocket in disconnected:
                            self.active_connections[user_id].discard(websocket)
                            
        except Exception as e:
            logger.error(f"❌ Error in batch updates listener for user {user_id}: {str(e)}")
            
    async def get_connection_stats(self) -> Dict[str, Any]:
        """Get WebSocket connection statistics."""
        total_connections = sum(len(connections) for connections in self.active_connections.values())
        return {
            "total_connections": total_connections,
            "total_users": len(self.active_connections),
            "redis_connected": self.redis_client is not None,
            "environment": settings.environment
        }

# Global instances
batch_progress_notifier = BatchProgressNotifier()
websocket_manager = WebSocketManager()

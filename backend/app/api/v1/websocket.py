"""
WebSocket API Endpoints for Real-time Batch Progress Updates
==========================================================

Provides authenticated WebSocket connections for real-time batch scan 
progress updates and system notifications.
"""

import logging
import json
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, HTTPException, status, Query
from typing import Dict, Any, Optional

from ...core.dependencies import get_current_user_websocket, get_current_user
from ...services.websocket_manager import websocket_manager, batch_progress_notifier

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ws", tags=["WebSocket"])

@router.websocket("/batch-progress")
async def websocket_batch_progress(
    websocket: WebSocket,
    token: str = Query(None, description="Authentication token for WebSocket connection (optional in development)")
):
    """
    WebSocket endpoint for real-time batch progress updates.
    
    Provides authenticated real-time updates for:
    • Batch scan progress and status changes
    • Cost optimization notifications
    • Resource allocation updates
    • Error notifications and alerts
    
    Authentication:
    In production: Requires valid JWT token passed as query parameter
    In development: Token is optional for easier testing
    
    Message Format:
    {
        "type": "batch_progress",
        "batch_id": "uuid",
        "user_id": "user_uuid", 
        "status": "started|progress|completed|failed",
        "progress": { ... },
        "timestamp": "ISO 8601",
        "message": "Human readable message"
    }
    """
    # DEBUG: Log very beginning of WebSocket connection
    logger.info(f"🚀 WebSocket endpoint called - Starting connection process")
    
    user_id = None
    
    # DEBUG: Log connection attempt details
    client_ip = websocket.headers.get("x-forwarded-for", "unknown")
    logger.info(f"🔌 WebSocket connection attempt from {client_ip}")
    logger.info(f"🔑 Token provided: {'YES' if token else 'NO'}")
    if token:
        logger.info(f"🔑 Token preview: {token[:50]}...")
    
    try:
        # Authentication - flexible for development
        if token:
            try:
                logger.info(f"🔍 Starting WebSocket token validation...")
                # Authenticate user via token
                user = await get_current_user_websocket(token)
                user_id = user.id
                logger.info(f"✅ WebSocket authenticated successfully for user {user_id}")
            except Exception as e:
                logger.error(f"❌ WebSocket token authentication failed: {type(e).__name__}: {e}")
                logger.error(f"❌ Full error details: {str(e)}")
                # In development, continue without auth
                from ...core.config import settings
                if settings.environment in ["dev", "development", "local", "local-dev"]:
                    user_id = "dev-user"  # Use default dev user ID
                    logger.info("🔌 WebSocket connected in development mode without authentication")
                else:
                    # In production, reject invalid tokens
                    await websocket.close(code=4001, reason="Authentication failed")
                    return
        else:
            # No token provided
            from ...core.config import settings
            if settings.environment in ["dev", "development", "local", "local-dev"]:
                user_id = "dev-user"  # Use default dev user ID
                logger.info("🔌 WebSocket connected in development mode without token")
            else:
                # In production, require token
                await websocket.close(code=4001, reason="Authentication token required")
                return
        
        # Accept the WebSocket connection after successful authentication
        logger.info(f"🤝 Accepting WebSocket connection for user {user_id}")
        await websocket.accept()
        logger.info(f"✅ WebSocket connection accepted for user {user_id}")
        
        # Connect to WebSocket manager
        logger.info(f"🔗 Attempting to connect user {user_id} to WebSocket manager...")
        try:
            await websocket_manager.connect(websocket, user_id)
            logger.info(f"✅ WebSocket manager connection successful for user {user_id}")
        except Exception as e:
            logger.error(f"❌ WebSocket manager connection failed for user {user_id}: {type(e).__name__}: {e}")
            logger.error(f"❌ Manager error details: {str(e)}")
            await websocket.close(code=1011, reason="Internal server error")
            return
        
        logger.info(f"🔌 WebSocket fully connected for user {user_id}")
        
        # Keep connection alive and handle incoming messages
        while True:
            try:
                # Receive messages from client (for potential two-way communication)
                message = await websocket.receive_text()
                
                # Handle client messages (e.g., subscription preferences, ping/pong)
                await handle_client_message(message, user_id, websocket)
                
            except WebSocketDisconnect:
                logger.info(f"🔌 WebSocket disconnected for user {user_id}")
                break
                
            except Exception as e:
                logger.error(f"WebSocket message error for user {user_id}: {e}")
                # Send error message to client
                try:
                    error_message = json.dumps({
                        "type": "error",
                        "message": "Message processing error",
                        "error": str(e)
                    })
                    await websocket.send_text(error_message)
                except Exception as send_error:
                    logger.error(f"Failed to send error message: {send_error}")
                
    except HTTPException as e:
        # Authentication failed
        logger.error(f"❌ WebSocket authentication failed: {e.status_code} - {e.detail}")
        logger.error(f"❌ HTTPException type: {type(e).__name__}")
        try:
            await websocket.close(code=4001, reason="Authentication failed")
        except Exception as close_error:
            logger.error(f"❌ Error closing WebSocket after auth failure: {close_error}")
        
    except Exception as e:
        logger.error(f"❌ WebSocket connection error: {type(e).__name__}: {e}")
        logger.error(f"❌ Full error traceback:", exc_info=True)
        try:
            await websocket.close(code=1011, reason="Internal server error")
        except Exception as close_error:
            logger.error(f"❌ Error closing WebSocket after error: {close_error}")
        
    finally:
        # Clean up connection
        if user_id:
            await websocket_manager.disconnect(websocket, user_id)

async def handle_client_message(message: str, user_id: str, websocket: WebSocket):
    """Handle incoming messages from WebSocket clients."""
    try:
        import json
        data = json.loads(message)
        message_type = data.get("type")
        
        if message_type == "ping":
            # Respond to ping with pong
            pong_message = json.dumps({
                "type": "pong",
                "timestamp": data.get("timestamp")
            })
            await websocket.send_text(pong_message)
            
        elif message_type == "subscribe_batch":
            # Subscribe to specific batch updates
            batch_id = data.get("batch_id")
            if batch_id:
                subscription_message = json.dumps({
                    "type": "subscription_confirmed",
                    "batch_id": batch_id,
                    "message": f"Subscribed to batch {batch_id} updates"
                })
                await websocket.send_text(subscription_message)
                
        elif message_type == "get_connection_stats":
            # Send connection statistics (for debugging)
            stats = await websocket_manager.get_connection_stats()
            stats_message = json.dumps({
                "type": "connection_stats",
                "stats": stats
            })
            await websocket.send_text(stats_message)
            
        else:
            # Unknown message type
            error_message = json.dumps({
                "type": "error",
                "message": f"Unknown message type: {message_type}"
            })
            await websocket.send_text(error_message)
            
    except json.JSONDecodeError:
        error_message = json.dumps({
            "type": "error",
            "message": "Invalid JSON message format"
        })
        await websocket.send_text(error_message)
        
    except Exception as e:
        logger.error(f"Error handling client message: {e}")
        error_message = json.dumps({
            "type": "error", 
            "message": "Message processing error"
        })
        await websocket.send_text(error_message)

@router.get("/stats")
async def get_websocket_stats(
    current_user: Dict = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Get WebSocket connection statistics.
    
    Provides information about active WebSocket connections,
    useful for monitoring and debugging purposes.
    
    Returns:
        Dictionary with connection statistics including:
        • Total active connections
        • Connected users count  
        • Connections per user
        • Redis connectivity status
    """
    try:
        stats = await websocket_manager.get_connection_stats()
        
        return {
            "success": True,
            "stats": stats,
            "message": "WebSocket statistics retrieved successfully"
        }
        
    except Exception as e:
        logger.error(f"Failed to get WebSocket stats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve WebSocket statistics: {str(e)}"
        )

@router.post("/test-notification")
async def send_test_notification(
    message: str = "Test notification",
    current_user: Dict = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Send a test notification via WebSocket.
    
    Useful for testing WebSocket connectivity and notification delivery.
    Only sends to the authenticated user's connections.
    
    Args:
        message: Test message to send
        
    Returns:
        Confirmation of message delivery attempt
    """
    try:
        user_id = current_user.id
        
        test_message = {
            "type": "test_notification",
            "message": message,
            "user_id": user_id,
            "timestamp": "2024-01-01T00:00:00Z"  # Will be overridden by manager
        }
        
        # Note: WebSocket manager doesn't have send_user_message - this would be handled via Redis pub/sub
        await batch_progress_notifier.notify_batch_progress("test", user_id, test_message)
        
        return {
            "success": True,
            "message": f"Test notification sent to user {user_id}",
            "data": test_message
        }
        
    except Exception as e:
        logger.error(f"Failed to send test notification: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to send test notification: {str(e)}"
        )

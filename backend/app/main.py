"""    
Main Backend FastAPI application. 
""" 
import logging
import sys
import re
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from .core.config import settings
from .api.v1.auth import router as auth_router
from .api.v1.assets import router as assets_router
from .api.v1.programs import router as programs_router  # LEAN: Public programs API
from .api.v1.usage import router as usage_router  # LEAN: Backwards compatibility for recon-data
from .api.v1.websocket import router as websocket_router
from .api.v1.scans import router as scans_router
from .api.v1.http_probes import router as http_probes_router
from .api.v1.urls import router as urls_router
from .api.v1.public import router as public_router, limiter  # PUBLIC: Unauthenticated showcase
from .api.v1.billing import router as billing_router  # Stripe billing
from .services.websocket_manager import websocket_manager, batch_progress_notifier

# Configure logging for CloudWatch visibility
# Use INFO level to capture our UUID debugging logs
log_level = logging.DEBUG if settings.debug else logging.INFO

logging.basicConfig(
    level=log_level,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stdout  # Ensures logs go to CloudWatch in ECS
)

# Set specific loggers to appropriate levels
logging.getLogger("app.services.asset_service").setLevel(logging.INFO)  # Ensure UUID debugging is visible
logging.getLogger("uvicorn.access").setLevel(logging.WARNING)  # Reduce access log noise
logging.getLogger("uvicorn.error").setLevel(logging.INFO)  # Keep error logs visible

logger = logging.getLogger(__name__)


class ReverseProxyMiddleware(BaseHTTPMiddleware):
    """
    Middleware to handle reverse proxy headers (CloudFront, ALB, etc.)
    
    Fixes HTTPS redirects when FastAPI is behind a reverse proxy.
    """
    async def dispatch(self, request: Request, call_next):
        # Handle X-Forwarded-Proto header from CloudFront/ALB
        forwarded_proto = request.headers.get('x-forwarded-proto')
        if forwarded_proto:
            # Update the request URL scheme to match the original protocol
            request.scope['scheme'] = forwarded_proto
        
        # Handle X-Forwarded-Host header
        forwarded_host = request.headers.get('x-forwarded-host')
        if forwarded_host:
            request.scope['server'] = (forwarded_host, None)
        
        response = await call_next(request)
        return response


def is_origin_allowed(origin: str) -> bool:
    """
    Check if origin is allowed via static list or dynamic patterns.
    
    This enables CORS for:
    - All Vercel preview deployments (*.vercel.app)
    - All neobotnet subdomains (*.neobotnet.com)
    - Localhost development
    """
    if not origin:
        return False
    
    # Check static list first
    if origin in settings.allowed_origins:
        return True
    
    # Check dynamic patterns
    for pattern in settings.cors_origin_patterns:
        if re.match(pattern, origin):
            return True
    
    return False


class DynamicCORSMiddleware(BaseHTTPMiddleware):
    """
    Custom CORS middleware that supports dynamic origin patterns.
    
    Extends standard CORS to allow Vercel preview URLs dynamically.
    """
    async def dispatch(self, request: Request, call_next) -> Response:
        origin = request.headers.get("origin")
        
        # Handle preflight requests
        if request.method == "OPTIONS":
            if origin and is_origin_allowed(origin):
                response = Response(status_code=200)
                response.headers["Access-Control-Allow-Origin"] = origin
                response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, PATCH, DELETE, OPTIONS"
                response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization, X-API-Key, X-Requested-With"
                response.headers["Access-Control-Allow-Credentials"] = "true"
                response.headers["Access-Control-Max-Age"] = "600"
                return response
        
        # Process actual request
        response = await call_next(request)
        
        # Add CORS headers if origin is allowed
        if origin and is_origin_allowed(origin):
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Access-Control-Allow-Credentials"] = "true"
            response.headers["Access-Control-Expose-Headers"] = "Content-Type"
        
        return response


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Manage application lifespan events.
    
    Handles startup and shutdown events for proper resource management,
    including WebSocket connections and Redis pub/sub subscriptions.
    """
    # Startup
    logger.info("🚀 Starting Web Reconnaissance Framework API...")
    
    # ============================================================
    # Redis Health Check (Critical for Streaming Architecture)
    # ============================================================
    try:
        import redis.asyncio as redis
        from app.core.config import settings
        
        # Instantiate Redis client using settings
        redis_client = redis.from_url(
            settings.redis_url,
            encoding="utf-8",
            decode_responses=True,
            socket_timeout=5
        )
        
        # Test connection
        await redis_client.ping()
        await redis_client.close()  # Clean up test connection
        
        logger.info("✅ Redis connection established (streaming architecture ready)")
    except Exception as e:
        logger.error(f"❌ FATAL: Redis unavailable - {e}")
        logger.error("   Streaming architecture requires Redis for scan execution")
        logger.error("   Check Redis host configuration and connectivity")
        raise RuntimeError(
            "Cannot start backend without Redis. "
            "Streaming-only architecture requires Redis for scan pipeline execution."
        )
    
    try:
        # Initialize batch progress notifier with Redis pub/sub
        logger.info("🔄 Initializing batch progress notifier...")
        await batch_progress_notifier.initialize_redis()
        logger.info("✅ Batch progress notifier initialized successfully")
        
        # Initialize WebSocket manager with Redis pub/sub
        logger.info("🔄 Initializing WebSocket manager...")
        await websocket_manager.initialize_redis()
        logger.info("✅ WebSocket manager initialized successfully")
        
    except Exception as e:
        logger.error(f"❌ Failed to initialize Redis components: {e}")
        # Continue without WebSocket functionality in case of Redis issues
        # This allows the API to work even if Redis is temporarily unavailable
        if settings.is_local_environment:
            logger.warning("⚠️  Local development: API will continue without real-time features")
        else:
            logger.warning("⚠️  Cloud environment: API will continue without real-time features")
    
    # ============================================================
    # Module Configuration Loader (Phase 2 of 7-Layer Fix)
    # ============================================================
    try:
        from app.services.module_config_loader import initialize_module_config
        from app.core.supabase_client import supabase_client
        
        await initialize_module_config(supabase_client.service_client)
        
        logger.info("✅ Module configuration loaded from database")
    except Exception as e:
        logger.error(f"❌ Failed to load module configuration: {e}")
        logger.error("   Scans may fail. Check scan_module_profiles table exists.")
        # Don't crash the app, but scans won't work without module config
    
    logger.info("🟢 Application startup complete")
    
    yield
    
    # Shutdown
    logger.info("🔄 Shutting down Web Reconnaissance Framework API...")
    
    try:
        # Clean up batch progress notifier
        if batch_progress_notifier.redis_client:
            await batch_progress_notifier.redis_client.close()
            logger.info("✅ Batch progress notifier Redis connection closed")
        
        # Clean up WebSocket connections and Redis subscriptions
        if websocket_manager.redis_client:
            # Cancel subscription tasks
            for task in websocket_manager.subscription_tasks:
                task.cancel()
            
            # Close Redis connection
            await websocket_manager.redis_client.close()
            logger.info("✅ WebSocket manager cleaned up successfully")
            
    except Exception as e:
        logger.error(f"⚠️ Error during cleanup: {e}")
    
    logger.info("🔴 Application shutdown complete")


def create_application() -> FastAPI:
    """Create and configure the FastAPI application."""
    
    app = FastAPI(
        title=settings.project_name,
        description="A modular, multitenant web reconnaissance framework with real-time batch processing",
        version="1.0.0",
        docs_url="/docs" if settings.debug else None,
        redoc_url="/redoc" if settings.debug else None,
        lifespan=lifespan,  # Add lifespan manager for startup/shutdown events
    )
    
    # Add reverse proxy middleware FIRST (before CORS)
    # This ensures proper HTTPS redirect handling behind CloudFront/ALB
    app.add_middleware(ReverseProxyMiddleware)
    
    # Add dynamic CORS middleware - supports pattern-based origins for Vercel
    # This handles ALL CORS including preflight OPTIONS requests
    app.add_middleware(DynamicCORSMiddleware)
    
    # Log CORS configuration for debugging
    logger.info(f"🔒 CORS configured with {len(settings.allowed_origins)} static origins")
    logger.info(f"🔒 CORS patterns: {settings.cors_origin_patterns}")
    
    # Add trusted host middleware for production security
    if settings.environment == "production":
        app.add_middleware(
            TrustedHostMiddleware,
            allowed_hosts=[
                "localhost",
                "127.0.0.1",
                "172.236.127.72",
                "aldous-api.neobotnet.com",
                "neobotnet.com", 
                "www.neobotnet.com",
                "*.neobotnet.com"  # Allow subdomains
            ]
        )
    elif settings.environment in ["staging", "dev"]:
        # More permissive for non-production
        app.add_middleware(
            TrustedHostMiddleware,
            allowed_hosts=["*"]  # Allow all hosts in dev/staging
        )
    
    # Include routers
    app.include_router(auth_router, prefix=settings.api_v1_str)
    app.include_router(assets_router, prefix=settings.api_v1_str)
    app.include_router(programs_router, prefix=settings.api_v1_str)  # LEAN: Public programs API
    app.include_router(usage_router, prefix=settings.api_v1_str)  # LEAN: Backwards compatibility
    app.include_router(websocket_router, prefix=settings.api_v1_str)  # Add WebSocket routes
    app.include_router(scans_router, prefix=settings.api_v1_str)  # Unified scan endpoint
    app.include_router(http_probes_router, prefix=f"{settings.api_v1_str}/http-probes", tags=["http-probes"])
    app.include_router(urls_router, prefix=f"{settings.api_v1_str}/urls", tags=["urls"])
    
    # PUBLIC: Unauthenticated showcase endpoint with rate limiting
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.include_router(public_router, prefix=f"{settings.api_v1_str}/public", tags=["public"])
    logger.info("🌐 Public showcase endpoint enabled at /api/v1/public/showcase (rate limited: 10/min)")
    
    # Billing: Stripe checkout and webhook endpoints
    app.include_router(billing_router, prefix=f"{settings.api_v1_str}/billing", tags=["billing"])
    logger.info("💳 Billing endpoints enabled at /api/v1/billing")
    
    return app


# Create the FastAPI app instance
app = create_application()


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "Web Reconnaissance Framework API",
        "version": "1.0.0",
        "status": "running",
        "docs": "/docs" if settings.debug else "disabled",
        "features": ["unified_scans", "real_time_updates", "websocket_support"]
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    # Get WebSocket connection stats for health monitoring
    websocket_stats = await websocket_manager.get_connection_stats()
    
    return {
        "status": "healthy",
        "service": "web-recon-api",
        "environment": settings.environment,
        "debug": settings.debug,
        "websocket": {
            "enabled": websocket_stats.get("redis_connected", False),
            "active_connections": websocket_stats.get("total_connections", 0),
            "connected_users": websocket_stats.get("total_users", 0)
        }
    } 
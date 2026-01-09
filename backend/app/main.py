"""
Main Backend FastAPI application.

LEAN Refactor (2026-01): Simplified without billing dependencies.
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
from .api.v1.programs import router as programs_router
from .api.v1.usage import router as usage_router
from .api.v1.websocket import router as websocket_router
from .api.v1.scans import router as scans_router
from .api.v1.http_probes import router as http_probes_router
from .api.v1.urls import router as urls_router
from .api.v1.public import router as public_router, limiter
from .api.v1.exports import router as exports_router
from .middleware.rate_limit import TieredRateLimitMiddleware
from .services.websocket_manager import websocket_manager, batch_progress_notifier

# Configure logging
log_level = logging.DEBUG if settings.debug else logging.INFO

logging.basicConfig(
    level=log_level,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)

logging.getLogger("app.services.asset_service").setLevel(logging.INFO)
logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
logging.getLogger("uvicorn.error").setLevel(logging.INFO)

logger = logging.getLogger(__name__)


class ReverseProxyMiddleware(BaseHTTPMiddleware):
    """Handle reverse proxy headers (CloudFront, ALB, etc.)"""
    async def dispatch(self, request: Request, call_next):
        forwarded_proto = request.headers.get('x-forwarded-proto')
        if forwarded_proto:
            request.scope['scheme'] = forwarded_proto
        
        forwarded_host = request.headers.get('x-forwarded-host')
        if forwarded_host:
            request.scope['server'] = (forwarded_host, None)
        
        response = await call_next(request)
        return response


def is_origin_allowed(origin: str) -> bool:
    """Check if origin is allowed via static list or dynamic patterns."""
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
    """Custom CORS middleware that supports dynamic origin patterns."""
    
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
        
        # Process actual request - wrap in try/except to ensure CORS headers on errors
        try:
            response = await call_next(request)
        except Exception as e:
            logger.error(f"Request error: {e}")
            response = Response(
                content='{"detail": "Internal server error"}',
                status_code=500,
                media_type="application/json"
            )
        
        # Add CORS headers if origin is allowed
        if origin and is_origin_allowed(origin):
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Access-Control-Allow-Credentials"] = "true"
            response.headers["Access-Control-Expose-Headers"] = "Content-Type"
        
        return response


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan events."""
    logger.info("🚀 Starting Web Reconnaissance Framework API...")
    
    # Redis Health Check
    try:
        import redis.asyncio as redis
        
        redis_client = redis.from_url(
            settings.redis_url,
            encoding="utf-8",
            decode_responses=True,
            socket_timeout=5
        )
        
        await redis_client.ping()
        await redis_client.close()
        
        logger.info("✅ Redis connection established")
    except Exception as e:
        logger.error(f"❌ Redis unavailable - {e}")
        logger.warning("⚠️  Continuing without Redis (scans will fail)")
    
    # Initialize WebSocket components
    try:
        logger.info("🔄 Initializing batch progress notifier...")
        await batch_progress_notifier.initialize_redis()
        logger.info("✅ Batch progress notifier initialized")
        
        logger.info("🔄 Initializing WebSocket manager...")
        await websocket_manager.initialize_redis()
        logger.info("✅ WebSocket manager initialized")
        
    except Exception as e:
        logger.warning(f"⚠️  WebSocket/Redis initialization failed: {e}")
        logger.warning("   Real-time features may be unavailable")
    
    # Load Module Configuration
    try:
        from .services.module_config_loader import initialize_module_config
        from .core.supabase_client import supabase_client
        
        await initialize_module_config(supabase_client.service_client)
        logger.info("✅ Module configuration loaded from database")
    except Exception as e:
        logger.error(f"❌ Failed to load module configuration: {e}")
    
    logger.info("🟢 Application startup complete")
    
    yield
    
    # Shutdown
    logger.info("🔄 Shutting down...")
    
    try:
        if batch_progress_notifier.redis_client:
            await batch_progress_notifier.redis_client.close()
        
        if websocket_manager.redis_client:
            for task in websocket_manager.subscription_tasks:
                task.cancel()
            await websocket_manager.redis_client.close()
            
    except Exception as e:
        logger.error(f"⚠️ Error during cleanup: {e}")
    
    logger.info("🔴 Application shutdown complete")


def create_application() -> FastAPI:
    """Create and configure the FastAPI application."""
    
    app = FastAPI(
        title=settings.project_name,
        description="NeoBot-Net Web Reconnaissance Framework",
        version="2.0.0",
        docs_url="/docs" if settings.debug else None,
        redoc_url="/redoc" if settings.debug else None,
        lifespan=lifespan,
    )
    
    # Add reverse proxy middleware FIRST
    app.add_middleware(ReverseProxyMiddleware)
    
    # Add dynamic CORS middleware
    app.add_middleware(DynamicCORSMiddleware)
    
    # Add tiered rate limiting middleware
    app.add_middleware(TieredRateLimitMiddleware, free_limit=30, paid_limit=100)
    logger.info("⏱️  Tiered rate limiting enabled (free: 30/min, paid: 100/min)")
    
    # Log CORS configuration
    logger.info(f"🔒 CORS configured with {len(settings.allowed_origins)} static origins")
    logger.info(f"🔒 CORS patterns: {settings.cors_origin_patterns}")
    
    # Add trusted host middleware for production
    if settings.environment == "production":
        app.add_middleware(
            TrustedHostMiddleware,
            allowed_hosts=[
                "localhost",
                "127.0.0.1",
                "172.236.127.72",
                # Production domains
                "aldous-api.neobotnet.com",  # Backend API
                "neobotnet.com",
                "www.neobotnet.com",         # Frontend
                "huxley.neobotnet.com",      # Supabase Auth
                "*.neobotnet.com"            # All subdomains
            ]
        )
    elif settings.environment in ["staging", "dev"]:
        app.add_middleware(
            TrustedHostMiddleware,
            allowed_hosts=["*"]
        )
    
    # Include routers
    app.include_router(auth_router, prefix=settings.api_v1_str)
    app.include_router(assets_router, prefix=settings.api_v1_str)
    app.include_router(programs_router, prefix=settings.api_v1_str)
    app.include_router(usage_router, prefix=settings.api_v1_str)
    app.include_router(websocket_router, prefix=settings.api_v1_str)
    app.include_router(scans_router, prefix=settings.api_v1_str)
    app.include_router(http_probes_router, prefix=f"{settings.api_v1_str}/http-probes", tags=["http-probes"])
    app.include_router(urls_router, prefix=f"{settings.api_v1_str}/urls", tags=["urls"])
    
    # Public endpoints with rate limiting
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.include_router(public_router, prefix=f"{settings.api_v1_str}/public", tags=["public"])
    logger.info("🌐 Public showcase endpoint enabled at /api/v1/public/showcase")
    
    # Data exports
    app.include_router(exports_router, prefix=f"{settings.api_v1_str}/exports", tags=["exports"])
    logger.info("📥 Export endpoints enabled at /api/v1/exports")
    
    return app


# Create the FastAPI app instance
app = create_application()


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "NeoBot-Net Web Reconnaissance API",
        "version": "2.0.0",
        "status": "running",
        "docs": "/docs" if settings.debug else "disabled",
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    websocket_stats = await websocket_manager.get_connection_stats()
    
    return {
        "status": "healthy",
        "service": "neobotnet-api",
        "environment": settings.environment,
        "debug": settings.debug,
        "websocket": {
            "enabled": websocket_stats.get("redis_connected", False),
            "active_connections": websocket_stats.get("total_connections", 0),
        }
    }

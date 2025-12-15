"""
Authentication service for handling user registration, login, and authentication.
"""
from typing import Optional, Dict, Any
from datetime import timedelta
from fastapi import HTTPException, status
from supabase import AuthError
import json

from ..utils.json_encoder import safe_json_dumps

try:
    import redis.asyncio as redis
except ImportError:
    import redis

from ..core.supabase_client import supabase_client
from ..core.security import create_access_token, verify_token
from ..core.config import settings
from ..schemas.auth import UserRegister, UserLogin, Token, UserResponse


class AuthService:
    """Service class for authentication operations."""
    
    def __init__(self):
        self.supabase = supabase_client.client
        self.service_supabase = supabase_client.service_client
        self.redis_client = None
    
    async def get_redis(self):
        """Get Redis connection with environment-specific configuration."""
        if not self.redis_client:
            try:
                # Use environment-specific Redis configuration
                redis_config = settings.redis_connection_kwargs
                
                # Log connection attempt for debugging
                print(f"Connecting to Redis: {redis_config['host']}:{redis_config['port']} "
                      f"(Environment: {settings.environment}, Cloud: {settings.is_cloud_environment})")
                
                self.redis_client = redis.Redis(**redis_config)
                
                # Test connection with timeout
                await self.redis_client.ping()
                print(f"✅ Redis connection successful to {redis_config['host']}:{redis_config['port']}")
                
            except Exception as e:
                print(f"❌ Redis connection failed: {str(e)}")
                print(f"   Host: {settings.redis_host}, Port: {settings.redis_port}")
                print(f"   Environment: {settings.environment}")
                self.redis_client = None
                
        return self.redis_client
    
    async def register_user(self, user_data: UserRegister) -> Dict[str, Any]:
        """Register a new user."""
        try:
            # Register user with Supabase Auth
            response = self.supabase.auth.sign_up({
                "email": user_data.email,
                "password": user_data.password,
                "options": {
                    "data": {
                        "full_name": user_data.full_name
                    }
                }
            })
            
            if response.user is None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Registration failed"
                )
            
            return {
                "message": "Registration successful. Please check your email for verification.",
                "user_id": response.user.id,
                "email": response.user.email
            }
            
        except AuthError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Registration failed: {str(e)}"
            )
    
    async def login_user(self, user_data: UserLogin) -> Token:
        """Login user and return JWT token."""
        try:
            # Authenticate with Supabase
            response = self.supabase.auth.sign_in_with_password({
                "email": user_data.email,
                "password": user_data.password
            })
            
            if response.user is None or response.session is None:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid credentials"
                )
            
            # Create our own JWT token for consistency
            token_data = {
                "sub": response.user.id,
                "email": response.user.email,
                "supabase_token": response.session.access_token
            }
            
            access_token = create_access_token(
                data=token_data,
                expires_delta=timedelta(minutes=settings.access_token_expire_minutes)
            )
            
            return Token(
                access_token=access_token,
                token_type="bearer",
                expires_in=settings.access_token_expire_minutes * 60
            )
            
        except AuthError as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Login failed: {str(e)}"
            )
    
    async def get_current_user(self, token: str) -> UserResponse:
        """Get current user from JWT token with Redis caching for performance."""
        # Verify our JWT token
        payload = verify_token(token)
        if not payload:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token"
            )
        
        user_id = payload.get("sub")
        user_email = payload.get("email")
        token_type = payload.get("type")
        supabase_token = payload.get("supabase_token")
        
        # Handle WebSocket tokens differently (they don't have supabase_token)
        if token_type == "websocket":
            if not user_id or not user_email:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid WebSocket token payload"
                )
        else:
            # Regular tokens require supabase_token
            if not user_id or not user_email or not supabase_token:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid token payload"
                )
        
        # Try to get user from Redis cache first (performance optimization)
        redis_client = await self.get_redis()
        cache_key = f"user:{user_id}"
        
        if redis_client:
            try:
                cached_user = await redis_client.get(cache_key)
                if cached_user:
                    user_data = json.loads(cached_user)
                    return UserResponse(**user_data)
            except Exception as e:
                print(f"Redis cache read failed: {str(e)}")
        
        # Handle user data extraction differently for WebSocket tokens
        if token_type == "websocket":
            # For WebSocket tokens, we trust our own JWT validation and create minimal user data
            # We'll fetch user data from the database using the user_id
            try:
                user_response = await self._get_user_from_database(user_id, user_email)
            except Exception as e:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail=f"Failed to fetch user data for WebSocket token: {str(e)}"
                )
        else:
            # Extract user data from the embedded Supabase token (regular tokens)
            try:
                from jose import jwt
                from datetime import datetime
                
                # SECURITY FIX: Validate Supabase token structure and expiration
                try:
                    supabase_payload = jwt.get_unverified_claims(supabase_token)
                    
                    # Validate token expiration manually
                    exp = supabase_payload.get("exp")
                    if exp and datetime.fromtimestamp(exp) < datetime.now():
                        raise HTTPException(
                            status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="Supabase token has expired"
                        )
                    
                    # Validate required claims are present
                    required_claims = ["sub", "email", "aud"]
                    missing_claims = [claim for claim in required_claims if not supabase_payload.get(claim)]
                    if missing_claims:
                        raise HTTPException(
                            status_code=status.HTTP_401_UNAUTHORIZED,
                            detail=f"Invalid token: missing claims {missing_claims}"
                        )
                        
                except HTTPException:
                    raise
                except Exception as token_error:
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail=f"Invalid Supabase token: {str(token_error)}"
                    )
                
                # Extract user metadata from Supabase token
                user_metadata = supabase_payload.get("user_metadata", {})
                
                # Format timestamps as ISO strings
                token_issued = supabase_payload.get("iat")
                created_at = datetime.fromtimestamp(token_issued).isoformat() + "Z" if token_issued else datetime.now().isoformat() + "Z"
                
                # Check email verification status
                email_verified = user_metadata.get("email_verified", False)
                email_confirmed_at = created_at if email_verified else None
            
                user_response = UserResponse(
                    id=user_id,
                    email=user_email,
                    full_name=user_metadata.get("full_name"),
                    created_at=created_at,
                    email_confirmed_at=email_confirmed_at
                )
                
                # Cache user data in Redis for 5 minutes (performance optimization)
                if redis_client:
                    try:
                        await redis_client.setex(
                            cache_key, 
                            300,  # 5 minutes TTL
                            safe_json_dumps(user_response.dict())
                        )
                    except Exception as e:
                        print(f"Redis cache write failed: {str(e)}")
                
                return user_response
                    
            except HTTPException:
                # Re-raise HTTP exceptions (don't mask them)
                raise
            except Exception as e:
                # SECURITY FIX: Fail closed instead of returning fallback user data
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail=f"Authentication token processing failed: {str(e)}"
                )
        
        # Cache user data in Redis for 5 minutes (performance optimization)
        if redis_client and user_response:
            try:
                await redis_client.setex(
                    cache_key, 
                    300,  # 5 minutes TTL
                    safe_json_dumps(user_response.dict())
                )
            except Exception as e:
                print(f"Redis cache write failed: {str(e)}")
        
        return user_response
    
    async def _get_user_from_database(self, user_id: str, user_email: str) -> UserResponse:
        """
        Helper method to fetch user data directly from Supabase for WebSocket tokens.
        This bypasses the Supabase token validation since WebSocket tokens don't contain it.
        """
        from datetime import datetime
        
        try:
            # Use the service client to fetch user data by ID
            result = self.service_supabase.auth.admin.get_user_by_id(user_id)
            
            if not result or not result.user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="User not found in database"
                )
            
            user = result.user
            
            # Verify the email matches (additional security check)
            if user.email != user_email:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="User email mismatch in WebSocket token"
                )
            
            # Extract user metadata
            user_metadata = user.user_metadata or {}
            
            # Format timestamps
            created_at = user.created_at if user.created_at else datetime.now().isoformat() + "Z"
            email_confirmed_at = user.email_confirmed_at if user.email_confirmed_at else None
            
            return UserResponse(
                id=user.id,
                email=user.email,
                full_name=user_metadata.get("full_name"),
                created_at=created_at,
                email_confirmed_at=email_confirmed_at
            )
            
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Failed to fetch user from database: {str(e)}"
            )
    
    async def logout_user(self, token: str) -> Dict[str, str]:
        """Logout user by invalidating Supabase session."""
        payload = verify_token(token)
        if not payload:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token"
            )
        
        supabase_token = payload.get("supabase_token")
        if supabase_token:
            try:
                user_client = supabase_client.get_user_client(supabase_token)
                user_client.auth.sign_out()
            except AuthError:
                pass  # Ignore errors during logout
        
        return {"message": "Logout successful"}


# Global auth service instance
auth_service = AuthService() 
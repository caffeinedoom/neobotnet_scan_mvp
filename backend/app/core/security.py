"""
Security utilities for authentication and authorization.

Supports two types of JWT tokens:
1. Custom tokens (created by this backend) - signed with jwt_secret_key
2. Supabase tokens (from OAuth login) - signed with Supabase's JWT secret
"""
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from jose import JWTError, jwt
from passlib.context import CryptContext
from .config import settings


# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """Create a JWT access token."""
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.access_token_expire_minutes)
    
    to_encode.update({"exp": expire, "iat": datetime.utcnow()})
    
    encoded_jwt = jwt.encode(
        to_encode, 
        settings.jwt_secret_key, 
        algorithm=settings.jwt_algorithm
    )
    return encoded_jwt


def verify_token(token: str) -> Optional[Dict[str, Any]]:
    """
    Verify and decode a JWT token.
    
    Tries multiple verification methods in order:
    1. Custom JWT secret (for tokens created by this backend)
    2. Supabase JWT secret (for tokens from OAuth login via Supabase)
    """
    # DEBUG: Log token info for troubleshooting
    token_preview = token[:50] + "..." if len(token) > 50 else token
    secret_preview = settings.jwt_secret_key[:10] + "..." if len(settings.jwt_secret_key) > 10 else settings.jwt_secret_key
    print(f"[AUTH DEBUG] verify_token called")
    print(f"[AUTH DEBUG] Token preview: {token_preview}")
    print(f"[AUTH DEBUG] Secret preview: {secret_preview}")
    print(f"[AUTH DEBUG] Algorithm: {settings.jwt_algorithm}")
    
    # Try to decode without verification first to see the claims
    try:
        unverified = jwt.get_unverified_claims(token)
        print(f"[AUTH DEBUG] Unverified claims: aud={unverified.get('aud')}, iss={unverified.get('iss')}, sub={unverified.get('sub')[:8] if unverified.get('sub') else 'None'}...")
    except Exception as e:
        print(f"[AUTH DEBUG] Failed to get unverified claims: {e}")
    
    # First, try to verify with our JWT secret (no audience check)
    try:
        payload = jwt.decode(
            token, 
            settings.jwt_secret_key, 
            algorithms=[settings.jwt_algorithm],
            options={"verify_aud": False}  # Don't verify audience for flexibility
        )
        print(f"[AUTH DEBUG] ✅ Token verified successfully (no aud check)")
        payload["_token_type"] = "verified"
        return payload
    except JWTError as e:
        print(f"[AUTH DEBUG] ❌ Verification failed (no aud): {type(e).__name__}: {e}")
    
    # Second, try with audience="authenticated" (Supabase standard)
    try:
        payload = jwt.decode(
            token, 
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
            audience="authenticated"
        )
        print(f"[AUTH DEBUG] ✅ Token verified successfully (with aud=authenticated)")
        payload["_token_type"] = "supabase"
        return payload
    except JWTError as e:
        print(f"[AUTH DEBUG] ❌ Verification failed (with aud): {type(e).__name__}: {e}")
    
    print(f"[AUTH DEBUG] ❌ All verification methods failed")
    return None


def verify_supabase_token(token: str) -> Optional[Dict[str, Any]]:
    """
    Verify a Supabase JWT token directly.
    
    This is specifically for tokens issued by Supabase Auth (OAuth, magic link, etc.)
    These tokens are signed with the Supabase JWT secret and have specific claims.
    """
    try:
        # Supabase tokens use HS256 and the JWT secret from the project settings
        payload = jwt.decode(
            token, 
            settings.jwt_secret_key,
            algorithms=["HS256"],
            audience="authenticated"
        )
        return payload
    except JWTError as e:
        print(f"Supabase token verification failed: {e}")
        return None


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash."""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Generate password hash."""
    return pwd_context.hash(password)


def extract_user_id_from_token(token: str) -> Optional[str]:
    """Extract user ID from JWT token."""
    payload = verify_token(token)
    if payload:
        return payload.get("sub")  # 'sub' is the standard claim for user ID
    return None 
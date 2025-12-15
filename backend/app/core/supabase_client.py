"""
Supabase client configuration and initialization.
"""
from supabase import create_client, Client
from .config import settings


class SupabaseClient:
    """Supabase client wrapper for database and auth operations."""
    
    def __init__(self):
        self._client: Client = None
        self._service_client: Client = None
    
    @property
    def client(self) -> Client:
        """Get the standard Supabase client (with anon key)."""
        if not self._client:
            self._client = create_client(
                settings.supabase_url,
                settings.supabase_anon_key
            )
        return self._client
    
    @property
    def service_client(self) -> Client:
        """Get the service role client (with elevated permissions)."""
        if not self._service_client:
            self._service_client = create_client(
                settings.supabase_url,
                settings.supabase_service_role_key
            )
        return self._service_client
    
    def get_user_client(self, access_token: str) -> Client:
        """Get a client with user's access token."""
        # Note: This method is currently unused as we simplified authentication
        # to use JWT payload directly. Keeping for future use if needed.
        client = create_client(
            settings.supabase_url,
            settings.supabase_anon_key
        )
        return client


# Global Supabase client instance
supabase_client = SupabaseClient() 
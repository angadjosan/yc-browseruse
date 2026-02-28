"""Supabase client for database access."""
from typing import Optional

from supabase import Client, create_client

from app.config import get_config

_client: Optional[Client] = None


def get_supabase() -> Client:
    global _client
    if _client is None:
        cfg = get_config()
        url = cfg["supabase_url"]
        key = cfg["supabase_service_role_key"]
        if not url or not key:
            raise ValueError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set")
        _client = create_client(url, key)
    return _client


# Lazy singleton access
def supabase() -> Client:
    return get_supabase()

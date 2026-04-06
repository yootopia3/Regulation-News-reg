"""Supabase client module.

Importing this module has no side effects. Environment variables are only
read when the client is actually used (method access on `supabase` or
explicit `get_supabase_client()` call). The real client is created once
and cached as a singleton.
"""

from typing import Any, Optional

from supabase import create_client, Client

from src.config.settings import load_env, get_supabase_url, get_supabase_anon_key

_client: Optional[Client] = None


def get_supabase_client() -> Client:
    """Return the cached Supabase client, creating it on first call."""
    global _client
    if _client is None:
        load_env()
        url = get_supabase_url()
        key = get_supabase_anon_key()
        _client = create_client(url, key)
    return _client


class _LazySupabaseClient:
    """Lazy proxy around the real Supabase `Client`.

    Importing this object is free; the underlying client is only created
    when an attribute is accessed (e.g. `supabase.table(...)`).
    """

    def __getattr__(self, name: str) -> Any:
        return getattr(get_supabase_client(), name)


supabase: Any = _LazySupabaseClient()

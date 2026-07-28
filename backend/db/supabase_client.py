"""Thin wrapper around the Supabase Python client.

A single ``Client`` is cached for the lifetime of the process so we don't pay
the cost of repeatedly initialising the underlying HTTP client.  When running
in dry-run mode (no credentials), the wrapper returns ``None`` and callers
fall back to in-memory persistence so the frontend can be developed locally.
"""

from __future__ import annotations

import threading
from typing import Optional

from core.config import Settings
from supabase import Client, create_client  # type: ignore[import-not-found]

_lock = threading.Lock()
_cached: Optional[Client] = None


def get_supabase_client(settings: Settings) -> Optional[Client]:
    """Return a Supabase client or ``None`` if credentials are missing / dry-run."""
    global _cached

    if not settings.has_supabase or settings.dry_run:
        return None

    with _lock:
        if _cached is None:
            _cached = create_client(settings.supabase_url, settings.supabase_service_key)
        return _cached


def reset_supabase_client() -> None:
    """Forget the cached client. Useful for tests."""
    global _cached
    with _lock:
        _cached = None
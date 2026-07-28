"""In-memory fallback store used when Supabase credentials are absent
(``DEADZONE_DRY_RUN=true`` or no ``SUPABASE_*`` env vars set).

Gives every service a tiny thread-safe table abstraction so the bot and API
can be developed and demoed end-to-end without a real Postgres/Supabase
project. Data does not persist across process restarts and is not shared
across processes (the API process and the bot process each get their own
store) — that's fine for local development; a real crisis deployment should
always run with real Supabase credentials.
"""

from __future__ import annotations

import threading
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


class InMemoryTable:
    """A minimal in-memory stand-in for a Supabase/Postgres table."""

    def __init__(self) -> None:
        self._rows: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.Lock()

    def insert(self, row: Dict[str, Any]) -> Dict[str, Any]:
        row = dict(row)
        row.setdefault("id", str(uuid.uuid4()))
        row.setdefault("created_at", datetime.now(timezone.utc))
        with self._lock:
            self._rows[row["id"]] = row
        return dict(row)

    def upsert(self, key: str, row: Dict[str, Any]) -> Dict[str, Any]:
        with self._lock:
            existing = self._rows.get(key, {})
            merged = {**existing, **row}
            self._rows[key] = merged
            return dict(merged)

    def get(self, key: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            row = self._rows.get(key)
            return dict(row) if row is not None else None

    def all(self) -> List[Dict[str, Any]]:
        with self._lock:
            return [dict(r) for r in self._rows.values()]

    def update(self, key: str, patch: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        with self._lock:
            if key not in self._rows:
                return None
            self._rows[key].update(patch)
            return dict(self._rows[key])


class MemoryStore:
    """Process-wide singleton holding all dry-run tables."""

    def __init__(self) -> None:
        self.pulses = InMemoryTable()
        self.h3_hexes = InMemoryTable()
        self.needs = InMemoryTable()


_store: Optional[MemoryStore] = None
_store_lock = threading.Lock()


def get_memory_store() -> MemoryStore:
    """Return the process-wide in-memory store, creating it on first use."""
    global _store
    with _store_lock:
        if _store is None:
            _store = MemoryStore()
        return _store


def reset_memory_store() -> None:
    """Discard all in-memory data. Useful for tests."""
    global _store
    with _store_lock:
        _store = MemoryStore()


__all__ = ["InMemoryTable", "MemoryStore", "get_memory_store", "reset_memory_store"]

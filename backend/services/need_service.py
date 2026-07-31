"""Business logic for the Need Broadcast Engine.

Parses free-text Bangla need reports, categorizes and priority-scores them,
geocodes and h3-indexes the location (so needs can be layered onto the same
map as pulses), and persists them — to Supabase when configured, or an
in-memory store in DRY_RUN mode.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import h3

from core.config import Settings
from db.memory_store import get_memory_store
from db.supabase_client import get_supabase_client
from services.geocoder import geocode
from services.need_parser import parse_need

log = logging.getLogger("deadzone.need_service")

H3_RESOLUTION = 7

VALID_STATUSES: Tuple[str, ...] = ("open", "acknowledged", "dispatched", "fulfilled")


@dataclass
class NeedCreateResult:
    """What the API layer needs after a need report is parsed and persisted."""

    id: str
    need_text: str
    category: str
    place_text: Optional[str]
    lat: Optional[float]
    lng: Optional[float]
    h3_cell: Optional[str]
    priority: int
    urgent: bool
    status: str
    created_at: datetime


class NeedService:
    """Create and query need-broadcast reports."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client = get_supabase_client(settings)
        self._memory = get_memory_store()

    # ------------------------------------------------------------------
    # Writes
    # ------------------------------------------------------------------

    def create_need(
        self,
        raw_text: str,
        telegram_id: Optional[int] = None,
        source: str = "bot",
    ) -> NeedCreateResult:
        """Parse, geocode, and persist a need report.

        Raises ``ValueError`` if the text doesn't look like a need report —
        the API layer turns that into a 422.
        """
        parsed = parse_need(raw_text)
        if parsed is None:
            raise ValueError(
                "Message doesn't look like a need report. Expected something "
                "like 'পানি দরকার, মিরপুর ১০'."
            )

        lat: Optional[float] = None
        lng: Optional[float] = None
        h3_cell: Optional[str] = None

        if parsed.place_text:
            geo = geocode(parsed.place_text)
            lat, lng = geo.lat, geo.lng
            h3_cell = h3.geo_to_h3(lat, lng, H3_RESOLUTION)

        now = datetime.now(timezone.utc)
        row: Dict[str, Any] = {
            "raw_text": parsed.raw_text,
            "need_text": parsed.need_text,
            "category": parsed.category,
            "place_text": parsed.place_text,
            "lat": lat,
            "lng": lng,
            "h3_cell": h3_cell,
            "priority": parsed.priority,
            "urgent": parsed.urgent,
            "status": "open",
            "source": source,
            "created_at": now.isoformat(),
        }

        if h3_cell:
            self._touch_hex(h3_cell, now)

        if self._client is not None:
            saved = self._client.table("needs").insert(row).execute().data[0]
        else:
            saved = self._memory.needs.insert(row)

        return NeedCreateResult(
            id=str(saved["id"]),
            need_text=saved["need_text"],
            category=saved["category"],
            place_text=saved.get("place_text"),
            lat=saved.get("lat"),
            lng=saved.get("lng"),
            h3_cell=saved.get("h3_cell"),
            priority=saved["priority"],
            urgent=saved["urgent"],
            status=saved["status"],
            created_at=saved.get("created_at", now),
        )

    def _touch_hex(self, h3_cell: str, when: datetime) -> None:
        """Upsert the h3_hexes rollup row used by the Dead Zone heatmap."""
        centroid_lat, centroid_lng = h3.h3_to_geo(h3_cell)

        if self._client is not None:
            self._client.rpc(
                "increment_hex",
                {
                    "p_cell_id": h3_cell,
                    "p_centroid_lat": centroid_lat,
                    "p_centroid_lng": centroid_lng,
                    "p_when": when.isoformat(),
                },
            ).execute()
            return

        existing_row = self._memory.h3_hexes.get(h3_cell) or {}
        count = existing_row.get("pulse_count", 0) + 1
        self._memory.h3_hexes.upsert(
            h3_cell,
            {
                "cell_id": h3_cell,
                "h3_cell": h3_cell,
                "centroid_lat": centroid_lat,
                "centroid_lng": centroid_lng,
                "last_pulse_at": when,
                "pulse_count": count,
                "updated_at": when,
            },
        )

    def mark_status(self, need_id: str, status: str) -> Optional[Dict[str, Any]]:
        """Coordinator updates a need's status (open/acknowledged/dispatched/
        fulfilled). Full dispatch bookkeeping — which coordinator, which
        resources, timestamps for the audit trail — belongs to the Aid
        Ledger feature; this is intentionally just a status flag for now.
        """
        if status not in VALID_STATUSES:
            raise ValueError(f"status must be one of {VALID_STATUSES}")

        if self._client is not None:
            resp = (
                self._client.table("needs")
                .update({"status": status})
                .eq("id", need_id)
                .execute()
            )
            return resp.data[0] if resp.data else None

        return self._memory.needs.update(need_id, {"status": status})

    # ------------------------------------------------------------------
    # Reads
    # ------------------------------------------------------------------

    def list_recent(
        self,
        limit: int = 100,
        category: Optional[str] = None,
        status: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Needs sorted by priority (highest first), then recency.

        This ordering is what makes the "priority scoring" feature visible
        on the coordinator dashboard: the most urgent, highest-priority
        reports surface at the top regardless of arrival order.
        """
        if self._client is not None:
            query = (
                self._client.table("needs")
                .select("*")
                .order("priority", desc=True)
                .order("created_at", desc=True)
                .limit(limit)
            )
            if category:
                query = query.eq("category", category)
            if status:
                query = query.eq("status", status)
            return query.execute().data

        rows = self._memory.needs.all()
        if category:
            rows = [r for r in rows if r.get("category") == category]
        if status:
            rows = [r for r in rows if r.get("status") == status]
        rows.sort(key=lambda r: (r["priority"], r["created_at"]), reverse=True)
        return rows[:limit]


__all__ = ["NeedService", "NeedCreateResult", "VALID_STATUSES"]

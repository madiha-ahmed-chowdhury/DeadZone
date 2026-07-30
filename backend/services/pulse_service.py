"""Business logic for creating and querying "I'm alive" pulses.

Wires together the Bangla pulse parser, the gazetteer geocoder, h3 hex
indexing, and persistence. Persistence targets Supabase when credentials are
configured, and falls back to an in-memory store in DRY_RUN / no-credentials
mode so the bot and dashboard can be developed without a live project.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import h3

from core.config import Settings
from db.memory_store import get_memory_store
from db.supabase_client import get_supabase_client
from services.geocoder import geocode
from services.pulse_parser import parse_pulse

log = logging.getLogger("deadzone.pulse_service")

# Resolution 7 hexes are ~5 km^2 — fine-grained enough to distinguish
# neighbourhoods (Mirpur 10 vs Mirpur 11) without exploding the hex count
# for a national-scale heatmap.
H3_RESOLUTION = 7


@dataclass
class PulseCreateResult:
    """What the API layer needs after a pulse is parsed and persisted."""

    id: str
    place_text: Optional[str]
    lat: Optional[float]
    lng: Optional[float]
    h3_cell: Optional[str]
    confidence: str
    matched_kind: str
    created_at: datetime


class PulseService:
    """Create and query "I'm alive" pulses."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client = get_supabase_client(settings)
        self._memory = get_memory_store()

    # ------------------------------------------------------------------
    # Writes
    # ------------------------------------------------------------------

    def create_pulse(
        self,
        raw_text: str,
        telegram_id: Optional[int] = None,
        source: str = "bot",
    ) -> PulseCreateResult:
        """Parse *raw_text*, geocode it, index it in h3, and persist it.

        Raises ``ValueError`` if the text doesn't look like an alive pulse —
        the API layer turns that into a 422 so callers (bot, curl, tests)
        can tell "not a pulse" apart from a real server error.
        """
        parsed = parse_pulse(raw_text)
        if parsed is None:
            raise ValueError(
                "Message doesn't look like an 'I'm alive' pulse. Expected "
                "something like 'আমি ঠিক আছি, ঢাকা'."
            )

        lat: Optional[float] = None
        lng: Optional[float] = None
        h3_cell: Optional[str] = None
        confidence = "low"
        matched_kind = "unknown"

        if parsed.place_text:
            geo = geocode(parsed.place_text)
            lat, lng = geo.lat, geo.lng
            confidence = geo.confidence
            matched_kind = "gazetteer" if geo.matched_alias else "centroid"
            h3_cell = h3.geo_to_h3(lat, lng, H3_RESOLUTION)

        now = datetime.now(timezone.utc)
        pulse_row: Dict[str, Any] = {
            "raw_text": parsed.raw_text,
            "place_text": parsed.place_text,
            "lat": lat,
            "lng": lng,
            "h3_cell": h3_cell,
            "confidence": confidence,
            "matched_kind": matched_kind,
            "source": source,
            "created_at": now,
        }

        if h3_cell:
            self._touch_hex(h3_cell, lat, lng, now)  # type: ignore[arg-type]

        if self._client is not None:
            user_id = self._resolve_user_id(telegram_id) if telegram_id else None
            if user_id:
                pulse_row["user_id"] = user_id
            saved = self._client.table("pulses").insert(pulse_row).execute().data[0]
        else:
            saved = self._memory.pulses.insert(pulse_row)

        return PulseCreateResult(
            id=str(saved["id"]),
            place_text=saved.get("place_text"),
            lat=saved.get("lat"),
            lng=saved.get("lng"),
            h3_cell=saved.get("h3_cell"),
            confidence=saved.get("confidence", confidence),
            matched_kind=saved.get("matched_kind", matched_kind),
            created_at=saved.get("created_at", now),
        )

    def _resolve_user_id(self, telegram_id: int) -> Optional[str]:
        """Find-or-create the ``users`` row for a Telegram sender."""
        if self._client is None:
            return None
        existing = (
            self._client.table("users")
            .select("id")
            .eq("telegram_id", telegram_id)
            .limit(1)
            .execute()
        )
        if existing.data:
            return existing.data[0]["id"]
        created = self._client.table("users").insert({"telegram_id": telegram_id}).execute()
        return created.data[0]["id"] if created.data else None

    def _touch_hex(self, h3_cell: str, lat: float, lng: float, when: datetime) -> None:
        """Upsert the h3_hexes rollup row used by the Dead Zone heatmap."""
        centroid_lat, centroid_lng = h3.h3_to_geo(h3_cell)

        if self._client is not None:
            # Atomic increment on the Postgres side (see increment_hex() in
            # schema.sql) — avoids the read-then-write race of the old
            # select-count / upsert-count+1 pattern under concurrent writes.
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

    # ------------------------------------------------------------------
    # Reads
    # ------------------------------------------------------------------

    def list_recent(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Most recent pulses, newest first."""
        if self._client is not None:
            resp = (
                self._client.table("pulses")
                .select("id, raw_text, place_text, lat, lng, h3_cell, confidence, created_at")
                .order("created_at", desc=True)
                .limit(limit)
                .execute()
            )
            return resp.data

        rows = sorted(self._memory.pulses.all(), key=lambda r: r["created_at"], reverse=True)
        return rows[:limit]

    def list_hex_summaries(self) -> List[Dict[str, Any]]:
        """Per-hex rollup (cell, centroid, last-seen, count) for the heatmap."""
        if self._client is not None:
            resp = (
                self._client.table("h3_hexes")
                .select("cell_id, centroid_lat, centroid_lng, last_pulse_at, pulse_count")
                .not_.is_("last_pulse_at", "null")
                .execute()
            )
            return [
                {
                    "h3_cell": row["cell_id"],
                    "centroid_lat": row["centroid_lat"],
                    "centroid_lng": row["centroid_lng"],
                    "last_pulse_at": row["last_pulse_at"],
                    "pulse_count": row["pulse_count"],
                }
                for row in resp.data
            ]

        rows = self._memory.h3_hexes.all()
        return [r for r in rows if r.get("last_pulse_at") is not None]


__all__ = ["PulseService", "PulseCreateResult"]

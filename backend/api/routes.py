"""HTTP routes for the DeadZone pulse API.

Defines:
- GET  /healthz                         liveness probe
- POST /api/v1/pulses                   create a pulse from bot or web
- GET  /api/v1/pulses                   list recent pulses (default 100)
- GET  /api/v1/hexes                    per-hex aggregate for the heatmap layer

The route handlers delegate parsing, geocoding, indexing, and persistence to
``services.pulse_service`` so this module stays focused on transport.
"""

from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from core.config import Settings, get_settings
from services.pulse_service import PulseService, PulseCreateResult

router = APIRouter()


# ---------- Schemas ----------


class CreatePulseIn(BaseModel):
    raw_text: str = Field(..., min_length=1, max_length=2000, description="Original message text")
    telegram_id: Optional[int] = Field(
        None,
        description="Telegram user ID. Optional so web/curl callers can omit it.",
    )
    source: str = Field("bot", description="'bot', 'web', or 'test'")


class CreatePulseOut(BaseModel):
    id: str
    place_text: Optional[str]
    lat: Optional[float]
    lng: Optional[float]
    h3_cell: Optional[str]
    confidence: str
    matched_kind: str
    created_at: datetime


class PulseOut(BaseModel):
    id: str
    raw_text: str
    place_text: Optional[str]
    lat: Optional[float]
    lng: Optional[float]
    h3_cell: Optional[str]
    confidence: Optional[str]
    created_at: datetime


class HexSummary(BaseModel):
    h3_cell: str
    centroid_lat: float
    centroid_lng: float
    last_pulse_at: datetime
    pulse_count: int


# ---------- Dependencies ----------


def get_pulse_service(settings: Settings = Depends(get_settings)) -> PulseService:
    return PulseService(settings)


# ---------- Endpoints ----------


@router.get("/healthz", tags=["meta"])
def healthz() -> dict:
    """Lightweight liveness probe. Always returns ``{ok: True}``."""
    return {"ok": True, "service": "deadzone-api", "ts": datetime.now(timezone.utc).isoformat()}


@router.post(
    "/api/v1/pulses",
    response_model=CreatePulseOut,
    status_code=201,
    tags=["pulses"],
)
def create_pulse(
    payload: CreatePulseIn,
    service: PulseService = Depends(get_pulse_service),
) -> CreatePulseOut:
    """Parse raw Bangla text, geocode, index in h3, and persist.

    The same endpoint is called from the Telegram bot and from any direct
    HTTP client (curl, frontend debug tools, tests).
    """
    try:
        result: PulseCreateResult = service.create_pulse(
            raw_text=payload.raw_text,
            telegram_id=payload.telegram_id,
            source=payload.source,
        )
    except ValueError as exc:
        # Validation failure from inside the service layer
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return CreatePulseOut(
        id=result.id,
        place_text=result.place_text,
        lat=result.lat,
        lng=result.lng,
        h3_cell=result.h3_cell,
        confidence=result.confidence,
        matched_kind=result.matched_kind,
        created_at=result.created_at,
    )


@router.get("/api/v1/pulses", response_model=List[PulseOut], tags=["pulses"])
def list_pulses(
    limit: int = Query(100, ge=1, le=500),
    service: PulseService = Depends(get_pulse_service),
) -> List[PulseOut]:
    """Return the most recent pulses, newest first."""
    rows = service.list_recent(limit=limit)
    return [PulseOut(**r) for r in rows]


@router.get("/api/v1/hexes", response_model=List[HexSummary], tags=["pulses"])
def list_hex_summaries(
    service: PulseService = Depends(get_pulse_service),
) -> List[HexSummary]:
    """Per-hex rollup used to colour the Dead Zone heatmap layer."""
    rows = service.list_hex_summaries()
    return [HexSummary(**r) for r in rows]

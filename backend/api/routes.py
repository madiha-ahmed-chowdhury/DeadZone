"""HTTP routes for the DeadZone pulse API.

Defines:
- GET  /healthz                         liveness probe
- POST /api/v1/pulses                   create a pulse from bot or web
- GET  /api/v1/pulses                   list recent pulses (default 100)
- GET  /api/v1/hexes                    per-hex aggregate for the heatmap layer

The route handlers delegate parsing, geocoding, indexing, and persistence to
``services.pulse_service`` so this module stays focused on transport.
"""

import secrets
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, Field

from core.config import Settings, get_settings
from services.need_service import NeedService, NeedCreateResult
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


class CreateNeedIn(BaseModel):
    raw_text: str = Field(..., min_length=1, max_length=2000, description="Original message text")
    telegram_id: Optional[int] = Field(None, description="Telegram user ID, if reported via bot")
    source: str = Field("bot", description="'bot', 'web', or 'test'")


class CreateNeedOut(BaseModel):
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


class NeedOut(BaseModel):
    id: str
    raw_text: str
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


class UpdateNeedStatusIn(BaseModel):
    status: str = Field(..., pattern="^(open|acknowledged|dispatched|fulfilled)$")


# ---------- Dependencies ----------


def get_pulse_service(settings: Settings = Depends(get_settings)) -> PulseService:
    return PulseService(settings)


def get_need_service(settings: Settings = Depends(get_settings)) -> NeedService:
    return NeedService(settings)


def require_api_key(
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    settings: Settings = Depends(get_settings),
) -> None:
    """Gate write endpoints behind a shared secret.

    If BACKEND_API_KEY isn't set (local dev / DRY_RUN demo), auth is
    skipped so curl/tests keep working without setup. Set it before any
    public deployment — without this, anyone with the URL can forge
    'I'm alive' pulses or flip a real aid request to 'fulfilled'.
    """
    if not settings.has_api_key:
        return
    if not x_api_key or not secrets.compare_digest(x_api_key, settings.backend_api_key):
        raise HTTPException(status_code=401, detail="Missing or invalid X-API-Key")


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
    dependencies=[Depends(require_api_key)],
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


@router.post(
    "/api/v1/needs",
    response_model=CreateNeedOut,
    status_code=201,
    tags=["needs"],
    dependencies=[Depends(require_api_key)],
)
def create_need(
    payload: CreateNeedIn,
    service: NeedService = Depends(get_need_service),
) -> CreateNeedOut:
    """Parse a Bangla need report ("পানি দরকার, মিরপুর ১০"), categorize it,
    score its priority, geocode it, and persist it.

    Called from the Telegram bot as a fallback whenever a message isn't an
    "I'm alive" pulse, and from any direct HTTP client.
    """
    try:
        result: NeedCreateResult = service.create_need(
            raw_text=payload.raw_text,
            telegram_id=payload.telegram_id,
            source=payload.source,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return CreateNeedOut(
        id=result.id,
        need_text=result.need_text,
        category=result.category,
        place_text=result.place_text,
        lat=result.lat,
        lng=result.lng,
        h3_cell=result.h3_cell,
        priority=result.priority,
        urgent=result.urgent,
        status=result.status,
        created_at=result.created_at,
    )


@router.get("/api/v1/needs", response_model=List[NeedOut], tags=["needs"])
def list_needs(
    limit: int = Query(100, ge=1, le=500),
    category: Optional[str] = Query(
        None, pattern="^(water|food|medical|shelter|other)$",
        description="Filter to a single category",
    ),
    status: Optional[str] = Query(
        None, pattern="^(open|acknowledged|dispatched|fulfilled)$",
        description="Filter to a single status",
    ),
    service: NeedService = Depends(get_need_service),
) -> List[NeedOut]:
    """Needs sorted by priority (highest first) then recency — this is the
    coordinator dashboard's main feed, ready for the anti-duplication aid
    ledger to consume next."""
    rows = service.list_recent(limit=limit, category=category, status=status)
    return [NeedOut(**r) for r in rows]


@router.patch(
    "/api/v1/needs/{need_id}/status",
    response_model=NeedOut,
    tags=["needs"],
    dependencies=[Depends(require_api_key)],
)
def update_need_status(
    need_id: str,
    payload: UpdateNeedStatusIn,
    service: NeedService = Depends(get_need_service),
) -> NeedOut:
    """Coordinator marks a need acknowledged/dispatched/fulfilled."""
    updated = service.mark_status(need_id, payload.status)
    if updated is None:
        raise HTTPException(status_code=404, detail="Need not found")
    return NeedOut(**updated)

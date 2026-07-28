"""Supabase Realtime → WebSocket bridge.

Each frontend dashboard connects to ``/ws/pulses`` and receives JSON-encoded
events whenever a row is inserted into the ``pulses`` table.

Implementation note
-------------------
In ``DRY_RUN`` mode (no Supabase credentials), the bridge still accepts
connections so the frontend can be developed end-to-end.  It exposes a
``/ws/pulses/test`` ping endpoint instead.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import AsyncIterator, Set

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect, status

from core.config import Settings, get_settings
from db.supabase_client import get_supabase_client

router = APIRouter()
log = logging.getLogger("deadzone.realtime")


class ConnectionManager:
    """Tracks open WebSocket clients and broadcasts events to all of them."""

    def __init__(self) -> None:
        self._clients: Set[WebSocket] = set()
        self._lock = asyncio.Lock()

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        async with self._lock:
            self._clients.add(ws)
        log.info("realtime client connected (total=%d)", len(self._clients))

    async def disconnect(self, ws: WebSocket) -> None:
        async with self._lock:
            self._clients.discard(ws)
        log.info("realtime client disconnected (total=%d)", len(self._clients))

    async def broadcast(self, payload: dict) -> None:
        text = json.dumps(payload, default=str)
        dead: list[WebSocket] = []
        # Iterate over a snapshot to avoid mutation during send
        async with self._lock:
            clients = list(self._clients)
        for ws in clients:
            try:
                await ws.send_text(text)
            except Exception:  # pragma: no cover - defensive cleanup
                dead.append(ws)
        if dead:
            async with self._lock:
                for ws in dead:
                    self._clients.discard(ws)


manager = ConnectionManager()


async def _supabase_event_stream(settings: Settings) -> AsyncIterator[dict]:
    """Yield decoded events from the Supabase Realtime channel.

    This is a coroutine that connects to the Supabase Realtime WebSocket and
    yields each row-insert event on the ``pulses`` table.  It is started once
    on app startup and terminates gracefully on shutdown.
    """
    if not settings.has_supabase or settings.dry_run:
        # No Supabase — yield nothing. Clients remain connected but receive
        # only the periodic ping from the handler below.
        log.info("supabase realtime disabled (dry_run=%s, has_supabase=%s)",
                 settings.dry_run, settings.has_supabase)
        return

    from realtime import connect  # type: ignore[import-not-found]  # supabase-realtime pkg

    # Supabase realtime URL is derived from the project URL
    url = settings.supabase_url.replace("https://", "wss://") + "/realtime/v1/websocket"
    params = {
        "apikey": settings.supabase_service_key,
        "vsn": "1.0.0",
        "events": "postgres_changes",
        "table": "pulses",
        "schema": "public",
    }
    log.info("connecting to supabase realtime at %s", url)
    async for event in connect(url, params):
        # Only forward row-inserts to the dashboard
        if event.get("event") == "INSERT":
            yield {
                "type": "pulse.created",
                "data": event.get("new", {}),
            }


@router.websocket("/pulses")
async def ws_pulses(
    websocket: WebSocket,
    settings: Settings = Depends(get_settings),
) -> None:
    """Push channel for pulse-insert events.

    The handler:
    1. Accepts the client and registers it with ``manager``.
    2. Spawns a background task that drains the Supabase event stream and
       broadcasts to all connected clients.
    3. Keeps the socket open reading pings until the client disconnects.
    """
    await manager.connect(websocket)

    async def _pump() -> None:
        async for event in _supabase_event_stream(settings):
            await manager.broadcast(event)

    pump_task = asyncio.create_task(_pump())
    try:
        while True:
            # We don't expect inbound messages, but reading lets us detect
            # disconnects promptly and apply backpressure.
            msg = await websocket.receive_text()
            if msg == "ping":
                await websocket.send_text(json.dumps({"type": "pong"}))
    except WebSocketDisconnect:
        log.info("realtime client disconnected cleanly")
    except Exception:  # pragma: no cover - defensive
        log.exception("realtime handler error")
    finally:
        pump_task.cancel()
        await manager.disconnect(websocket)


@router.websocket("/pulses/test")
async def ws_pulses_test(websocket: WebSocket) -> None:
    """Heartbeat-only endpoint used by the frontend during local dev."""
    await websocket.accept()
    try:
        while True:
            msg = await websocket.receive_text()
            if msg == "ping":
                await websocket.send_text(json.dumps({"type": "pong", "ok": True}))
    except WebSocketDisconnect:
        return
    except Exception:  # pragma: no cover
        log.exception("test handler error")


__all__ = ["router", "manager"]
"""FastAPI application entrypoint.

Run locally:

    uvicorn main:app --reload --port 8000
"""

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.realtime import router as realtime_router  # noqa: F401  (mounted below)
from api.routes import router as api_router
from core.config import get_settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s :: %(message)s",
)
log = logging.getLogger("deadzone.api")


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="DeadZone API",
        version="0.1.0",
        description="Crisis-coordination API for the DeadZone Telegram bot + web dashboard.",
        docs_url="/docs",
        redoc_url=None,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(api_router)
    app.include_router(realtime_router, prefix="/ws", tags=["realtime"])

    @app.on_event("startup")
    async def _log_startup_state() -> None:  # pragma: no cover - thin wiring
        flags = {
            "supabase": settings.has_supabase,
            "telegram": settings.has_telegram,
            "dry_run": settings.dry_run,
            "origins": settings.origins_list,
        }
        log.info("DeadZone API starting up :: %s", flags)

    return app


app = create_app()

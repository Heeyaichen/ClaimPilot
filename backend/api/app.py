"""FastAPI application factory for ClaimPilot."""

from __future__ import annotations

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.adjuster_routes import router as adjuster_router
from backend.api.routes import router

_cors_raw = os.environ.get("CORS_ALLOWED_ORIGINS", "")
ALLOWED_ORIGINS = _cors_raw.split(",") if _cors_raw else []


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="ClaimPilot",
        version="0.4.0",
        description="AI-powered insurance claims autopilot — Phase 4 Voice Live API",
    )

    if ALLOWED_ORIGINS:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=ALLOWED_ORIGINS,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    app.include_router(router)
    app.include_router(adjuster_router)
    return app


app = create_app()

"""FastAPI application factory for ClaimPilot."""

from __future__ import annotations

from fastapi import FastAPI

from backend.api.adjuster_routes import router as adjuster_router
from backend.api.routes import router


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="ClaimPilot",
        version="0.4.0",
        description="AI-powered insurance claims autopilot — Phase 4 Voice Live API",
    )
    app.include_router(router)
    app.include_router(adjuster_router)
    return app


app = create_app()

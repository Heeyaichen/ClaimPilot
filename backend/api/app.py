"""FastAPI application factory for ClaimPilot."""

from __future__ import annotations

from fastapi import FastAPI

from backend.api.routes import router


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="ClaimPilot",
        version="0.2.0",
        description="AI-powered insurance claims autopilot — Phase 2 API",
    )
    app.include_router(router)
    return app


app = create_app()

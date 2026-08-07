"""FastAPI application factory — README §20.1 Passo B, roadmap Phase 17.

Interactive docs (`/docs`/`/redoc`) are disabled: FastAPI's default
Swagger UI/ReDoc pages load their JS/CSS from a CDN, which
`specs/mission.md` principle 1's "no CDN assets" forbids. `/openapi.json`
stays enabled — it's generated in-process with no network activity.
Binding to `127.0.0.1` only happens at serve time (`cli/main.py`'s
`serve` command); this module never chooses a host itself.
"""

from __future__ import annotations

from fastapi import FastAPI

from backend.app.api.routes import router


def create_app() -> FastAPI:
    app = FastAPI(title="Local Media Organizer API", docs_url=None, redoc_url=None)
    app.include_router(router, prefix="/api")
    return app


app = create_app()

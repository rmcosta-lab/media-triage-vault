"""FastAPI application factory — README §20.1 Passo B, roadmap Phases 17/20.

Interactive docs (`/docs`/`/redoc`) are disabled: FastAPI's default
Swagger UI/ReDoc pages load their JS/CSS from a CDN, which
`specs/mission.md` principle 1's "no CDN assets" forbids. `/openapi.json`
stays enabled — it's generated in-process with no network activity.
Binding to `127.0.0.1` only happens at serve time (`cli/main.py`'s
`serve` command); this module never chooses a host itself.

CORS is scoped to `localhost`/`127.0.0.1` on any port (a regex, not a
fixed origin list): the Next.js dev server and the eventual production
build both run on loopback but not necessarily on a fixed port, and the
browser enforces CORS on every cross-port `fetch`/`EventSource` call even
though both ends are local. This never opens the API to a non-loopback
origin.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.api.routes import router

_LOCAL_ORIGIN_REGEX = r"^http://(localhost|127\.0\.0\.1)(:\d+)?$"


def create_app() -> FastAPI:
    app = FastAPI(title="Local Media Organizer API", docs_url=None, redoc_url=None)
    app.add_middleware(
        CORSMiddleware,
        allow_origin_regex=_LOCAL_ORIGIN_REGEX,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(router, prefix="/api")
    return app


app = create_app()

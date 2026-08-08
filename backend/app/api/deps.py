"""FastAPI dependencies — roadmap Phase 17.

`get_session_dependency` opens the standard database, matching the
CLI's own per-invocation `get_engine()`/`create_db_and_tables()`
pattern. `get_thumbnail_cache_dir_dependency` resolves the on-demand
thumbnail cache directory. Both are overridden in tests via
`app.dependency_overrides` to point at temp paths instead of the real
repo's `runtime/` tree.
"""

from __future__ import annotations

from collections.abc import Iterator
from functools import lru_cache
from pathlib import Path

from sqlalchemy import Engine
from sqlmodel import Session

from backend.app.core.db import create_db_and_tables, get_database_path, get_engine

_REPO_ROOT = Path(__file__).resolve().parents[3]


@lru_cache(maxsize=1)
def get_api_engine() -> Engine:
    """Return the process-wide API engine and initialize its schema once."""
    engine = get_engine(get_database_path())
    create_db_and_tables(engine)
    return engine


def get_session_dependency() -> Iterator[Session]:
    with Session(get_api_engine()) as session:
        yield session


def get_thumbnail_cache_dir_dependency() -> Path:
    directory = _REPO_ROOT / "runtime" / "thumbnails" / "api"
    directory.mkdir(parents=True, exist_ok=True)
    return directory

"""Database engine and session management.

The SQLite file lives under ``runtime/database/``, anchored to the repo root
rather than the process's working directory — same pattern as
``backend/app/core/tools.py``'s tool resolver. Schema is created via
``SQLModel.metadata.create_all``; there is no migrations framework yet (see
``specs/2026-08-07-phase-3-data-model-sqlite/requirements.md``).
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import Engine
from sqlmodel import Session, SQLModel, create_engine

_REPO_ROOT = Path(__file__).resolve().parents[3]
_DATABASE_PATH = _REPO_ROOT / "runtime" / "database" / "media_organizer.db"


def get_database_path() -> Path:
    """Return the SQLite database path, creating its parent directory if needed."""
    _DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    return _DATABASE_PATH


def get_engine(path: Path | None = None) -> Engine:
    """Create an engine for ``path`` (defaults to the standard database path)."""
    database_path = path if path is not None else get_database_path()
    return create_engine(f"sqlite:///{database_path}")


def create_db_and_tables(engine: Engine) -> None:
    """Create all SQLModel tables that do not already exist."""
    SQLModel.metadata.create_all(engine)


@contextmanager
def get_session(engine: Engine) -> Iterator[Session]:
    """Yield a session bound to ``engine``."""
    with Session(engine) as session:
        yield session

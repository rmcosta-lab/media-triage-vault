"""``Scan`` table — README §24.1."""

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from backend.app.models.media_file import MediaFile


class Scan(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    source_root: str
    recursive: bool
    status: str
    total_files: int = 0
    processed_files: int = 0
    total_bytes: int = 0
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    started_at: datetime | None = None
    finished_at: datetime | None = None

    # No `from __future__ import annotations` in this module: SQLModel's relationship
    # resolution reads the *raw* class annotation at runtime, so the "MediaFile" forward
    # reference must stay an actual quoted string, not source text stringified by PEP 563.
    media_files: list["MediaFile"] = Relationship(back_populates="scan")

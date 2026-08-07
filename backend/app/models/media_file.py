"""``MediaFile`` table — README §24.2."""

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Optional

from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from backend.app.models.media_metadata import MediaMetadata
    from backend.app.models.scan import Scan


class MediaFile(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    scan_id: int = Field(foreign_key="scan.id")
    absolute_path: str
    relative_path: str
    file_name: str
    extension: str
    mime_type: str | None = None
    file_type: str | None = None
    size_bytes: int
    modified_at: datetime | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    width: int | None = None
    height: int | None = None
    duration_seconds: float | None = None
    metadata_json: str | None = None
    media_kind: str | None = None
    extension_mismatch: bool = False
    processing_status: str
    error_code: str | None = None
    error_message: str | None = None

    scan: "Scan" = Relationship(back_populates="media_files")
    media_metadata: Optional["MediaMetadata"] = Relationship(back_populates="media_file")

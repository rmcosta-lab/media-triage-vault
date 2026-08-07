"""``MediaMetadata`` table — normalized ExifTool fields, README §8.2, roadmap Phase 6."""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from backend.app.models.media_file import MediaFile


class MediaMetadata(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    media_file_id: int = Field(foreign_key="mediafile.id", unique=True)
    capture_datetime: datetime | None = None
    make: str | None = None
    model: str | None = None
    software: str | None = None
    lens_model: str | None = None
    camera_serial_number: str | None = None
    gps_latitude: float | None = None
    gps_longitude: float | None = None
    gps_position_raw: str | None = None
    location_information: str | None = None
    handler_description: str | None = None
    compressor_name: str | None = None
    encoder: str | None = None
    rotation: int | None = None
    profile_description: str | None = None
    color_space: str | None = None
    raw_json: str | None = None

    media_file: "MediaFile" = Relationship(back_populates="media_metadata")

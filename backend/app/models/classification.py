"""``Classification`` table — README §24.3, roadmap Phase 8.

Splits the automatic result from any later manual correction (README
§15.3): ``automatic_routing_group`` is what the rule engine decided,
``manual_routing_group`` is filled in by a Phase 12 override, and
``effective_routing_group`` is whichever of the two currently applies.
"""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from backend.app.models.media_file import MediaFile


class Classification(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    media_file_id: int = Field(foreign_key="mediafile.id", unique=True)
    media_kind: str
    source_origin: str
    image_format: str
    automatic_routing_group: str
    manual_routing_group: str | None = None
    effective_routing_group: str
    confidence: float
    requires_review: bool
    reasons_json: str
    device_make: str | None = None
    device_model: str | None = None
    captured_at: datetime | None = None
    gps_latitude: float | None = None
    gps_longitude: float | None = None
    country_code: str | None = None
    country_name: str | None = None

    media_file: "MediaFile" = Relationship(back_populates="classification")

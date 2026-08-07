"""Read-only API response schemas — README §25, roadmap Phase 17.

Deliberately filtered views, not full model dumps — same pattern as
`cli/scan_report.py`'s `_media_file_to_dict`/`_media_metadata_to_dict`.
`ClassificationRead`/`MediaMetadataRead` omit every coordinate-shaped
field (`gps_latitude`/`gps_longitude`/`gps_position_raw`/
`location_information`), and `MediaFileRead` omits `absolute_path` — a
browser client never needs a full local filesystem path.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ScanRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    source_root: str
    recursive: bool
    status: str
    total_files: int
    processed_files: int
    total_bytes: int
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None


class MediaFileRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    scan_id: int
    relative_path: str
    file_name: str
    extension: str
    mime_type: str | None
    file_type: str | None
    media_kind: str | None
    size_bytes: int
    width: int | None
    height: int | None
    duration_seconds: float | None
    extension_mismatch: bool
    modified_at: datetime | None
    processing_status: str
    error_code: str | None
    error_message: str | None


class ClassificationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    media_file_id: int
    media_kind: str
    source_origin: str
    image_format: str
    automatic_routing_group: str
    manual_routing_group: str | None
    effective_routing_group: str
    confidence: float
    requires_review: bool
    reasons_json: str
    device_make: str | None
    device_model: str | None
    captured_at: datetime | None
    country_code: str | None
    country_name: str | None
    override_timestamp: datetime | None


class ScanCreateRequest(BaseModel):
    source_root: str
    recursive: bool = True


class JobRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    job_type: str
    scan_id: int | None
    status: str
    total: int
    processed: int
    message: str | None
    error_code: str | None
    error_message: str | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None


class MediaMetadataRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    media_file_id: int
    capture_datetime: datetime | None
    make: str | None
    model: str | None
    software: str | None
    lens_model: str | None
    camera_serial_number: str | None
    handler_description: str | None
    compressor_name: str | None
    encoder: str | None
    rotation: int | None
    profile_description: str | None
    color_space: str | None

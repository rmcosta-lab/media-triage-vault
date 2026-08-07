"""Error log and JSON inventory export for `media-organizer scan` — roadmap Phase 7."""

from __future__ import annotations

import json
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlmodel import Session

from backend.app.models.media_file import MediaFile
from backend.app.models.media_metadata import MediaMetadata
from backend.app.repositories.media_metadata_repository import MediaMetadataRepository


def write_error_log(path: Path, rows: Sequence[MediaFile]) -> int:
    """Write one line per errored row to `path`. Returns the count written."""
    errored = [row for row in rows if row.error_code is not None]
    lines = [
        f"{row.relative_path}: {row.error_code} — {row.error_message or ''}" for row in errored
    ]
    path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    return len(errored)


def write_inventory_json(path: Path, session: Session, rows: Sequence[MediaFile]) -> None:
    """Write the full inventory (one object per row, nested metadata) as a JSON array."""
    metadata_repository = MediaMetadataRepository(session)
    inventory = []
    for row in rows:
        entry = _media_file_to_dict(row)
        media_metadata = (
            metadata_repository.get_by_media_file_id(row.id) if row.id is not None else None
        )
        entry["metadata"] = (
            _media_metadata_to_dict(media_metadata) if media_metadata is not None else None
        )
        inventory.append(entry)
    path.write_text(
        json.dumps(inventory, default=_json_default, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def _json_default(value: Any) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def _media_file_to_dict(row: MediaFile) -> dict[str, Any]:
    return {
        "id": row.id,
        "relative_path": row.relative_path,
        "absolute_path": row.absolute_path,
        "file_name": row.file_name,
        "extension": row.extension,
        "media_kind": row.media_kind,
        "mime_type": row.mime_type,
        "file_type": row.file_type,
        "size_bytes": row.size_bytes,
        "width": row.width,
        "height": row.height,
        "duration_seconds": row.duration_seconds,
        "extension_mismatch": row.extension_mismatch,
        "modified_at": row.modified_at,
        "processing_status": row.processing_status,
        "error_code": row.error_code,
        "error_message": row.error_message,
    }


def _media_metadata_to_dict(media_metadata: MediaMetadata) -> dict[str, Any]:
    return {
        "capture_datetime": media_metadata.capture_datetime,
        "make": media_metadata.make,
        "model": media_metadata.model,
        "software": media_metadata.software,
        "lens_model": media_metadata.lens_model,
        "camera_serial_number": media_metadata.camera_serial_number,
        "gps_latitude": media_metadata.gps_latitude,
        "gps_longitude": media_metadata.gps_longitude,
        "gps_position_raw": media_metadata.gps_position_raw,
        "location_information": media_metadata.location_information,
        "handler_description": media_metadata.handler_description,
        "compressor_name": media_metadata.compressor_name,
        "encoder": media_metadata.encoder,
        "rotation": media_metadata.rotation,
        "profile_description": media_metadata.profile_description,
        "color_space": media_metadata.color_space,
    }

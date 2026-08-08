"""Batch metadata extraction — README §8 "Extração de metadados", roadmap Phase 6.

Runs ExifTool once per batch of pending ``MediaFile`` rows (never one
process per file), normalizes the README §8.2 field list onto a
``MediaMetadata`` row per file, and validates every ``media_kind="video"``
row with FFprobe, marking unreadable videos per README §9.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlmodel import Session

from backend.app.core.tools import run_tool
from backend.app.models.media_file import MediaFile
from backend.app.models.media_metadata import MediaMetadata
from backend.app.repositories.media_file_repository import MediaFileRepository
from backend.app.repositories.media_metadata_repository import MediaMetadataRepository

DEFAULT_BATCH_SIZE = 200

# README §8.2 — the exact field list to request from ExifTool.
EXIFTOOL_FIELDS: tuple[str, ...] = (
    "FileName",
    "Directory",
    "FileType",
    "MIMEType",
    "FileSize",
    "ImageWidth",
    "ImageHeight",
    "Duration",
    "CreateDate",
    "DateTimeOriginal",
    "MediaCreateDate",
    "TrackCreateDate",
    "Make",
    "Model",
    "Software",
    "LensModel",
    "CameraSerialNumber",
    "GPSLatitude",
    "GPSLongitude",
    "GPSPosition",
    "GPSCoordinates",
    "LocationInformation",
    "HandlerDescription",
    "CompressorName",
    "Encoder",
    "Rotation",
    "ProfileDescription",
    "ColorSpace",
)

_CAPTURE_DATETIME_FIELDS: tuple[str, ...] = (
    "DateTimeOriginal",
    "CreateDate",
    "MediaCreateDate",
    "TrackCreateDate",
)

_METADATA_VALUE_FIELDS: tuple[str, ...] = (
    "capture_datetime",
    "make",
    "model",
    "software",
    "lens_model",
    "camera_serial_number",
    "gps_latitude",
    "gps_longitude",
    "gps_position_raw",
    "location_information",
    "handler_description",
    "compressor_name",
    "encoder",
    "rotation",
    "profile_description",
    "color_space",
    "raw_json",
)


class MetadataBatchError(RuntimeError):
    """Raised when an ExifTool batch response doesn't match the request shape."""


@dataclass(frozen=True)
class MetadataSummary:
    """Roll-up counters for a scan-level metadata extraction run."""

    extracted: int = 0
    video_ok: int = 0
    video_unreadable: int = 0
    metadata_errors: int = 0


def _parse_exiftool_datetime(value: Any) -> datetime | None:
    """Parse an ExifTool ``"YYYY:MM:DD HH:MM:SS"`` (optionally with a UTC offset)."""
    if not isinstance(value, str):
        return None
    text = value.strip()
    for fmt in ("%Y:%m:%d %H:%M:%S%z", "%Y:%m:%d %H:%M:%S"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


def _resolve_capture_datetime(tags: dict[str, Any]) -> datetime | None:
    for field in _CAPTURE_DATETIME_FIELDS:
        parsed = _parse_exiftool_datetime(tags.get(field))
        if parsed is not None:
            return parsed
    return None


def _as_str(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)


def _as_float(value: Any) -> float | None:
    if isinstance(value, int | float):
        return float(value)
    return None


def _as_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    return None


def _build_media_metadata(media_file_id: int, tags: dict[str, Any]) -> MediaMetadata:
    raw_subset = {field: tags[field] for field in EXIFTOOL_FIELDS if field in tags}
    return MediaMetadata(
        media_file_id=media_file_id,
        capture_datetime=_resolve_capture_datetime(tags),
        make=_as_str(tags.get("Make")),
        model=_as_str(tags.get("Model")),
        software=_as_str(tags.get("Software")),
        lens_model=_as_str(tags.get("LensModel")),
        camera_serial_number=_as_str(tags.get("CameraSerialNumber")),
        gps_latitude=_as_float(tags.get("GPSLatitude")),
        gps_longitude=_as_float(tags.get("GPSLongitude")),
        gps_position_raw=_as_str(tags.get("GPSPosition") or tags.get("GPSCoordinates")),
        location_information=_as_str(tags.get("LocationInformation")),
        handler_description=_as_str(tags.get("HandlerDescription")),
        compressor_name=_as_str(tags.get("CompressorName")),
        encoder=_as_str(tags.get("Encoder")),
        rotation=_as_int(tags.get("Rotation")),
        profile_description=_as_str(tags.get("ProfileDescription")),
        color_space=_as_str(tags.get("ColorSpace")),
        raw_json=json.dumps(raw_subset, ensure_ascii=False),
    )


def _run_exiftool_batch(paths: Sequence[Path]) -> list[dict[str, Any]]:
    """Run one ExifTool process over ``paths``, returning one tag dict per path, in order."""
    tag_args = [f"-{field}" for field in EXIFTOOL_FIELDS]
    args = ["-j", "-n", *tag_args, *(str(path) for path in paths)]
    result = run_tool("exiftool", args, check=False)
    try:
        payload: list[dict[str, Any]] = json.loads(result.stdout)
    except json.JSONDecodeError as error:
        raise MetadataBatchError(f"ExifTool returned non-JSON output: {error}") from error
    if len(payload) != len(paths):
        raise MetadataBatchError(
            f"ExifTool batch returned {len(payload)} entries for {len(paths)} paths"
        )
    return payload


def _apply_tags_to_media_file(row: MediaFile, tags: dict[str, Any]) -> None:
    file_type = _as_str(tags.get("FileType"))
    if file_type is not None:
        row.file_type = file_type
    mime_type = _as_str(tags.get("MIMEType"))
    if mime_type is not None:
        row.mime_type = mime_type
    width = _as_int(tags.get("ImageWidth"))
    if width is not None:
        row.width = width
    height = _as_int(tags.get("ImageHeight"))
    if height is not None:
        row.height = height
    duration = _as_float(tags.get("Duration"))
    if duration is not None:
        row.duration_seconds = duration


def _merge_media_metadata(target: MediaMetadata, source: MediaMetadata) -> None:
    """Copy extracted values while preserving the existing row identity."""
    for field_name in _METADATA_VALUE_FIELDS:
        setattr(target, field_name, getattr(source, field_name))


def _validate_video(row: MediaFile) -> bool:
    """Confirm a `media_kind="video"` row has a decodable video stream (README §9)."""
    result = run_tool(
        "ffprobe",
        ["-v", "error", "-print_format", "json", "-show_streams", row.absolute_path],
        check=False,
    )
    has_video_stream = False
    if result.returncode == 0:
        try:
            payload = json.loads(result.stdout)
            has_video_stream = any(
                stream.get("codec_type") == "video" for stream in payload.get("streams", [])
            )
        except json.JSONDecodeError:
            has_video_stream = False

    if not has_video_stream:
        row.processing_status = "error"
        row.error_code = "VIDEO_UNREADABLE"
        row.error_message = result.stderr.strip() or "FFprobe found no readable video stream"
        return False
    return True


def extract_metadata_for_scan(
    session: Session,
    scan_id: int,
    *,
    batch_size: int = DEFAULT_BATCH_SIZE,
    on_progress: Callable[[int], None] | None = None,
    should_cancel: Callable[[], bool] | None = None,
) -> MetadataSummary:
    """Extract and persist README §8.2 metadata for every pending row of ``scan_id``."""
    media_file_repository = MediaFileRepository(session)
    media_metadata_repository = MediaMetadataRepository(session)

    rows = [
        row
        for row in media_file_repository.list_by_scan(scan_id)
        if row.processing_status == "pending" and row.media_kind in ("image", "video")
    ]

    extracted = video_ok = video_unreadable = metadata_errors = 0
    processed = 0

    for batch_start in range(0, len(rows), batch_size):
        if should_cancel is not None and should_cancel():
            break
        batch = rows[batch_start : batch_start + batch_size]
        paths = [Path(row.absolute_path) for row in batch]
        tag_results = _run_exiftool_batch(paths)
        media_file_ids = [_require_id(row) for row in batch]
        existing_metadata = {
            item.media_file_id: item
            for item in media_metadata_repository.list_by_media_file_ids(media_file_ids)
        }
        metadata_to_save: list[MediaMetadata] = []

        try:
            for row, tags in zip(batch, tag_results, strict=True):
                media_file_id = _require_id(row)
                error = tags.get("Error")
                if error is not None:
                    row.error_code = "METADATA_READ_ERROR"
                    row.error_message = str(error)
                    candidate = MediaMetadata(media_file_id=media_file_id)
                    metadata_errors += 1
                else:
                    _apply_tags_to_media_file(row, tags)
                    candidate = _build_media_metadata(media_file_id, tags)
                    extracted += 1

                persisted = existing_metadata.get(media_file_id)
                if persisted is None:
                    metadata_to_save.append(candidate)
                else:
                    _merge_media_metadata(persisted, candidate)
                    metadata_to_save.append(persisted)

                if row.media_kind == "video" and error is None:
                    if _validate_video(row):
                        video_ok += 1
                    else:
                        video_unreadable += 1

            session.add_all(batch)
            session.add_all(metadata_to_save)
            session.commit()
        except Exception:
            session.rollback()
            raise

        processed += len(batch)
        if on_progress is not None:
            on_progress(processed)

    return MetadataSummary(
        extracted=extracted,
        video_ok=video_ok,
        video_unreadable=video_unreadable,
        metadata_errors=metadata_errors,
    )


def _require_id(row: MediaFile) -> int:
    if row.id is None:
        raise ValueError("MediaFile row has no id — must be persisted before metadata extraction")
    return row.id

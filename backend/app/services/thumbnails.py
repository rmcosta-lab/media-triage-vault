"""Thumbnail generation — README §19.1/§19.4, roadmap Phase 13.

Dispatches by ``MediaFile.media_kind``/extension to the right decoder
(Pillow, pillow-heif, rawpy, or an FFmpeg frame grab via the Phase 2
resolver) and writes a small JPEG preview. Every failure is caught per
file and reported, never raised — a corrupt or unreadable file must not
abort the rest of the batch (same pattern as Phase 4's scanner and
Phase 6's metadata extraction).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import pillow_heif
import rawpy
from PIL import Image, UnidentifiedImageError
from rawpy._rawpy import (  # rawpy's own __init__ only re-exports these under TYPE_CHECKING
    LibRawError,
    LibRawNoThumbnailError,
    LibRawUnsupportedThumbnailError,
    ThumbFormat,
)
from sqlmodel import Session

from backend.app.core.tools import run_tool
from backend.app.models.media_file import MediaFile
from backend.app.repositories.media_file_repository import MediaFileRepository
from backend.app.services.classification import RAW_EXTENSIONS

THUMBNAIL_MAX_DIMENSION = 320
THUMBNAIL_QUALITY = 82

pillow_heif.register_heif_opener()


@dataclass(frozen=True)
class ThumbnailResult:
    """The outcome of generating one file's thumbnail."""

    success: bool
    error_code: str | None = None
    error_message: str | None = None


@dataclass(frozen=True)
class ThumbnailSummary:
    """Roll-up counters for a scan-level thumbnail generation run."""

    generated: int = 0
    failed: int = 0


def _save_image_thumbnail(image: Image.Image, destination: Path) -> None:
    if image.mode not in ("RGB", "L"):
        background = Image.new("RGB", image.size, (255, 255, 255))
        rgba = image.convert("RGBA")
        background.paste(rgba, mask=rgba.split()[-1])
        image = background
    image.thumbnail((THUMBNAIL_MAX_DIMENSION, THUMBNAIL_MAX_DIMENSION))
    image.save(destination, format="JPEG", quality=THUMBNAIL_QUALITY)


def _thumbnail_from_image(path: Path, destination: Path) -> ThumbnailResult:
    try:
        with Image.open(path) as image:
            _save_image_thumbnail(image, destination)
        return ThumbnailResult(success=True)
    except (UnidentifiedImageError, OSError) as error:
        return ThumbnailResult(
            success=False, error_code="THUMBNAIL_DECODE_ERROR", error_message=str(error)
        )


def _thumbnail_from_raw(path: Path, destination: Path) -> ThumbnailResult:
    try:
        with rawpy.imread(str(path)) as raw:
            try:
                thumb = raw.extract_thumb()
                if thumb.format == ThumbFormat.JPEG:
                    destination.write_bytes(thumb.data)
                    return ThumbnailResult(success=True)
                if thumb.format == ThumbFormat.BITMAP and not isinstance(thumb.data, bytes):
                    _save_image_thumbnail(Image.fromarray(thumb.data), destination)
                    return ThumbnailResult(success=True)
            except (LibRawNoThumbnailError, LibRawUnsupportedThumbnailError):
                pass
            rgb = raw.postprocess()
            _save_image_thumbnail(Image.fromarray(rgb), destination)
        return ThumbnailResult(success=True)
    except (LibRawError, OSError) as error:
        return ThumbnailResult(
            success=False, error_code="THUMBNAIL_RAW_DECODE_ERROR", error_message=str(error)
        )


def _thumbnail_from_video(path: Path, destination: Path) -> ThumbnailResult:
    try:
        result = run_tool(
            "ffmpeg",
            [
                "-ss",
                "00:00:00",
                "-i",
                str(path),
                "-frames:v",
                "1",
                "-update",
                "1",
                "-vf",
                f"scale='min({THUMBNAIL_MAX_DIMENSION},iw)':-2",
                "-y",
                str(destination),
            ],
            timeout=30,
        )
    except OSError as error:
        return ThumbnailResult(
            success=False, error_code="THUMBNAIL_VIDEO_ERROR", error_message=str(error)
        )
    if result.returncode != 0 or not destination.is_file():
        destination.unlink(missing_ok=True)
        return ThumbnailResult(
            success=False,
            error_code="THUMBNAIL_VIDEO_ERROR",
            error_message=result.stderr.strip(),
        )
    return ThumbnailResult(success=True)


def generate_thumbnail(media_file: MediaFile, destination: Path) -> ThumbnailResult:
    """Generate a JPEG thumbnail for ``media_file`` at ``destination``."""
    path = Path(media_file.absolute_path)
    extension = (media_file.extension or "").lower()

    if media_file.media_kind == "video":
        return _thumbnail_from_video(path, destination)
    if extension in RAW_EXTENSIONS:
        return _thumbnail_from_raw(path, destination)
    if media_file.media_kind == "image":
        return _thumbnail_from_image(path, destination)
    return ThumbnailResult(
        success=False,
        error_code="UNSUPPORTED_MEDIA_KIND",
        error_message=f"No thumbnail strategy for media_kind={media_file.media_kind!r}",
    )


def generate_thumbnails_for_scan(
    session: Session,
    scan_id: int,
    thumbnails_dir: Path,
    *,
    on_progress: Callable[[MediaFile, ThumbnailResult], None] | None = None,
) -> dict[int, ThumbnailResult]:
    """Generate thumbnails for every eligible ``image``/``video`` row of ``scan_id``.

    Returns a ``{media_file_id: ThumbnailResult}`` map for every row attempted.
    Rows with no ``media_kind`` in ``("image", "video")`` or that already carry
    an extraction error (e.g. ``VIDEO_UNREADABLE``) are skipped entirely.
    """
    thumbnails_dir.mkdir(parents=True, exist_ok=True)
    repository = MediaFileRepository(session)
    results: dict[int, ThumbnailResult] = {}

    for media in repository.list_by_scan(scan_id):
        if media.id is None or media.media_kind not in ("image", "video"):
            continue
        if media.error_code is not None:
            continue

        destination = thumbnails_dir / f"{media.id}.jpg"
        result = generate_thumbnail(media, destination)
        results[media.id] = result
        if on_progress is not None:
            on_progress(media, result)

    return results


def summarize_thumbnail_results(results: dict[int, ThumbnailResult]) -> ThumbnailSummary:
    generated = sum(1 for result in results.values() if result.success)
    failed = len(results) - generated
    return ThumbnailSummary(generated=generated, failed=failed)

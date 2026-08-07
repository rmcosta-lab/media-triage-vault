"""Media type detection — README §6.4 "Detecção do tipo real", roadmap Phase 5.

Combines the file extension, a fixed extension->MIME table, and a file
signature (magic bytes) read from a small header, so a file's type doesn't
depend solely on its extension. ExifTool ``FileType`` and FFprobe (the
other two signals README §6.4 lists) are Phase 6 — this phase is pure
Python, no external tool invocation.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from sqlmodel import Session

from backend.app.core.media_signatures import EXTENSION_CATEGORY, EXTENSION_MIME, MediaCategory
from backend.app.models.media_file import MediaFile
from backend.app.repositories.media_file_repository import MediaFileRepository

HEADER_SIZE = 64

_HEIC_BRANDS: frozenset[bytes] = frozenset(
    {b"heic", b"heix", b"hevc", b"heim", b"heis", b"hevm", b"hevs", b"mif1", b"msf1"}
)


@dataclass(frozen=True)
class MediaTypeDetection:
    """The outcome of combining extension, MIME, and signature for one file."""

    media_kind: str
    mime_type: str | None
    extension_mismatch: bool
    reason: str


@dataclass(frozen=True)
class MediaTypeSummary:
    """Roll-up counters for a scan-level detection run."""

    images: int = 0
    videos: int = 0
    unsupported: int = 0
    mismatches: int = 0
    read_errors: int = 0


def read_header(path: Path, size: int = HEADER_SIZE) -> bytes:
    """Read at most ``size`` bytes from the start of ``path``.

    Raises ``OSError`` on any access failure — callers decide how to record it.
    """
    with path.open("rb") as file_handle:
        return file_handle.read(size)


def _sniff_signature(header: bytes) -> MediaCategory | None:
    """Return the media category the file's content actually looks like, if recognized."""
    if header.startswith(b"\xff\xd8\xff"):
        return "image"
    if header.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image"
    if header[:6] in (b"GIF87a", b"GIF89a"):
        return "image"
    if header.startswith(b"BM"):
        return "image"
    if header[:4] == b"RIFF" and len(header) >= 12:
        riff_subtype = header[8:12]
        if riff_subtype == b"WEBP":
            return "image"
        if riff_subtype == b"AVI ":
            return "video"
    if header[:4] in (b"II*\x00", b"MM\x00*"):
        return "image"
    if header.startswith(b"FUJIFILMCCD-RAW"):
        return "image"
    if len(header) >= 12 and header[4:8] == b"ftyp":
        brand = header[8:12]
        return "image" if brand in _HEIC_BRANDS else "video"
    if header.startswith(b"\x1a\x45\xdf\xa3"):
        return "video"
    return None


def detect_media_type(path: Path, extension: str) -> MediaTypeDetection:
    """Combine extension, MIME, and file signature into a single detection result."""
    normalized_extension = extension.lower()
    extension_category = EXTENSION_CATEGORY.get(normalized_extension)
    mime_type = EXTENSION_MIME.get(normalized_extension)

    header = read_header(path)
    signature_category = _sniff_signature(header)

    media_kind: str
    if signature_category is not None:
        media_kind = signature_category
    elif extension_category is not None:
        media_kind = extension_category
    else:
        media_kind = "unsupported"

    extension_mismatch = (
        extension_category is not None
        and signature_category is not None
        and extension_category != signature_category
    )

    reason = (
        f"signature={signature_category or 'unrecognized'}, "
        f"extension={extension_category or 'unknown'} ({normalized_extension or 'none'})"
    )

    return MediaTypeDetection(
        media_kind=media_kind,
        mime_type=mime_type,
        extension_mismatch=extension_mismatch,
        reason=reason,
    )


def detect_media_types_for_scan(
    session: Session,
    scan_id: int,
    *,
    on_progress: Callable[[int], None] | None = None,
    should_cancel: Callable[[], bool] | None = None,
) -> MediaTypeSummary:
    """Run detection over every pending ``MediaFile`` row of ``scan_id`` and persist results."""
    repository = MediaFileRepository(session)
    pending_rows = [
        row for row in repository.list_by_scan(scan_id) if row.processing_status == "pending"
    ]

    images = videos = unsupported = mismatches = read_errors = 0

    for index, row in enumerate(pending_rows, start=1):
        if should_cancel is not None and should_cancel():
            break
        _detect_and_update_row(repository, row)
        if row.error_code == "SIGNATURE_READ_ERROR":
            read_errors += 1
        elif row.media_kind == "image":
            images += 1
        elif row.media_kind == "video":
            videos += 1
        else:
            unsupported += 1
        if row.extension_mismatch:
            mismatches += 1
        if on_progress is not None:
            on_progress(index)

    return MediaTypeSummary(
        images=images,
        videos=videos,
        unsupported=unsupported,
        mismatches=mismatches,
        read_errors=read_errors,
    )


def _detect_and_update_row(repository: MediaFileRepository, row: MediaFile) -> None:
    try:
        detection = detect_media_type(Path(row.absolute_path), row.extension)
    except OSError as error:
        row.error_code = "SIGNATURE_READ_ERROR"
        row.error_message = str(error)
        repository.update(row)
        return

    row.media_kind = detection.media_kind
    row.mime_type = detection.mime_type
    row.extension_mismatch = detection.extension_mismatch
    repository.update(row)

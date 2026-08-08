"""Recursive filesystem scanner — README §7 "Descoberta de arquivos", roadmap Phase 4.

Discovery only: walks a root folder, records size/mtime/access errors as
``MediaFile`` rows under a ``Scan``, and never reads file content or writes
to the scanned tree. Media type detection (Phase 5) and metadata extraction
(Phase 6) populate the remaining columns on top of these rows.
"""

from __future__ import annotations

import os
from collections.abc import Callable, Iterator, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from sqlmodel import Session

from backend.app.core.ignore_patterns import is_ignored_dir, is_ignored_file
from backend.app.core.paths import absolute_nfc, relative_nfc, to_nfc
from backend.app.models.media_file import MediaFile
from backend.app.models.scan import Scan
from backend.app.repositories.media_file_repository import MediaFileRepository
from backend.app.repositories.scan_repository import ScanRepository

DEFAULT_BATCH_SIZE = 200


@dataclass(frozen=True)
class ScanProgress:
    """A snapshot of scan progress, reported after each flushed batch."""

    processed_files: int
    total_bytes_so_far: int


class InvalidSourceRootError(ValueError):
    """Raised when the scan source root does not exist or is not a directory."""


def scan_folder(
    session: Session,
    source_root: Path,
    *,
    recursive: bool,
    exclude_dirs: Sequence[Path] = (),
    batch_size: int = DEFAULT_BATCH_SIZE,
    on_progress: Callable[[ScanProgress], None] | None = None,
    should_cancel: Callable[[], bool] | None = None,
    on_scan_created: Callable[[Scan], None] | None = None,
) -> Scan:
    """Walk ``source_root`` and persist a ``Scan`` and its ``MediaFile`` rows.

    Read-only: no file under ``source_root`` is ever opened, modified, or
    deleted. Symlinked files/directories and entries matching the ignore
    rules (README §7.1) are skipped. Per-entry access errors are recorded
    on the ``MediaFile`` row instead of aborting the scan.
    """
    if not source_root.is_dir():
        raise InvalidSourceRootError(f"{source_root} does not exist or is not a directory")

    scan_repository = ScanRepository(session)
    media_file_repository = MediaFileRepository(session)
    excluded = {path.resolve() for path in exclude_dirs}

    scan = scan_repository.create(
        Scan(
            source_root=absolute_nfc(source_root),
            recursive=recursive,
            status="running",
            started_at=datetime.now(UTC),
        )
    )
    assert scan.id is not None
    if on_scan_created is not None:
        on_scan_created(scan)

    processed_files = 0
    total_bytes = 0
    buffer: list[MediaFile] = []

    def flush() -> None:
        media_file_repository.save_many(buffer)
        buffer.clear()
        if on_progress is not None:
            on_progress(
                ScanProgress(processed_files=processed_files, total_bytes_so_far=total_bytes)
            )

    cancelled = False
    for file_path in _iter_files(source_root, recursive=recursive, excluded=excluded):
        media_file = _build_media_file(scan.id, source_root, file_path)
        buffer.append(media_file)
        processed_files += 1
        if media_file.processing_status != "error":
            total_bytes += media_file.size_bytes
        if len(buffer) >= batch_size:
            flush()
            if should_cancel is not None and should_cancel():
                cancelled = True
                break
    if not cancelled and buffer:
        flush()

    scan.status = "cancelled" if cancelled else "completed"
    scan.finished_at = datetime.now(UTC)
    scan.total_files = processed_files
    scan.processed_files = processed_files
    scan.total_bytes = total_bytes
    return scan_repository.update(scan)


def _iter_files(root: Path, *, recursive: bool, excluded: set[Path]) -> Iterator[Path]:
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        current_dir = Path(dirpath)
        dirnames[:] = [
            name
            for name in dirnames
            if not is_ignored_dir(name)
            and not (current_dir / name).is_symlink()
            and (current_dir / name).resolve() not in excluded
        ]

        for name in filenames:
            file_path = current_dir / name
            if file_path.is_symlink() or is_ignored_file(name):
                continue
            yield file_path

        if not recursive:
            break


def _build_media_file(scan_id: int, root: Path, file_path: Path) -> MediaFile:
    absolute_path = absolute_nfc(file_path)
    relative_path = relative_nfc(file_path, root)
    file_name = to_nfc(file_path.name)
    extension = file_path.suffix

    try:
        stat_result = file_path.stat()
    except OSError as error:
        return MediaFile(
            scan_id=scan_id,
            absolute_path=absolute_path,
            relative_path=relative_path,
            file_name=file_name,
            extension=extension,
            size_bytes=0,
            processing_status="error",
            error_code="ACCESS_ERROR",
            error_message=str(error),
        )

    return MediaFile(
        scan_id=scan_id,
        absolute_path=absolute_path,
        relative_path=relative_path,
        file_name=file_name,
        extension=extension,
        size_bytes=stat_result.st_size,
        modified_at=datetime.fromtimestamp(stat_result.st_mtime, tz=UTC),
        processing_status="pending",
    )

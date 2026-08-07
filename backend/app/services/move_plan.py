"""Move-plan (dry-run) service — README §16 Etapa 5, §17.1, roadmap Phase 14.

`generate_move_plan` computes a destination path for every classified,
mapped file in a scan, runs every plan-time validation from README §16
Etapa 5, and persists the result as one `MoveOperation` row per file plus
a `MovePlan` header. It never writes, moves, renames, or deletes a
source file, never creates a destination directory, and never computes a
content hash — those are Phase 15's job, run only during real execution.
"""

from __future__ import annotations

import os
import shutil
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from sqlmodel import Session

from backend.app.core.destination_paths import (
    WINDOWS_MAX_PATH,
    exceeds_windows_path_limit,
    paths_collide,
    sanitize_path_component,
)
from backend.app.core.paths import to_nfc
from backend.app.models.classification import Classification
from backend.app.models.destination_rule import DestinationRule
from backend.app.models.media_file import MediaFile
from backend.app.models.move_plan import MoveOperation, MovePlan
from backend.app.repositories.classification_repository import ClassificationRepository
from backend.app.repositories.destination_rule_repository import DestinationRuleRepository
from backend.app.repositories.media_file_repository import MediaFileRepository
from backend.app.repositories.move_operation_repository import MoveOperationRepository
from backend.app.repositories.move_plan_repository import MovePlanRepository
from backend.app.repositories.scan_repository import ScanRepository

SUPPORTED_COLLISION_POLICY = "error"


@dataclass(frozen=True)
class MovePlanSummary:
    """Roll-up counters for a generated move plan."""

    total_planned: int = 0
    total_blocked: int = 0
    total_bytes_planned: int = 0
    unmapped: int = 0
    skipped_unclassified: int = 0
    by_group: dict[str, int] = field(default_factory=dict)
    by_error_code: dict[str, int] = field(default_factory=dict)


@dataclass
class _PendingOp:
    media_file: MediaFile
    routing_group: str
    destination_path: str
    status: str = "planned"
    error_code: str | None = None
    error_message: str | None = None


def _build_destination_path(
    media_file: MediaFile, classification: Classification, rule: DestinationRule
) -> str:
    destination = Path(rule.destination_root)
    if rule.country_subfolder_enabled:
        country_label = classification.country_name or classification.country_code or "unknown"
        destination = destination / sanitize_path_component(country_label)
    destination = destination / media_file.file_name
    return to_nfc(destination.as_posix())


def _source_changed(media_file: MediaFile, stat_result: os.stat_result) -> bool:
    if stat_result.st_size != media_file.size_bytes:
        return True
    if media_file.modified_at is None:
        return False
    # SQLite round-trips `datetime` as naive (see core/db.py); reattach UTC before
    # comparing so a freshly-`stat`-ed, timezone-aware value isn't spuriously "changed".
    stored_modified_at = media_file.modified_at
    if stored_modified_at.tzinfo is None:
        stored_modified_at = stored_modified_at.replace(tzinfo=UTC)
    current_modified_at = datetime.fromtimestamp(stat_result.st_mtime, tz=UTC)
    return current_modified_at != stored_modified_at


def _is_locked(path: Path) -> bool:
    try:
        with open(path, "r+b"):
            pass
    except (PermissionError, OSError):
        return True
    return False


def _nearest_existing_ancestor_writable(path: Path) -> bool:
    ancestor = path
    while not ancestor.exists():
        parent = ancestor.parent
        if parent == ancestor:
            return False
        ancestor = parent
    return os.access(ancestor, os.W_OK)


def _volume_root(path_str: str) -> str:
    drive, _tail = os.path.splitdrive(path_str)
    if drive:
        return drive + os.sep
    return Path(path_str).anchor or "/"


def _check_disk_space(pending_ops: list[_PendingOp]) -> dict[str, int]:
    """Return `{volume_root: shortfall_bytes}` for every volume short on space."""
    needed_by_volume: dict[str, int] = {}
    for op in pending_ops:
        volume_root = _volume_root(op.destination_path)
        needed_by_volume[volume_root] = (
            needed_by_volume.get(volume_root, 0) + op.media_file.size_bytes
        )

    shortfalls: dict[str, int] = {}
    for volume_root, needed_bytes in needed_by_volume.items():
        free_bytes = shutil.disk_usage(volume_root).free
        if needed_bytes > free_bytes:
            shortfalls[volume_root] = needed_bytes - free_bytes
    return shortfalls


def _block(op: _PendingOp, error_code: str, error_message: str) -> None:
    op.status = "blocked"
    op.error_code = error_code
    op.error_message = error_message


def generate_move_plan(
    session: Session,
    scan_id: int,
    *,
    collision_policy: str = "error",
    validation_mode: str = "standard",
    on_progress: Callable[[MediaFile, MoveOperation], None] | None = None,
) -> MovePlanSummary:
    """Generate and persist a dry-run move plan for `scan_id`. Never touches a file."""
    if collision_policy != SUPPORTED_COLLISION_POLICY:
        raise ValueError(
            f"Unsupported collision_policy {collision_policy!r}. "
            f"Only {SUPPORTED_COLLISION_POLICY!r} is implemented."
        )

    scan_repository = ScanRepository(session)
    scan = scan_repository.get(scan_id)
    if scan is None:
        raise ValueError(f"No scan found for scan_id={scan_id}")

    rules_by_group = {
        rule.routing_group: rule
        for rule in DestinationRuleRepository(session).list_by_scan(scan_id)
        if rule.enabled
    }

    media_file_repository = MediaFileRepository(session)
    classification_repository = ClassificationRepository(session)

    pending_ops: list[_PendingOp] = []
    unmapped = 0
    skipped_unclassified = 0

    for media_file in media_file_repository.list_by_scan(scan_id):
        assert media_file.id is not None
        classification = classification_repository.get_by_media_file_id(media_file.id)
        if classification is None:
            skipped_unclassified += 1
            continue

        rule = rules_by_group.get(classification.effective_routing_group)
        if rule is None:
            unmapped += 1
            continue

        destination_path = _build_destination_path(media_file, classification, rule)
        pending_ops.append(
            _PendingOp(
                media_file=media_file,
                routing_group=classification.effective_routing_group,
                destination_path=destination_path,
            )
        )

    claimed_destinations: dict[str, _PendingOp] = {}
    for op in pending_ops:
        source_path = Path(op.media_file.absolute_path)

        if not source_path.exists():
            _block(op, "SOURCE_MISSING", f"Source file no longer exists: {source_path}")
            continue

        stat_result = source_path.stat()
        if _source_changed(op.media_file, stat_result):
            _block(
                op,
                "SOURCE_CHANGED",
                f"Source file changed since scan: {source_path}",
            )
            continue

        if _is_locked(source_path):
            _block(op, "SOURCE_LOCKED", f"Source file is locked by another process: {source_path}")
            continue

        if paths_collide(to_nfc(source_path.as_posix()), op.destination_path):
            _block(op, "SOURCE_EQUALS_DESTINATION", "Source and destination paths are the same.")
            continue

        if exceeds_windows_path_limit(op.destination_path):
            _block(
                op,
                "PATH_TOO_LONG",
                f"Destination path exceeds the {WINDOWS_MAX_PATH}-character Windows limit: "
                f"{op.destination_path}",
            )
            continue

        collision_key = to_nfc(op.destination_path).casefold()
        duplicate = claimed_destinations.get(collision_key)
        if duplicate is not None:
            _block(
                op,
                "DUPLICATE_IN_PLAN",
                f"Destination path already claimed by media_file_id={duplicate.media_file.id} "
                f"in this plan: {op.destination_path}",
            )
            continue

        if Path(op.destination_path).exists():
            _block(
                op,
                "NAME_COLLISION",
                f"A file already exists at the destination: {op.destination_path}",
            )
            continue

        if not _nearest_existing_ancestor_writable(Path(op.destination_path).parent):
            _block(
                op,
                "DESTINATION_NOT_WRITABLE",
                f"Destination is not writable: {op.destination_path}",
            )
            continue

        claimed_destinations[collision_key] = op

    still_planned = [op for op in pending_ops if op.status == "planned"]
    shortfalls = _check_disk_space(still_planned)
    for op in still_planned:
        volume_root = _volume_root(op.destination_path)
        if volume_root in shortfalls:
            _block(
                op,
                "INSUFFICIENT_DISK_SPACE",
                f"Destination volume {volume_root} is short "
                f"{shortfalls[volume_root]} bytes for this plan.",
            )

    move_plan = MovePlanRepository(session).create(
        MovePlan(
            scan_id=scan_id,
            status="generated",
            collision_policy=collision_policy,
            validation_mode=validation_mode,
        )
    )
    assert move_plan.id is not None

    operations: list[MoveOperation] = []
    by_group: dict[str, int] = {}
    by_error_code: dict[str, int] = {}
    total_planned = 0
    total_blocked = 0
    total_bytes_planned = 0

    for op in pending_ops:
        operation = MoveOperation(
            move_plan_id=move_plan.id,
            scan_id=scan_id,
            media_file_id=op.media_file.id,
            source_path=op.media_file.absolute_path,
            planned_destination_path=op.destination_path,
            source_size=op.media_file.size_bytes,
            status=op.status,
            error_code=op.error_code,
            error_message=op.error_message,
        )
        operations.append(operation)

        by_group[op.routing_group] = by_group.get(op.routing_group, 0) + 1
        if op.status == "planned":
            total_planned += 1
            total_bytes_planned += op.media_file.size_bytes
        else:
            total_blocked += 1
            assert op.error_code is not None
            by_error_code[op.error_code] = by_error_code.get(op.error_code, 0) + 1

    MoveOperationRepository(session).bulk_create(operations)

    if on_progress is not None:
        for op, operation in zip(pending_ops, operations, strict=True):
            on_progress(op.media_file, operation)

    return MovePlanSummary(
        total_planned=total_planned,
        total_blocked=total_blocked,
        total_bytes_planned=total_bytes_planned,
        unmapped=unmapped,
        skipped_unclassified=skipped_unclassified,
        by_group=by_group,
        by_error_code=by_error_code,
    )

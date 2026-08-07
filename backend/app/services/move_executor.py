"""Transactional move executor — README §17/§18, roadmap Phase 15.

Drives every `MoveOperation` still `status="planned"` on a `MovePlan`
(Phase 14) through to a terminal state (`completed`/`failed`), using an
atomic rename on the same volume or the hash -> copy-temp -> verify ->
rename -> delete-source sequence across volumes (README §17.2/§17.3). The
journal row's own `status` is consulted before every operation, so
re-running this function on the same plan is idempotent and resumable —
a crashed run is picked back up rather than repeated. Confirmation,
live progress display, cancellation-between-files, and the move report
are Phase 16's job; this module only exposes `on_progress` and
`should_cancel` hooks for that CLI to use.
"""

from __future__ import annotations

import contextlib
import os
import shutil
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from sqlmodel import Session

from backend.app.core.hashing import sha256_file
from backend.app.core.volume import is_same_volume
from backend.app.models.move_plan import MoveOperation
from backend.app.repositories.move_operation_repository import MoveOperationRepository
from backend.app.repositories.move_plan_repository import MovePlanRepository

TERMINAL_STATUSES = ("completed", "failed", "skipped", "cancelled")
IN_FLIGHT_STATUSES = ("validating", "copying", "verifying", "renaming", "deleting_source")


class _ExecutionError(Exception):
    def __init__(self, error_code: str, message: str) -> None:
        super().__init__(message)
        self.error_code = error_code


@dataclass(frozen=True)
class MoveExecutionSummary:
    """Roll-up counters for one `execute_move_plan` call."""

    total_completed: int = 0
    total_failed: int = 0
    total_skipped: int = 0
    total_bytes_moved: int = 0
    by_error_code: dict[str, int] = field(default_factory=dict)


def _now() -> datetime:
    return datetime.now(UTC)


def _partial_path(destination: Path, operation_id: int) -> Path:
    return destination.with_name(f"{destination.name}.partial-{operation_id}")


def _cleanup_partial(partial: Path) -> None:
    if partial.exists():
        with contextlib.suppress(OSError):
            partial.unlink()


def _validate_source(operation: MoveOperation, source: Path) -> str | None:
    if not source.exists():
        return "SOURCE_MISSING"
    if source.stat().st_size != operation.source_size:
        return "SOURCE_CHANGED"
    return None


def _execute_same_volume(
    operation: MoveOperation, source: Path, destination: Path, validation_mode: str
) -> None:
    if destination.exists():
        raise _ExecutionError("DESTINATION_EXISTS", f"Destination already exists: {destination}")

    destination.parent.mkdir(parents=True, exist_ok=True)
    operation.status = "renaming"
    os.rename(source, destination)

    if not destination.exists():
        raise _ExecutionError("RENAME_FAILED", f"Rename did not produce {destination}")

    destination_stat = destination.stat()
    if destination_stat.st_size != operation.source_size:
        raise _ExecutionError(
            "SIZE_MISMATCH",
            f"Destination size {destination_stat.st_size} != source size {operation.source_size}",
        )

    if validation_mode == "strict":
        digest = sha256_file(destination)
        operation.source_hash = digest
        operation.destination_hash = digest

    operation.actual_destination_path = str(destination)
    operation.destination_size = destination_stat.st_size


def _execute_cross_volume(
    operation: MoveOperation, source: Path, destination: Path, validation_mode: str
) -> None:
    assert operation.id is not None
    operation.status = "validating"
    source_hash = sha256_file(source)
    operation.source_hash = source_hash

    destination.parent.mkdir(parents=True, exist_ok=True)
    partial = _partial_path(destination, operation.id)
    _cleanup_partial(partial)

    operation.status = "copying"
    try:
        with open(source, "rb") as src, open(partial, "wb") as dst:
            shutil.copyfileobj(src, dst)
            dst.flush()
            os.fsync(dst.fileno())
    except OSError as exc:
        _cleanup_partial(partial)
        raise _ExecutionError("COPY_FAILED", str(exc)) from exc

    operation.status = "verifying"
    if partial.stat().st_size != operation.source_size:
        _cleanup_partial(partial)
        raise _ExecutionError(
            "SIZE_MISMATCH",
            f"Copied size {partial.stat().st_size} != source size {operation.source_size}",
        )

    partial_hash = sha256_file(partial)
    if partial_hash != source_hash:
        _cleanup_partial(partial)
        raise _ExecutionError("HASH_MISMATCH", "Copied file hash does not match source hash")

    if destination.exists():
        _cleanup_partial(partial)
        raise _ExecutionError("DESTINATION_EXISTS", f"Destination already exists: {destination}")

    operation.status = "renaming"
    os.rename(partial, destination)

    operation.status = "deleting_source"
    os.remove(source)
    if source.exists():
        raise _ExecutionError("SOURCE_NOT_DELETED", f"Source still exists after delete: {source}")

    operation.actual_destination_path = str(destination)
    operation.destination_size = destination.stat().st_size
    operation.destination_hash = partial_hash
    if validation_mode == "strict":
        operation.source_hash = source_hash


def _resume_or_reset(operation: MoveOperation) -> bool:
    """Reconcile a row left mid-flight by a crashed run. Returns True if touched."""
    if operation.status not in IN_FLIGHT_STATUSES:
        return False

    if operation.actual_destination_path is not None:
        destination = Path(operation.actual_destination_path)
        if destination.exists() and destination.stat().st_size == operation.source_size:
            operation.status = "completed"
            operation.finished_at = _now()
            return True

    if operation.id is not None:
        _cleanup_partial(_partial_path(Path(operation.planned_destination_path), operation.id))
    operation.status = "planned"
    operation.actual_destination_path = None
    operation.error_code = None
    operation.error_message = None
    return True


def execute_move_plan(
    session: Session,
    move_plan_id: int,
    *,
    validation_mode: str | None = None,
    on_progress: Callable[[MoveOperation], None] | None = None,
    should_cancel: Callable[[], bool] | None = None,
) -> MoveExecutionSummary:
    """Execute every `planned` operation on `move_plan_id`. Idempotent, resumable."""
    move_plan = MovePlanRepository(session).get(move_plan_id)
    if move_plan is None:
        raise ValueError(f"No move plan found for move_plan_id={move_plan_id}")
    effective_validation_mode = validation_mode or move_plan.validation_mode

    operation_repository = MoveOperationRepository(session)
    operations = operation_repository.list_by_plan(move_plan_id)

    total_completed = 0
    total_failed = 0
    total_skipped = 0
    total_bytes_moved = 0
    by_error_code: dict[str, int] = {}

    def _tally(operation: MoveOperation) -> None:
        nonlocal total_completed, total_failed, total_skipped, total_bytes_moved
        if operation.status == "completed":
            total_completed += 1
            total_bytes_moved += operation.destination_size or 0
        elif operation.status == "failed":
            total_failed += 1
            if operation.error_code is not None:
                by_error_code[operation.error_code] = by_error_code.get(operation.error_code, 0) + 1
        elif operation.status == "skipped":
            total_skipped += 1

    for operation in operations:
        touched = _resume_or_reset(operation)
        if touched:
            operation_repository.update(operation)

        if operation.status in TERMINAL_STATUSES:
            _tally(operation)
            continue

        if operation.status != "planned":
            # "blocked" rows come from plan generation and are never executed.
            continue

        if should_cancel is not None and should_cancel():
            break

        operation.started_at = _now()
        source = Path(operation.source_path)
        destination = Path(operation.planned_destination_path)

        try:
            source_error = _validate_source(operation, source)
            if source_error is not None:
                raise _ExecutionError(source_error, f"{source_error}: {source}")

            operation.status = "validating"
            if is_same_volume(source, destination):
                _execute_same_volume(operation, source, destination, effective_validation_mode)
            else:
                _execute_cross_volume(operation, source, destination, effective_validation_mode)

            operation.status = "completed"
            operation.finished_at = _now()
        except _ExecutionError as exc:
            operation.status = "failed"
            operation.error_code = exc.error_code
            operation.error_message = str(exc)
            operation.finished_at = _now()
        except OSError as exc:
            operation.status = "failed"
            operation.error_code = "UNEXPECTED_ERROR"
            operation.error_message = str(exc)
            operation.finished_at = _now()

        operation_repository.update(operation)
        _tally(operation)
        if on_progress is not None:
            on_progress(operation)

    return MoveExecutionSummary(
        total_completed=total_completed,
        total_failed=total_failed,
        total_skipped=total_skipped,
        total_bytes_moved=total_bytes_moved,
        by_error_code=by_error_code,
    )

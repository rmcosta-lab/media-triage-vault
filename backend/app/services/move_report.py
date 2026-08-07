"""Move report — README §19.3, roadmap Phase 16.

After `execute_move_plan` (Phase 15) runs, `generate_move_report` writes
the final account of what happened: the originating plan, per-status
counts, total bytes moved, execution time, and one row per file with its
source, destination, validation result, and any error.
"""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path

from sqlmodel import Session

from backend.app.models.move_plan import MoveOperation
from backend.app.repositories.move_operation_repository import MoveOperationRepository
from backend.app.repositories.move_plan_repository import MovePlanRepository
from backend.app.services.move_executor import MoveExecutionSummary

_CSV_FIELDNAMES = (
    "media_file_id",
    "source_path",
    "planned_destination_path",
    "actual_destination_path",
    "status",
    "source_size",
    "destination_size",
    "source_hash",
    "destination_hash",
    "started_at",
    "finished_at",
    "error_code",
    "error_message",
)


@dataclass(frozen=True)
class MoveReportSummary:
    """Roll-up counters written into `move_report.json`'s `totals` block."""

    total_operations: int
    total_planned: int
    total_completed: int
    total_failed: int
    total_skipped: int
    total_blocked: int
    total_bytes_moved: int
    elapsed_seconds: float


def _operation_row(operation: MoveOperation) -> dict[str, object]:
    return {
        "media_file_id": operation.media_file_id,
        "source_path": operation.source_path,
        "planned_destination_path": operation.planned_destination_path,
        "actual_destination_path": operation.actual_destination_path,
        "status": operation.status,
        "source_size": operation.source_size,
        "destination_size": operation.destination_size,
        "source_hash": operation.source_hash,
        "destination_hash": operation.destination_hash,
        "started_at": operation.started_at.isoformat() if operation.started_at else None,
        "finished_at": operation.finished_at.isoformat() if operation.finished_at else None,
        "error_code": operation.error_code,
        "error_message": operation.error_message,
    }


def generate_move_report(
    session: Session,
    move_plan_id: int,
    output_dir: Path,
    execution_summary: MoveExecutionSummary,
    elapsed_seconds: float,
) -> MoveReportSummary:
    """Write `move_report.json`/`.csv` to `output_dir` and return the totals."""
    move_plan = MovePlanRepository(session).get(move_plan_id)
    if move_plan is None:
        raise ValueError(f"No move plan found for move_plan_id={move_plan_id}")

    operations = list(MoveOperationRepository(session).list_by_plan(move_plan_id))
    rows = [_operation_row(operation) for operation in operations]

    total_blocked = sum(1 for operation in operations if operation.status == "blocked")
    total_still_planned = sum(1 for operation in operations if operation.status == "planned")

    report = {
        "move_plan_id": move_plan.id,
        "scan_id": move_plan.scan_id,
        "collision_policy": move_plan.collision_policy,
        "validation_mode": move_plan.validation_mode,
        "elapsed_seconds": elapsed_seconds,
        "totals": {
            "operations": len(operations),
            "completed": execution_summary.total_completed,
            "failed": execution_summary.total_failed,
            "skipped": execution_summary.total_skipped,
            "blocked": total_blocked,
            "still_planned": total_still_planned,
            "bytes_moved": execution_summary.total_bytes_moved,
        },
        "by_error_code": execution_summary.by_error_code,
        "operations": rows,
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "move_report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    with open(output_dir / "move_report.csv", "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=_CSV_FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)

    return MoveReportSummary(
        total_operations=len(operations),
        total_planned=total_still_planned,
        total_completed=execution_summary.total_completed,
        total_failed=execution_summary.total_failed,
        total_skipped=execution_summary.total_skipped,
        total_blocked=total_blocked,
        total_bytes_moved=execution_summary.total_bytes_moved,
        elapsed_seconds=elapsed_seconds,
    )

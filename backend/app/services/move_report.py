"""Move report — README §19.3, roadmap Phases 16 and 19.

`build_move_report_payload` derives the full report purely from the
persisted `MoveOperation` rows — no live execution-run object needed —
so it works equally well right after a CLI `execute` run and later, on
demand, through the API (`GET /api/move-runs/{run_id}/report`, Phase 19).
`generate_move_report` (Phase 16's CLI path) is a thin wrapper that also
writes `move_report.json`/`.csv` to disk.
"""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlmodel import Session

from backend.app.models.move_plan import MoveOperation
from backend.app.repositories.move_operation_repository import MoveOperationRepository
from backend.app.repositories.move_plan_repository import MovePlanRepository

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
    """Roll-up counters mirroring `build_move_report_payload`'s `totals` block."""

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


def build_move_report_payload(
    session: Session, move_plan_id: int, elapsed_seconds: float
) -> dict[str, Any]:
    """Build the report dict purely from persisted `MoveOperation` rows."""
    move_plan = MovePlanRepository(session).get(move_plan_id)
    if move_plan is None:
        raise ValueError(f"No move plan found for move_plan_id={move_plan_id}")

    operations = list(MoveOperationRepository(session).list_by_plan(move_plan_id))
    rows = [_operation_row(operation) for operation in operations]

    total_completed = sum(1 for operation in operations if operation.status == "completed")
    total_failed = sum(1 for operation in operations if operation.status == "failed")
    total_skipped = sum(1 for operation in operations if operation.status == "skipped")
    total_blocked = sum(1 for operation in operations if operation.status == "blocked")
    total_still_planned = sum(1 for operation in operations if operation.status == "planned")
    total_bytes_moved = sum(
        operation.destination_size or 0
        for operation in operations
        if operation.status == "completed"
    )

    by_error_code: dict[str, int] = {}
    for operation in operations:
        if operation.status == "failed" and operation.error_code is not None:
            by_error_code[operation.error_code] = by_error_code.get(operation.error_code, 0) + 1

    return {
        "move_plan_id": move_plan.id,
        "scan_id": move_plan.scan_id,
        "collision_policy": move_plan.collision_policy,
        "validation_mode": move_plan.validation_mode,
        "elapsed_seconds": elapsed_seconds,
        "totals": {
            "operations": len(operations),
            "completed": total_completed,
            "failed": total_failed,
            "skipped": total_skipped,
            "blocked": total_blocked,
            "still_planned": total_still_planned,
            "bytes_moved": total_bytes_moved,
        },
        "by_error_code": by_error_code,
        "operations": rows,
    }


def generate_move_report(
    session: Session, move_plan_id: int, output_dir: Path, elapsed_seconds: float
) -> MoveReportSummary:
    """Write `move_report.json`/`.csv` to `output_dir` and return the totals."""
    payload = build_move_report_payload(session, move_plan_id, elapsed_seconds)
    rows = payload["operations"]
    totals = payload["totals"]

    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "move_report.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    with open(output_dir / "move_report.csv", "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=_CSV_FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)

    return MoveReportSummary(
        total_operations=totals["operations"],
        total_planned=totals["still_planned"],
        total_completed=totals["completed"],
        total_failed=totals["failed"],
        total_skipped=totals["skipped"],
        total_blocked=totals["blocked"],
        total_bytes_moved=totals["bytes_moved"],
        elapsed_seconds=elapsed_seconds,
    )

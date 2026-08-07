"""Integration test: `execute` CLI, US-004 (README §16 Etapa 6-8, §40) — see
specs/2026-08-07-phase-16-execute-resume-cli-move-report/plan.md and validation.md.
"""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

from typer.testing import CliRunner

from backend.app.cli.main import app
from backend.app.core.db import get_engine, get_session
from backend.app.repositories.move_operation_repository import MoveOperationRepository
from backend.app.repositories.move_plan_repository import MovePlanRepository
from backend.app.rules.engine import ROUTING_GROUPS
from backend.app.services.move_executor import execute_move_plan

FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures"

ALL_FIXTURES = (
    "iphone_jpeg_gps.jpg",
    "iphone_heic.heic",
    "jpeg_no_exif.jpg",
    "Screenshot_20260730-152000.png",
    "IMG-20260730-WA0001.jpg",
    "sample_video.mp4",
    "misnamed_video_as_jpg.jpg",
    "corrupt_video.mp4",
)

runner = CliRunner()


def _copy_fixtures(root: Path) -> None:
    for name in ALL_FIXTURES:
        shutil.copy(FIXTURES_DIR / name, root / name)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _run_full_pipeline(source: Path, output: Path, database: Path, dest_root: Path) -> None:
    scan_result = runner.invoke(
        app, ["scan", str(source), "--output", str(output), "--database", str(database)]
    )
    assert scan_result.exit_code == 0, scan_result.output

    classify_result = runner.invoke(
        app, ["classify", "--scan-id", "1", "--database", str(database)]
    )
    assert classify_result.exit_code == 0, classify_result.output

    config_path = output / "destinations.json"
    config_path.write_text(
        json.dumps(
            {group: {"destination_root": str(dest_root / group)} for group in ROUTING_GROUPS}
        ),
        encoding="utf-8",
    )
    destinations_result = runner.invoke(
        app,
        [
            "destinations",
            "--scan-id",
            "1",
            "--config",
            str(config_path),
            "--database",
            str(database),
        ],
    )
    assert destinations_result.exit_code == 0, destinations_result.output

    plan_result = runner.invoke(app, ["plan", "--scan-id", "1", "--database", str(database)])
    assert plan_result.exit_code == 0, plan_result.output


def test_execute_cli_end_to_end(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    _copy_fixtures(source)
    source_hashes_before = {name: _sha256(source / name) for name in ALL_FIXTURES}

    output = tmp_path / "report"
    database = tmp_path / "test.db"
    dest_root = tmp_path / "dest"

    _run_full_pipeline(source, output, database, dest_root)

    with get_session(get_engine(database)) as session:
        move_plan = MovePlanRepository(session).get_latest_for_scan(1)
        assert move_plan is not None
        assert move_plan.id is not None
        operations_before = MoveOperationRepository(session).list_by_plan(move_plan.id)
        planned_before = [op for op in operations_before if op.status == "planned"]
        blocked_before = [op for op in operations_before if op.status == "blocked"]
        assert planned_before, "expected at least one planned operation for this fixture set"

    execute_output = tmp_path / "move_report"
    execute_result = runner.invoke(
        app,
        [
            "execute",
            "--scan-id",
            "1",
            "--output",
            str(execute_output),
            "--confirm",
            "--database",
            str(database),
        ],
    )
    assert execute_result.exit_code == 0, execute_result.output
    assert f"completed={len(planned_before)}" in execute_result.output

    with get_session(get_engine(database)) as session:
        move_plan = MovePlanRepository(session).get_latest_for_scan(1)
        assert move_plan is not None
        assert move_plan.id is not None
        operations_after = MoveOperationRepository(session).list_by_plan(move_plan.id)

    planned_ids = {op.id for op in planned_before}
    for operation in operations_after:
        if operation.id in planned_ids:
            assert operation.status == "completed"
            assert operation.actual_destination_path is not None
            destination = Path(operation.actual_destination_path)
            assert destination.exists()
            file_name = Path(operation.source_path).name
            assert _sha256(destination) == source_hashes_before[file_name]
            assert not Path(operation.source_path).exists()
        else:
            assert operation.status == "blocked"
            assert Path(operation.source_path).exists()

    assert len(blocked_before) == sum(1 for op in operations_after if op.status == "blocked")

    report_json_path = execute_output / "move_report.json"
    report_csv_path = execute_output / "move_report.csv"
    assert report_json_path.exists()
    assert report_csv_path.exists()
    report = json.loads(report_json_path.read_text(encoding="utf-8"))
    assert report["totals"]["completed"] == len(planned_before)


def test_execute_cli_without_confirm_does_nothing(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    _copy_fixtures(source)

    output = tmp_path / "report"
    database = tmp_path / "test.db"
    dest_root = tmp_path / "dest"

    _run_full_pipeline(source, output, database, dest_root)

    execute_result = runner.invoke(
        app,
        [
            "execute",
            "--scan-id",
            "1",
            "--output",
            str(tmp_path / "move_report"),
            "--database",
            str(database),
        ],
    )
    assert execute_result.exit_code == 0, execute_result.output
    assert "Nothing executed" in execute_result.output
    assert not dest_root.exists()

    with get_session(get_engine(database)) as session:
        move_plan = MovePlanRepository(session).get_latest_for_scan(1)
        assert move_plan is not None
        assert move_plan.id is not None
        operations = MoveOperationRepository(session).list_by_plan(move_plan.id)
        assert all(op.status in ("planned", "blocked") for op in operations)


def test_execute_cli_without_plan_exits_nonzero(tmp_path: Path) -> None:
    database = tmp_path / "test.db"
    result = runner.invoke(
        app,
        [
            "execute",
            "--scan-id",
            "1",
            "--output",
            str(tmp_path / "move_report"),
            "--confirm",
            "--database",
            str(database),
        ],
    )
    assert result.exit_code != 0


def test_kill_and_resume(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    _copy_fixtures(source)

    output = tmp_path / "report"
    database = tmp_path / "test.db"
    dest_root = tmp_path / "dest"

    _run_full_pipeline(source, output, database, dest_root)

    with get_session(get_engine(database)) as session:
        move_plan = MovePlanRepository(session).get_latest_for_scan(1)
        assert move_plan is not None
        assert move_plan.id is not None
        move_plan_id = move_plan.id
        planned_before = [
            op
            for op in MoveOperationRepository(session).list_by_plan(move_plan_id)
            if op.status == "planned"
        ]
        assert len(planned_before) >= 2, "need at least two planned files to simulate a kill"

        # Simulate the process being killed after the first file: cancel before the second.
        calls = 0

        def _should_cancel() -> bool:
            nonlocal calls
            calls += 1
            return calls > 1

        interrupted_summary = execute_move_plan(session, move_plan_id, should_cancel=_should_cancel)
        assert interrupted_summary.total_completed == 1

        operations_mid_run = MoveOperationRepository(session).list_by_plan(move_plan_id)
        still_planned = [op for op in operations_mid_run if op.status == "planned"]
        assert len(still_planned) == len(planned_before) - 1

    resume_result = runner.invoke(
        app,
        [
            "execute",
            "--scan-id",
            "1",
            "--output",
            str(tmp_path / "move_report"),
            "--confirm",
            "--database",
            str(database),
        ],
    )
    assert resume_result.exit_code == 0, resume_result.output
    assert f"completed={len(planned_before)}" in resume_result.output

    with get_session(get_engine(database)) as session:
        operations_final = MoveOperationRepository(session).list_by_plan(move_plan_id)
        planned_ids = {op.id for op in planned_before}
        for operation in operations_final:
            if operation.id in planned_ids:
                assert operation.status == "completed"

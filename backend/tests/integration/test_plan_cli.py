"""Integration test: full scan -> classify -> destinations -> plan pipeline and the
`destinations`/`plan` CLI commands, US-003 (README §39) — see
specs/2026-08-07-phase-14-destinations-move-plan/plan.md and validation.md.
"""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

from typer.testing import CliRunner

from backend.app.cli.main import app
from backend.app.core.db import get_engine, get_session
from backend.app.models.move_plan import MOVE_OPERATION_STATUSES
from backend.app.repositories.move_operation_repository import MoveOperationRepository
from backend.app.repositories.move_plan_repository import MovePlanRepository
from backend.app.rules.engine import ROUTING_GROUPS

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


def _hashes(root: Path) -> dict[str, str]:
    return {name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in ALL_FIXTURES}


def test_destinations_and_plan_cli_end_to_end(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    _copy_fixtures(source)
    before = _hashes(source)

    output = tmp_path / "report"
    database = tmp_path / "test.db"
    dest_root = tmp_path / "dest"

    scan_result = runner.invoke(
        app, ["scan", str(source), "--output", str(output), "--database", str(database)]
    )
    assert scan_result.exit_code == 0, scan_result.output

    classify_result = runner.invoke(
        app, ["classify", "--scan-id", "1", "--database", str(database)]
    )
    assert classify_result.exit_code == 0, classify_result.output

    config_path = tmp_path / "destinations.json"
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
    assert f"{len(ROUTING_GROUPS)} routing group(s) mapped" in destinations_result.output

    plan_result = runner.invoke(app, ["plan", "--scan-id", "1", "--database", str(database)])
    assert plan_result.exit_code == 0, plan_result.output
    assert "DRY RUN" in plan_result.output

    with get_session(get_engine(database)) as session:
        move_plan = MovePlanRepository(session).get_latest_for_scan(1)
        assert move_plan is not None
        assert move_plan.status == "generated"
        assert move_plan.id is not None

        operations = MoveOperationRepository(session).list_by_plan(move_plan.id)
        assert len(operations) == len(ALL_FIXTURES)
        assert all(op.status in MOVE_OPERATION_STATUSES for op in operations)
        assert all(op.source_path and op.planned_destination_path for op in operations)

    # Dry run: no destination directory or file was ever created.
    assert not dest_root.exists()

    assert _hashes(source) == before


def test_destinations_cli_rejects_unknown_routing_group(tmp_path: Path) -> None:
    database = tmp_path / "test.db"
    config_path = tmp_path / "destinations.json"
    config_path.write_text(
        json.dumps({"not_a_group": {"destination_root": str(tmp_path / "dest")}}),
        encoding="utf-8",
    )

    result = runner.invoke(
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
    assert result.exit_code != 0


def test_plan_cli_rejects_unsupported_collision_policy(tmp_path: Path) -> None:
    database = tmp_path / "test.db"
    result = runner.invoke(
        app,
        [
            "plan",
            "--scan-id",
            "1",
            "--collision-policy",
            "rename_with_suffix",
            "--database",
            str(database),
        ],
    )
    assert result.exit_code != 0

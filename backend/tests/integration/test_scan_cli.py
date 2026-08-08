"""Integration tests: `media-organizer scan` end to end, US-001 (README §37) — see
specs/2026-08-07-phase-7-scan-cli/plan.md and validation.md.
"""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

import pytest
from typer.testing import CliRunner

from backend.app.cli import main as cli_main
from backend.app.cli.main import app
from backend.app.core.tools import ToolNotAvailableError

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


def test_scan_command_end_to_end(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    _copy_fixtures(source)
    before = _hashes(source)

    output = tmp_path / "report"
    database = tmp_path / "test.db"

    result = runner.invoke(
        app,
        [
            "scan",
            str(source),
            "--output",
            str(output),
            "--database",
            str(database),
        ],
    )

    assert result.exit_code == 0, result.output
    assert (output / "inventory.json").exists()
    assert (output / "errors.log").exists()

    inventory = json.loads((output / "inventory.json").read_text(encoding="utf-8"))
    assert len(inventory) == len(ALL_FIXTURES)
    by_name = {entry["file_name"]: entry for entry in inventory}
    assert by_name["iphone_jpeg_gps.jpg"]["media_kind"] == "image"
    assert by_name["misnamed_video_as_jpg.jpg"]["extension_mismatch"] is True
    assert by_name["iphone_jpeg_gps.jpg"]["metadata"]["make"] == "Apple"

    errors_log = (output / "errors.log").read_text(encoding="utf-8")
    assert "corrupt_video.mp4" in errors_log
    assert "VIDEO_UNREADABLE" in errors_log

    assert _hashes(source) == before


def test_scan_command_nonexistent_path_exits_nonzero(tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        [
            "scan",
            str(tmp_path / "does-not-exist"),
            "--output",
            str(tmp_path / "out"),
            "--database",
            str(tmp_path / "test.db"),
        ],
    )
    assert result.exit_code != 0
    assert result.exception is None or isinstance(result.exception, SystemExit)


def test_scan_command_missing_tool_fails_before_creating_artifacts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "source"
    source.mkdir()
    output = tmp_path / "out"
    database = tmp_path / "test.db"

    def _missing_tool(*_names: str) -> None:
        raise ToolNotAvailableError("ffprobe", "ffprobe is unavailable")

    monkeypatch.setattr(cli_main, "require_tools", _missing_tool)

    result = runner.invoke(
        app,
        ["scan", str(source), "--output", str(output), "--database", str(database)],
    )

    assert result.exit_code == 1
    assert "Required local tool unavailable: ffprobe is unavailable" in result.output
    assert not output.exists()
    assert not database.exists()

"""Integration tests: full scan -> detect -> extract -> classify -> report pipeline
and the `report` CLI command, README §43 first-delivery checklist — see
specs/2026-08-07-phase-13-thumbnails-static-reports/plan.md and validation.md.
"""

from __future__ import annotations

import csv
import hashlib
import json
import shutil
from pathlib import Path

import pytest
from sqlalchemy import Engine
from typer.testing import CliRunner

from backend.app.cli.main import app
from backend.app.core.db import create_db_and_tables, get_engine, get_session
from backend.app.services.classification import classify_scan
from backend.app.services.media_type import detect_media_types_for_scan
from backend.app.services.metadata import extract_metadata_for_scan
from backend.app.services.reports import generate_report
from backend.app.services.scanner import scan_folder

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


@pytest.fixture
def engine(tmp_path: Path) -> Engine:
    engine = get_engine(tmp_path / "test.db")
    create_db_and_tables(engine)
    return engine


def test_generate_report_produces_full_bundle(engine: Engine, tmp_path: Path) -> None:
    root = tmp_path / "source"
    root.mkdir()
    _copy_fixtures(root)
    before = _hashes(root)

    output = tmp_path / "report"

    with get_session(engine) as session:
        scan = scan_folder(session, root, recursive=True)
        assert scan.id is not None
        detect_media_types_for_scan(session, scan.id)
        extract_metadata_for_scan(session, scan.id)
        classify_scan(session, scan.id)

        summary = generate_report(session, scan.id, output)

    assert summary.total_files == len(ALL_FIXTURES)

    assert (output / "report.json").is_file()
    assert (output / "report.csv").is_file()
    assert (output / "report.html").is_file()
    assert (output / "errors.log").is_file()

    thumbnails_dir = output / "thumbnails"
    thumbnail_files = {p.name for p in thumbnails_dir.glob("*.jpg")}
    # corrupt_video.mp4 gets no thumbnail; every other fixture does.
    assert len(thumbnail_files) == len(ALL_FIXTURES) - 1

    report_json = json.loads((output / "report.json").read_text(encoding="utf-8"))
    assert report_json["total_files"] == len(ALL_FIXTURES)
    raw_json_text = (output / "report.json").read_text(encoding="utf-8")
    assert "gps_latitude" not in raw_json_text
    assert "gps_longitude" not in raw_json_text

    with (output / "report.csv").open(newline="", encoding="utf-8") as handle:
        csv_rows = list(csv.reader(handle))
    assert len(csv_rows) == len(ALL_FIXTURES) + 1  # header + one row per file

    html_text = (output / "report.html").read_text(encoding="utf-8")
    for name in ALL_FIXTURES:
        assert name in html_text
    assert "confidence=" in html_text
    assert '<select id="filter-group">' in html_text
    assert '<select id="filter-country">' in html_text
    assert "no preview available" in html_text  # corrupt_video.mp4's card

    errors_log = (output / "errors.log").read_text(encoding="utf-8")
    assert "corrupt_video.mp4" in errors_log

    assert _hashes(root) == before


def test_report_cli_end_to_end(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    _copy_fixtures(source)
    before = _hashes(source)

    scan_output = tmp_path / "scan_output"
    report_output = tmp_path / "report_output"
    database = tmp_path / "test.db"

    scan_result = runner.invoke(
        app, ["scan", str(source), "--output", str(scan_output), "--database", str(database)]
    )
    assert scan_result.exit_code == 0, scan_result.output

    classify_result = runner.invoke(
        app, ["classify", "--scan-id", "1", "--database", str(database)]
    )
    assert classify_result.exit_code == 0, classify_result.output

    report_result = runner.invoke(
        app,
        ["report", "--scan-id", "1", "--output", str(report_output), "--database", str(database)],
    )
    assert report_result.exit_code == 0, report_result.output
    assert "report.html" in report_result.output
    assert "report.json" in report_result.output
    assert "report.csv" in report_result.output
    assert "errors.log" in report_result.output

    assert (report_output / "report.html").is_file()
    assert (report_output / "report.json").is_file()
    assert (report_output / "report.csv").is_file()
    assert (report_output / "errors.log").is_file()
    assert (report_output / "thumbnails").is_dir()

    assert _hashes(source) == before

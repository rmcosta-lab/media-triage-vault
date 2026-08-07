"""Integration tests: full scan -> detect -> extract -> classify pipeline and the
`classify`/`override` CLI commands, US-002 (README §38) — see
specs/2026-08-07-phase-12-classify-cli-overrides/plan.md and validation.md.
"""

from __future__ import annotations

import hashlib
import shutil
from pathlib import Path

import pytest
from sqlalchemy import Engine
from typer.testing import CliRunner

from backend.app.cli.main import app
from backend.app.core.db import create_db_and_tables, get_engine, get_session
from backend.app.models.classification import Classification
from backend.app.repositories.classification_repository import ClassificationRepository
from backend.app.repositories.media_file_repository import MediaFileRepository
from backend.app.services.classification import classify_scan
from backend.app.services.media_type import detect_media_types_for_scan
from backend.app.services.metadata import extract_metadata_for_scan
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


def test_classify_scan_routes_fixtures_correctly(engine: Engine, tmp_path: Path) -> None:
    root = tmp_path / "source"
    root.mkdir()
    _copy_fixtures(root)

    with get_session(engine) as session:
        scan = scan_folder(session, root, recursive=True)
        assert scan.id is not None
        detect_media_types_for_scan(session, scan.id)
        extract_metadata_for_scan(session, scan.id)

        classify_scan(session, scan.id)

        media_repo = MediaFileRepository(session)
        classification_repo = ClassificationRepository(session)
        rows = {mf.relative_path: mf for mf in media_repo.list_by_scan(scan.id)}

        def classification_for(name: str) -> Classification:
            media_file_id = rows[name].id
            assert media_file_id is not None
            classification = classification_repo.get_by_media_file_id(media_file_id)
            assert classification is not None
            return classification

        assert classification_for("sample_video.mp4").effective_routing_group == "video"
        assert classification_for("misnamed_video_as_jpg.jpg").effective_routing_group == "video"

        iphone = classification_for("iphone_jpeg_gps.jpg")
        assert iphone.effective_routing_group == "iphone_photo"
        assert iphone.country_code == "JP"
        assert iphone.confidence == 0.98

        screenshot = classification_for("Screenshot_20260730-152000.png")
        assert screenshot.effective_routing_group == "mobile_screenshot"

        corrupt = classification_for("corrupt_video.mp4")
        assert corrupt.effective_routing_group == "video"


def test_classify_scan_rerun_does_not_duplicate_or_clobber_override(
    engine: Engine, tmp_path: Path
) -> None:
    root = tmp_path / "source"
    root.mkdir()
    _copy_fixtures(root)

    with get_session(engine) as session:
        scan = scan_folder(session, root, recursive=True)
        assert scan.id is not None
        detect_media_types_for_scan(session, scan.id)
        extract_metadata_for_scan(session, scan.id)
        classify_scan(session, scan.id)

        media_repo = MediaFileRepository(session)
        classification_repo = ClassificationRepository(session)
        target = media_repo.list_by_scan(scan.id)[0]
        assert target.id is not None

        classification = classification_repo.get_by_media_file_id(target.id)
        assert classification is not None
        classification.manual_routing_group = "other"
        classification.effective_routing_group = "other"
        classification_repo.update(classification)

        classify_scan(session, scan.id)

        rows = media_repo.list_by_scan(scan.id)
        classifications = [
            c
            for row in rows
            if row.id is not None
            for c in [classification_repo.get_by_media_file_id(row.id)]
            if c is not None
        ]
        assert len({c.media_file_id for c in classifications}) == len(classifications)

        reclassified = classification_repo.get_by_media_file_id(target.id)
        assert reclassified is not None
        assert reclassified.manual_routing_group == "other"
        assert reclassified.effective_routing_group == "other"


def test_classify_and_override_cli_end_to_end(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    _copy_fixtures(source)
    before = _hashes(source)

    output = tmp_path / "report"
    database = tmp_path / "test.db"

    scan_result = runner.invoke(
        app, ["scan", str(source), "--output", str(output), "--database", str(database)]
    )
    assert scan_result.exit_code == 0, scan_result.output

    classify_result = runner.invoke(
        app, ["classify", "--scan-id", "1", "--database", str(database)]
    )
    assert classify_result.exit_code == 0, classify_result.output
    assert "confidence=" in classify_result.output
    assert any(group in classify_result.output for group in ("video", "iphone_photo", "other"))

    with get_session(get_engine(database)) as session:
        media_file_id = MediaFileRepository(session).list_by_scan(1)[0].id
    assert media_file_id is not None

    override_result = runner.invoke(
        app, ["override", str(media_file_id), "iphone_raw", "--database", str(database)]
    )
    assert override_result.exit_code == 0, override_result.output

    with get_session(get_engine(database)) as session:
        classification = ClassificationRepository(session).get_by_media_file_id(media_file_id)
        assert classification is not None
        assert classification.manual_routing_group == "iphone_raw"
        assert classification.effective_routing_group == "iphone_raw"
        assert classification.override_timestamp is not None

    assert _hashes(source) == before


def test_override_invalid_routing_group_exits_nonzero(tmp_path: Path) -> None:
    database = tmp_path / "test.db"
    result = runner.invoke(app, ["override", "1", "not_a_group", "--database", str(database)])
    assert result.exit_code != 0


def test_override_before_classify_exits_nonzero(tmp_path: Path) -> None:
    database = tmp_path / "test.db"
    engine = get_engine(database)
    create_db_and_tables(engine)
    result = runner.invoke(app, ["override", "1", "other", "--database", str(database)])
    assert result.exit_code != 0

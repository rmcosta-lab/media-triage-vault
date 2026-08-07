import json
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from backend.app.core.tools import resolve_tool, run_tool

FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures"

ALL_FIXTURES = [
    "iphone_jpeg_gps.jpg",
    "iphone_heic.heic",
    "IMG-20260730-WA0001.jpg",
    "Screenshot_20260730-152000.png",
    "jpeg_no_exif.jpg",
]


@pytest.mark.parametrize("filename", ALL_FIXTURES)
def test_exiftool_reads_fixture_through_resolver(filename: str) -> None:
    fixture = FIXTURES_DIR / filename
    result = run_tool("exiftool", ["-j", str(fixture)], check=True)
    payload = json.loads(result.stdout)
    assert len(payload) == 1
    assert payload[0]["FileName"] == filename


def test_exiftool_reports_injected_gps_and_make() -> None:
    fixture = FIXTURES_DIR / "iphone_jpeg_gps.jpg"
    result = run_tool("exiftool", ["-j", str(fixture)], check=True)
    tags = json.loads(result.stdout)[0]
    assert tags["Make"] == "Apple"
    assert "GPSLatitude" in tags
    assert "GPSLongitude" in tags


def test_exiftool_reports_apple_make_on_heic_fixture() -> None:
    fixture = FIXTURES_DIR / "iphone_heic.heic"
    result = run_tool("exiftool", ["-j", str(fixture)], check=True)
    tags = json.loads(result.stdout)[0]
    assert tags["Make"] == "Apple"


def test_exiftool_reports_no_exif_for_stripped_fixture() -> None:
    fixture = FIXTURES_DIR / "jpeg_no_exif.jpg"
    result = run_tool("exiftool", ["-j", str(fixture)], check=True)
    tags = json.loads(result.stdout)[0]
    assert "Make" not in tags


def test_ffprobe_reports_video_stream_for_sample_video() -> None:
    fixture = FIXTURES_DIR / "sample_video.mp4"
    result = run_tool(
        "ffprobe",
        ["-v", "error", "-show_entries", "stream=codec_type", "-of", "json", str(fixture)],
        check=True,
    )
    streams = json.loads(result.stdout)["streams"]
    assert any(stream["codec_type"] == "video" for stream in streams)


def test_exiftool_is_invoked_via_resolved_path_not_bare_command() -> None:
    fixture = FIXTURES_DIR / "iphone_jpeg_gps.jpg"
    with patch("backend.app.core.tools.subprocess.run", wraps=subprocess.run) as mocked:
        run_tool("exiftool", ["-j", str(fixture)], check=True)
    invoked_args = mocked.call_args[0][0]
    assert invoked_args[0] == str(resolve_tool("exiftool"))
    assert invoked_args[0] != "exiftool"


def test_ffprobe_is_invoked_via_resolver_lookup_not_a_bare_string() -> None:
    fixture = FIXTURES_DIR / "sample_video.mp4"
    with patch("backend.app.core.tools.subprocess.run", wraps=subprocess.run) as mocked:
        run_tool("ffprobe", ["-v", "error", str(fixture)], check=True)
    invoked_args = mocked.call_args[0][0]
    assert invoked_args[0] == str(resolve_tool("ffprobe"))
    assert invoked_args[0] != "ffprobe"

"""Unit tests for cross-platform ignore rules — see backend/app/core/ignore_patterns.py."""

from __future__ import annotations

import pytest

from backend.app.core.ignore_patterns import is_ignored_dir, is_ignored_file


@pytest.mark.parametrize(
    "name",
    [
        "Thumbs.db",
        "thumbs.db",
        "desktop.ini",
        ".DS_Store",
        "notes.tmp",
        "upload.partial",
        "~$document.docx",
        "._sidecar.jpg",
    ],
)
def test_is_ignored_file_matches_known_junk_names(name: str) -> None:
    assert is_ignored_file(name) is True


@pytest.mark.parametrize("name", ["photo.jpg", "video.mp4", "IMG_0001.HEIC"])
def test_is_ignored_file_does_not_match_normal_files(name: str) -> None:
    assert is_ignored_file(name) is False


@pytest.mark.parametrize("name", [".Spotlight-V100", ".Trashes", ".fseventsd", ".spotlight-v100"])
def test_is_ignored_dir_matches_known_junk_dirs(name: str) -> None:
    assert is_ignored_dir(name) is True


def test_is_ignored_dir_does_not_match_normal_dirs() -> None:
    assert is_ignored_dir("nested") is False

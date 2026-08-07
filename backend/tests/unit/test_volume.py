"""Unit tests for `is_same_volume` — README §17.2/17.3, roadmap Phase 15."""

from __future__ import annotations

from pathlib import Path

from backend.app.core.volume import is_same_volume


def test_same_directory_is_same_volume(tmp_path: Path) -> None:
    source = tmp_path / "a"
    destination = tmp_path / "b"
    source.mkdir()
    destination.mkdir()

    assert is_same_volume(source, destination) is True


def test_not_yet_existing_destination_resolves_via_ancestor(tmp_path: Path) -> None:
    source_file = tmp_path / "source.jpg"
    source_file.write_bytes(b"x")
    not_yet_created = tmp_path / "nested" / "deeper" / "destination.jpg"

    assert is_same_volume(source_file, not_yet_created) is True

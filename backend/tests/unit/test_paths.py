"""Unit tests for path normalization helpers — see backend/app/core/paths.py."""

from __future__ import annotations

import unicodedata
from pathlib import Path

from backend.app.core.paths import absolute_nfc, relative_nfc, to_nfc


def test_to_nfc_normalizes_nfd_input() -> None:
    nfd = unicodedata.normalize("NFD", "café")
    assert to_nfc(nfd) == unicodedata.normalize("NFC", "café")


def test_to_nfc_is_idempotent_on_nfc_input() -> None:
    nfc = unicodedata.normalize("NFC", "café")
    assert to_nfc(nfc) == nfc


def test_relative_nfc_returns_posix_style_relative_path(tmp_path: Path) -> None:
    root = tmp_path / "root"
    nested = root / "nested"
    nested.mkdir(parents=True)
    file_path = nested / "file.jpg"
    file_path.write_bytes(b"x")

    assert relative_nfc(file_path, root) == "nested/file.jpg"


def test_relative_nfc_normalizes_nfd_component(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    nfd_name = unicodedata.normalize("NFD", "café.jpg")
    file_path = root / nfd_name

    assert relative_nfc(file_path, root) == unicodedata.normalize("NFC", "café.jpg")


def test_absolute_nfc_normalizes_nfd_component(tmp_path: Path) -> None:
    nfd_name = unicodedata.normalize("NFD", "café.jpg")
    path = tmp_path / nfd_name

    assert absolute_nfc(path) == to_nfc(path.as_posix())

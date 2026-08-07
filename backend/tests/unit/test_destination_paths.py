"""Unit tests for destination-path helpers — see backend/app/core/destination_paths.py."""

from __future__ import annotations

import unicodedata

import pytest

from backend.app.core.destination_paths import (
    WINDOWS_MAX_PATH,
    exceeds_windows_path_limit,
    paths_collide,
    sanitize_path_component,
)


def test_sanitize_path_component_strips_forbidden_characters() -> None:
    assert sanitize_path_component('a<b>c:d"e/f\\g|h?i*j') == "abcdefghij"


def test_sanitize_path_component_strips_trailing_dot_and_space() -> None:
    assert sanitize_path_component("Trip Photos. ") == "Trip Photos"


def test_sanitize_path_component_passes_through_ordinary_name() -> None:
    assert sanitize_path_component("Japan") == "Japan"


@pytest.mark.parametrize(
    "reserved_name",
    ["CON", "con", "PRN", "AUX", "NUL", "COM1", "COM9", "LPT1", "LPT9", "CON.txt"],
)
def test_sanitize_path_component_prefixes_reserved_windows_names(reserved_name: str) -> None:
    result = sanitize_path_component(reserved_name)
    assert result == f"_{reserved_name}"


def test_sanitize_path_component_raises_when_nothing_survives() -> None:
    with pytest.raises(ValueError, match="empty"):
        sanitize_path_component('<>:"/\\|?*')


def test_exceeds_windows_path_limit_true_over_boundary() -> None:
    assert exceeds_windows_path_limit("D:/" + "a" * WINDOWS_MAX_PATH) is True


def test_exceeds_windows_path_limit_false_at_boundary() -> None:
    path = "a" * WINDOWS_MAX_PATH
    assert len(path) == WINDOWS_MAX_PATH
    assert exceeds_windows_path_limit(path) is False


def test_paths_collide_case_only_difference() -> None:
    assert paths_collide("D:/Midia/Foto.jpg", "D:/Midia/foto.JPG") is True


def test_paths_collide_nfc_nfd_pair_of_same_name() -> None:
    nfc = unicodedata.normalize("NFC", "D:/Midia/café.jpg")
    nfd = unicodedata.normalize("NFD", "D:/Midia/café.jpg")
    assert paths_collide(nfc, nfd) is True


def test_paths_collide_false_for_different_names() -> None:
    assert paths_collide("D:/Midia/Foto.jpg", "D:/Midia/Outro.jpg") is False

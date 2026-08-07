"""Path normalization helpers — see ``specs/tech-stack.md`` "Unicode normalization".

Paths are persisted NFC-normalized (NTFS/exFAT canonical form) while every
filesystem call keeps using the OS-native ``Path`` object as walked, since a
collection that crossed platforms may contain NFD-named entries (HFS+ and
older macOS writers).
"""

from __future__ import annotations

import unicodedata
from pathlib import Path


def to_nfc(value: str) -> str:
    """Return ``value`` normalized to NFC."""
    return unicodedata.normalize("NFC", value)


def absolute_nfc(path: Path) -> str:
    """Return ``path``'s absolute, NFC-normalized, POSIX-style form for storage."""
    return to_nfc(path.as_posix())


def relative_nfc(path: Path, root: Path) -> str:
    """Return ``path``'s NFC-normalized, POSIX-style path relative to ``root``."""
    return to_nfc(path.relative_to(root).as_posix())

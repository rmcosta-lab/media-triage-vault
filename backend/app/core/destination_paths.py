"""Destination-path helpers — README §16 Etapa 4/5, roadmap Phase 14.

Pure functions with no filesystem access: sanitizing a generated path
segment to the portable intersection of Windows/macOS naming rules, the
260-character Windows path-length check, and case-insensitive collision
comparison (NTFS/exFAT/default-APFS are all case-insensitive — see
``specs/tech-stack.md`` "Cross-platform").
"""

from __future__ import annotations

from backend.app.core.paths import to_nfc

FORBIDDEN_CHARS = '<>:"/\\|?*' + "".join(chr(c) for c in range(32))
RESERVED_WINDOWS_NAMES = (
    {"CON", "PRN", "AUX", "NUL"}
    | {f"COM{i}" for i in range(1, 10)}
    | {f"LPT{i}" for i in range(1, 10)}
)
WINDOWS_MAX_PATH = 260


def sanitize_path_component(name: str) -> str:
    """Sanitize `name` to a single portable path segment.

    Strips forbidden characters, trailing dots/spaces, and rewrites a
    reserved Windows device name (comparing the stem before any
    extension). Raises `ValueError` if nothing usable survives.
    """
    cleaned = "".join(char for char in name if char not in FORBIDDEN_CHARS)
    cleaned = cleaned.rstrip(". ")
    if not cleaned:
        raise ValueError(f"{name!r} sanitizes to an empty path component")

    stem = cleaned.split(".", 1)[0].upper()
    if stem in RESERVED_WINDOWS_NAMES:
        cleaned = f"_{cleaned}"

    return cleaned


def exceeds_windows_path_limit(path: str) -> bool:
    """Return True if `path` exceeds the 260-character Windows `MAX_PATH` limit."""
    return len(path) > WINDOWS_MAX_PATH


def paths_collide(a: str, b: str) -> bool:
    """Return True if `a` and `b` name the same path on a case-insensitive volume."""
    return to_nfc(a).casefold() == to_nfc(b).casefold()

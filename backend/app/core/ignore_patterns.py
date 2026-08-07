"""Cross-platform scanner ignore rules — README §7.1, ``specs/tech-stack.md`` "Junk files".

Directory names here are pruned from the walk entirely (the scanner never
descends into them), while file names/globs are filtered per entry.
"""

from __future__ import annotations

import fnmatch

IGNORED_FILE_NAMES: frozenset[str] = frozenset({"thumbs.db", "desktop.ini", ".ds_store"})

IGNORED_FILE_GLOBS: tuple[str, ...] = ("*.tmp", "*.partial", "~$*", "._*")

IGNORED_DIR_NAMES: frozenset[str] = frozenset({".spotlight-v100", ".trashes", ".fseventsd"})


def is_ignored_file(name: str) -> bool:
    """Return whether ``name`` matches a known junk file name or glob."""
    lowered = name.lower()
    if lowered in IGNORED_FILE_NAMES:
        return True
    return any(fnmatch.fnmatch(lowered, pattern) for pattern in IGNORED_FILE_GLOBS)


def is_ignored_dir(name: str) -> bool:
    """Return whether ``name`` matches a known junk directory name."""
    return name.lower() in IGNORED_DIR_NAMES

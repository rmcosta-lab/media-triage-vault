"""Same-volume detection — README §17.2/17.3, roadmap Phase 15.

`is_same_volume` is the one place the executor decides between an atomic
rename and the hash -> copy-temp -> verify -> rename -> delete-source
sequence. `os.stat().st_dev` already encodes "same filesystem" correctly
on every platform this project targets (the drive number on Windows, the
device id on POSIX), so no call site ever inspects a drive letter or
mount point itself.
"""

from __future__ import annotations

from pathlib import Path


def _nearest_existing_ancestor(path: Path) -> Path:
    ancestor = path
    while not ancestor.exists():
        parent = ancestor.parent
        if parent == ancestor:
            return ancestor
        ancestor = parent
    return ancestor


def is_same_volume(source: Path, destination: Path) -> bool:
    """Return True if `source` and `destination` live on the same volume.

    `destination` may not exist yet (a planned file path) — the check
    walks up to the nearest existing ancestor directory before calling
    `os.stat`.
    """
    source_stat = _nearest_existing_ancestor(source).stat()
    destination_stat = _nearest_existing_ancestor(destination).stat()
    return source_stat.st_dev == destination_stat.st_dev

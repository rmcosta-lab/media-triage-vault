"""SHA-256 file hashing — README §17.4, roadmap Phase 15.

Streamed in fixed-size chunks so hashing a large video never loads the
whole file into memory.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

_DEFAULT_CHUNK_SIZE = 1024 * 1024


def sha256_file(path: Path, chunk_size: int = _DEFAULT_CHUNK_SIZE) -> str:
    """Return the SHA-256 hex digest of the file at `path`."""
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()

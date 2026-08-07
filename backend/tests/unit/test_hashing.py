"""Unit tests for `sha256_file` — README §17.4, roadmap Phase 15."""

from __future__ import annotations

import hashlib
from pathlib import Path

from backend.app.core.hashing import sha256_file


def test_known_content_produces_known_digest(tmp_path: Path) -> None:
    path = tmp_path / "known.txt"
    path.write_bytes(b"hello world")

    assert sha256_file(path) == hashlib.sha256(b"hello world").hexdigest()


def test_chunked_read_matches_whole_file_digest(tmp_path: Path) -> None:
    content = b"x" * (2 * 1024 * 1024 + 17)  # spans multiple 1 MiB chunks
    path = tmp_path / "large.bin"
    path.write_bytes(content)

    assert sha256_file(path, chunk_size=64 * 1024) == hashlib.sha256(content).hexdigest()

# Changelog

## 2026-08-07

- Phase 5 — Media type detection: `backend/app/services/media_type.py` combines a fixed extension→category/MIME table (`backend/app/core/media_signatures.py`, README §6.1–§6.3, deliberately not `stdlib mimetypes`/the OS registry) with a magic-byte file-signature sniffer (JPEG, PNG, GIF, BMP, WEBP, TIFF-based RAW, Fujifilm RAF, HEIC/HEIF and MP4/MOV `ftyp` boxes, AVI `RIFF`, MKV/WEBM `EBML`) into a `media_kind` (`image`/`video`/`unsupported`) and an `extension_mismatch` flag on `MediaFile`; `detect_media_types_for_scan` runs detection over an existing scan's pending rows and records read errors without aborting; new `misnamed_video_as_jpg.jpg` fixture exercises the roadmap's misnamed-file done criterion.
- Phase 4 — Scanner: recursive `pathlib` walk (`backend/app/services/scanner.py`) with cross-platform ignore patterns (`Thumbs.db`, `desktop.ini`, `*.tmp`, `.DS_Store`, `._*` AppleDouble sidecars, `.Spotlight-V100`, `.Trashes`, `.fseventsd`) in `backend/app/core/ignore_patterns.py`, no symlink following, batched persistence with a progress callback, NFC-normalized path storage via `backend/app/core/paths.py`, and per-entry access errors recorded without aborting the scan; unit and integration tests including an unreadable entry, an AppleDouble sidecar, and an NFD/NFC filename pair.
- Phase 3 — Data model + SQLite: `Scan` and `MediaFile` SQLModel tables (README §24.1/§24.2) with a foreign-key relationship; SQLite engine/session module resolving `runtime/database/media_organizer.db` relative to the repo root; generic `Repository[T]` CRUD layer with `ScanRepository`/`MediaFileRepository`; round-trip and CRUD tests against a real SQLite engine.
- Phase 2 — Tooling + fixtures: vendored ExifTool (Windows) under `tools/exiftool/windows-x64/` behind a single per-platform resolver in `backend/app/core/tools.py`; FFmpeg/FFprobe resolved from the system PATH for now instead of vendored, to avoid committing a ~100-250MB binary to git history (see `specs/tech-stack.md` "Bundled binaries"); added the first six test fixtures (iPhone JPEG w/ GPS, HEIC, WhatsApp-named file, screenshot-named PNG, small MP4, JPEG without EXIF) and a smoke test proving both tools run through the resolver.
- Phase 1 — Repo bootstrap: `pyproject.toml` pinned to Python 3.13 and managed with `uv`, ruff/mypy/pytest/pre-commit wired together, minimal `backend/app/` package skeleton, and one trivial passing test.

## 2026-07-31

- Add initial technical specifications and objectives for Local Media Organizer.
- Add initial skills for project management: changelog, deep review, finish phase, implement phase, start phase.
- Add `AGENTS.md` agent guide for the repository.

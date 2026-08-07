# Validation — Phase 1: Repo bootstrap

### Functional

- [x] `pyproject.toml` exists at repo root with `requires-python` pinned to
      Python 3.13 and a `uv`-compatible dependency/dev-group structure.
      (Inspected `pyproject.toml`: `requires-python = ">=3.13,<3.14"`,
      `[dependency-groups] dev = [...]`.)
- [x] `uv sync` completes and produces `uv.lock`. (Ran `uv sync`; `uv.lock`
      present at repo root. Note: this machine's TLS-intercepting
      proxy/AV rejects the public CA chain, so `[tool.uv] system-certs =
      true` was added to `pyproject.toml` so plain `uv sync`/`uv run` work
      without extra flags — a one-time local dev-environment accommodation,
      not a runtime network dependency.)
- [x] `backend/app/` package exists and is importable as `backend.app`.
      (`backend/__init__.py`, `backend/app/__init__.py` present; covered by
      the trivial test below.)
- [x] `backend/tests/unit/` contains one trivial test, and it passes.
      (`backend/tests/unit/test_bootstrap.py::test_backend_app_package_is_importable`
      — 1 passed.)
- [x] `.pre-commit-config.yaml` exists and configures ruff (lint + format)
      and mypy. (Ran `uv run pre-commit run --all-files` after staging: all
      three hooks — ruff, ruff-format, mypy — passed.)
- [x] `uv run media-organizer --help` is not expected to work yet (no CLI
      exists until Phase 7) — confirmed not part of this phase's scope.
      (Ran it: `error: Failed to spawn: media-organizer — program not
      found`, as expected — no `[project.scripts]` entry point defined.)

### Tests

- [x] `uv run pytest` passes with the one trivial test collected and green.
      (`collected 1 item` / `1 passed`.)
- [x] No other tests exist yet beyond the trivial bootstrap test (feature
      tests start in Phase 2+). (Only file under `backend/tests/` is
      `unit/test_bootstrap.py`.)

### Safety

- [x] No network call is made by any dependency added in this phase or by
      the bootstrap process itself (`uv sync` reaches only the configured
      package index). (`dependencies = []`; dev group is ruff/mypy/
      pytest/pre-commit only — none perform runtime network I/O; no
      application code exists yet to make calls.)
- [x] No source file outside the repo is touched; nothing under `runtime/`,
      `tools/`, or user data directories is created or modified. (Verified
      `runtime/`, `tools/`, `backend/data/` are all absent; `git status`
      shows only the files this plan added.)
- [x] No external tool (ExifTool, FFmpeg) is invoked — that's Phase 2. (No
      `subprocess` calls anywhere in the new code.)

### Technical

- [x] `uv run ruff check .` clean. (`All checks passed!`)
- [x] `uv run ruff format --check .` clean. (`5 files already formatted` —
      required excluding `*.md` from ruff's file resolution, since ruff
      0.16 formats Python code fences inside Markdown by default and would
      otherwise have reformatted the READMEs, which are out of this
      phase's scope.)
- [x] `uv run mypy backend` clean. (`Success: no issues found in 5 source
      files`.)
- [x] `uv run pytest` green. (`1 passed`.)

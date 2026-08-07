# Plan — Phase 1: Repo bootstrap

## 1. Project metadata (`pyproject.toml`)

- Create `pyproject.toml` at repo root: `[project]` with name
  `media-triage-vault` (or `media-organizer`, matching the CLI entry point
  name used across the specs), `requires-python = ">=3.13,<3.14"`, version
  `0.1.0`.
- Add `[project.optional-dependencies]` or a `dependency-groups`/`dev`
  group (uv-native `[dependency-groups]`) holding `ruff`, `mypy`, `pytest`,
  `pre-commit`. No runtime dependencies yet — none are needed until Phase 2
  onward.
- Add `[tool.ruff]` (line length, target-version `py313`, lint rule
  selection — at least `E`, `F`, `I`, `UP`) and `[tool.ruff.format]`.
- Add `[tool.mypy]` (`python_version = "3.13"`, `strict = true` or an
  explicit strict-equivalent flag set, `packages = ["backend"]` or
  `files = ["backend"]`).
- Add `[tool.pytest.ini_options]` (`testpaths = ["backend/tests"]`).
- Add a `[build-system]` section (`hatchling` or `setuptools`) so
  `backend/app` is installable/importable as `backend.app`.

## 2. Package skeleton

- Create `backend/__init__.py` and `backend/app/__init__.py` (empty except
  maybe a version string) — no feature subpackages yet, per
  `AGENTS.md` "Repository layout".
- Create `backend/tests/__init__.py` and `backend/tests/unit/__init__.py`.

## 3. Trivial test

- Create `backend/tests/unit/test_bootstrap.py` with one test that imports
  `backend.app` and asserts the package is importable (e.g. checks
  `backend.app.__name__ == "backend.app"` or similar). This is the "one
  trivial passing test" the roadmap calls for.

## 4. Lint/type/test tooling wiring

- Run `uv sync` to generate `uv.lock` and the local `.venv`.
- Verify `uv run pytest`, `uv run ruff check .`, `uv run ruff format --check .`,
  `uv run mypy backend` all execute (not necessarily meaningful yet, but
  wired and clean).

## 5. pre-commit

- Create `.pre-commit-config.yaml` with hooks for `ruff` (lint, with
  `--fix` disabled or enabled per convention) and `ruff-format`, plus a
  local `mypy` hook running `uv run mypy backend`.
- Do not install the git hook into the developer's global git config as
  part of this automated run (that's a local `pre-commit install` the user
  runs themselves) — just ensure the config file is correct and
  `pre-commit run --all-files` succeeds if pre-commit is available.

## 6. Repo hygiene

- Update `.gitignore` (create if absent) with Python/uv artifacts:
  `.venv/`, `__pycache__/`, `*.pyc`, `.mypy_cache/`, `.ruff_cache/`,
  `.pytest_cache/`, `dist/`, `*.egg-info/`.

## 7. Verification

- `uv sync`
- `uv run pytest` — green, includes the one trivial test.
- `uv run ruff check .` — clean.
- `uv run ruff format --check .` — clean.
- `uv run mypy backend` — clean.
- `uv run pre-commit run --all-files` (if pre-commit is installed in the
  environment) — clean.

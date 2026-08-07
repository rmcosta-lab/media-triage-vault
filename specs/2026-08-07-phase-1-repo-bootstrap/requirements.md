# Requirements — Phase 1: Repo bootstrap

## Objective

Stand up the Python project scaffolding that every later phase builds on: a
`uv`-managed `pyproject.toml` pinned to Python 3.13, lint/type/test tooling
(ruff, mypy, pytest) wired together with pre-commit, a minimal `backend/app/`
package skeleton, and one trivial passing test proving the toolchain works
end to end.

## Scope

### In

- `pyproject.toml` — project metadata, Python 3.13 requirement, dependency
  groups (runtime vs. dev/test), tool configuration sections for `ruff`,
  `mypy`, and `pytest`.
- `uv.lock` generated via `uv sync`.
- `backend/app/` package skeleton: `__init__.py` only, no feature code (no
  `core`, `models`, `repositories`, `services`, `rules`, `templates`,
  `api` subpackages yet — those appear as their own phases land, per
  `AGENTS.md` "Repository layout").
- `backend/tests/` skeleton with `unit/` and one trivial test that imports
  `backend.app` and asserts it loads.
- `.pre-commit-config.yaml` running ruff (lint + format) and mypy on commit.
- `.gitignore` additions for Python/uv artifacts (`.venv/`, `__pycache__/`,
  `*.pyc`, `.mypy_cache/`, `.ruff_cache/`, `.pytest_cache/`) if not already
  covered.

### Out

- Any feature code: scanner, tools resolver, data models, CLI commands.
  Those are Phases 2–7 and later.
- `runtime/`, `tools/`, `backend/data/` directories — created when their
  owning phase lands, per `AGENTS.md`.
- Frontend tooling (`pnpm`, Next.js) — Stage G.
- CI workflow files — not called for by this phase's done criterion; can
  follow once there is code worth gating.

## Source of truth

- README §32 "Roadmap inicial" — Fase 0 — Bootstrap: "criar repositório;
  configurar Python, `uv`, lint e testes; adicionar ExifTool e FFmpeg; criar
  banco SQLite; criar fixtures iniciais." This spec covers the "Python, uv,
  lint e testes" slice only — ExifTool/FFmpeg, the SQLite schema, and
  fixtures are Phases 2 and 3.
- `specs/roadmap.md` — Phase 1 entry (Stage A — Foundation): pyproject.toml
  with uv, Python 3.13, ruff, mypy, pytest, pre-commit; package skeleton
  `backend/app/`; one trivial passing test. Done when `uv run pytest` and
  lint pass clean.
- `specs/tech-stack.md` — "Backend (core engine — Phase A)" pins Python
  3.13 + uv, and "Quality" pins pytest, ruff, mypy, pre-commit.
- `AGENTS.md` — "Repository layout" (directories appear as their phase
  lands) and "Local commands" (the exact `uv run ...` invocations this
  phase must make work).

## Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Scope | Implement as written | User confirmed the roadmap phase description as-is. |
| Implementation approach | Tech-lead's call | User deferred to `specs/tech-stack.md` and `specs/mission.md`. |
| Validation criteria | Standard checks only | User confirmed no extra criteria beyond the roadmap's done condition and the standard lint/type/test gate. |
| Package layout | `backend/app/__init__.py` only, no empty subpackages | `AGENTS.md` explicitly says subdirectories appear as their phase lands — creating them now would be speculative structure. |
| Dependency manager | `uv` exclusively, `uv.lock` committed | Pinned in `specs/tech-stack.md`; matches `AGENTS.md` "Dependencies" convention. |
| Trivial test location | `backend/tests/unit/test_bootstrap.py` | Matches the `backend/tests/{unit,integration,fixtures}` layout in `AGENTS.md`. |

## Constraints

- **No network**: bootstrap must not add any dependency that performs
  network calls at runtime; `uv sync` itself is a one-time local dev-machine
  operation, not part of the shipped app.
- **Read-only until Phase 14**: no file-moving code is introduced in this
  phase — it doesn't exist yet, and this phase must not add any.
- **Core before interface**: no FastAPI or frontend scaffolding here; this
  phase is Python-engine-only.
- **Dependencies**: any dependency added must already be listed in
  `specs/tech-stack.md`, or the spec must be updated first — for Phase 1
  that means uv, ruff, mypy, pytest, pre-commit, and their direct
  transitive requirements only.
- **Language**: all code, comments, config, and commit messages in English.

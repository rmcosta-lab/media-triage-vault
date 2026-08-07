# Agent guide — media-triage-vault

## The project in a few lines

Local Media Organizer: a local application that scans a folder of photos and
videos, extracts metadata, classifies each file along independent dimensions,
presents the results for review, and — only after explicit confirmation — moves
files into user-defined destinations. Everything runs offline on the user's
machine.

## Read before you touch code

- `specs/mission.md` — what we are building and the seven non-negotiable
  principles. Read it before any design decision.
- `specs/tech-stack.md` — pinned technology decisions and the cross-platform
  rules. Read it before changing dependencies, architecture, or data flow.
- `specs/roadmap.md` — the phase order and each phase's done criteria.
- For a planned phase, also read its `specs/YYYY-MM-DD-<slug>/` directory
  (`requirements.md`, `plan.md`, `validation.md`).
- `README_media_triage_vault.md` is the detailed source of truth for the rules
  (classification tables, scoring, acceptance criteria). Specs cite it by
  section number — follow the citation rather than reinventing a rule.

## Non-negotiables

These come from `specs/mission.md` and override convenience:

1. **No network.** No external API, telemetry, analytics, CDN asset, or online
   geocoding — ever. The API layer binds to `127.0.0.1` only.
2. **Read-only until Phase 14.** No code that moves, renames, or deletes user
   files exists before the move planner. Analysis never writes to source files.
3. **Never destroy data.** Default collision policy is `error`; a source is
   deleted only after the destination copy is validated; every move goes through
   the transactional journal and is idempotent and resumable.
4. **Explainable classification.** Every automatic result carries a confidence
   score and human-readable reasons; manual overrides stay separate from
   automatic ones.
5. **Core before interface.** Engine and CLI first, then FastAPI, then Next.js,
   and Tauri only after the flow is validated.

## Repository layout

Directories appear as their phase lands; do not create them ahead of time.

```text
backend/app/{api,cli,core,models,repositories,services,rules,templates}
backend/tests/{unit,integration,fixtures}
backend/data/geography/countries.geojson
frontend/                  # Stage G onwards
tools/{exiftool,ffmpeg}/<platform>/
runtime/{database,reports,thumbnails,logs}/
specs/
```

## Local commands

Backend (from the repo root, once Phase 1 has landed):

```bash
uv sync
uv run pytest
uv run pytest backend/tests/unit -q
uv run ruff check .
uv run ruff format .
uv run mypy backend
uv run media-organizer --help
```

Frontend (inside `frontend/`, from Stage G onwards) uses `pnpm`:
`pnpm dev`, `pnpm build`, `pnpm lint`, `pnpm test`.

After a code change, run checks proportional to the scope. For a completed
phase, run at least `uv run ruff check .`, `uv run mypy backend` and
`uv run pytest`, plus the phase's own `validation.md`.

## Implementation conventions

- **Dependencies**: `uv` only, pinned in `uv.lock`. Adding a dependency that is
  not in `specs/tech-stack.md` needs a decision recorded there first.
- **External tools**: ExifTool is resolved through the bundled per-platform
  resolver, never from a bare `PATH` lookup. FFmpeg/FFprobe are an interim
  exception (Phase 2, see `specs/tech-stack.md` "Bundled binaries"): too
  large to vendor into git for the MVP, so the resolver discovers them once
  via `shutil.which` and still centralizes the lookup behind
  `resolve_tool()` — no call site invokes a bare command string directly.
  Invoke every tool with `subprocess` argument lists — never a shell
  string, never `shell=True`. A single-frame FFmpeg extraction (thumbnails,
  Phase 13) needs an explicit `-update 1` — without it, newer FFmpeg's
  `image2` muxer silently writes nothing for a plain filename target and
  still exits `0`, so check `returncode` *and* that the destination file
  actually exists.
- **Paths**: store and compare NFC-normalized; pass the OS-native form to every
  filesystem call. Sanitize destination names to the portable intersection and
  check the 260-character Windows limit at plan time.
- **Types**: SQLModel is the single model layer (validation + persistence). No
  parallel Pydantic schemas duplicating a table. Table modules that declare a
  `Relationship()` (Phase 3, see `backend/app/models/`) must **not** use
  `from __future__ import annotations` — SQLModel resolves relationship
  targets from the raw class annotation at class-creation time, and under
  PEP 563 that annotation is unparsed source text, which breaks
  `Relationship()`. Use quoted forward references instead
  (`list["MediaFile"]`, `"Scan"`), with the related class imported under
  `TYPE_CHECKING` to avoid circular imports. A nullable one-to-one
  `Relationship()` needs `Optional["Target"]`, not `"Target | None"` — the
  latter is a string SQLAlchemy can't resolve as a forward reference at
  mapper-configuration time. Also never name a `Relationship()` attribute
  `metadata` — it collides with SQLAlchemy's reserved `Base.metadata`
  (Phase 6: `MediaFile.media_metadata` / `MediaMetadata.media_file`).
  `rawpy` (Phase 13) only re-exports its enums/exceptions
  (`ThumbFormat`, `LibRawError`, ...) under `TYPE_CHECKING` in its own
  `__init__.py`, which trips mypy strict's no-implicit-reexport check —
  import those specific names from `rawpy._rawpy` directly instead of
  `rawpy`; `rawpy.imread` itself is unaffected. SQLite round-trips a
  `datetime` column as **naive** even when it was written timezone-aware
  (Phase 14) — reattach `tzinfo=UTC` to a value read back from the
  database before comparing it to a freshly computed aware `datetime`
  (e.g. from `datetime.fromtimestamp(..., tz=UTC)`), or the comparison
  silently returns "not equal" every time instead of raising. A
  repository method that replaces a table's rows for some key (delete
  the old set, insert the new one) must `session.flush()` between the
  deletes and the inserts (Phase 14,
  `DestinationRuleRepository.replace_for_scan`) — SQLAlchemy's default
  flush order runs inserts before deletes, which trips a unique
  constraint shared between an old row and its replacement.
- **Tests**: every rule and every failure path gets a test. Move-related code is
  tested against temp directories, including interrupted and mismatched-hash
  runs. Fixtures live in `backend/tests/fixtures/` and stay small.
- **CLI**: every `media-organizer` subcommand hangs off the single `app`
  in `backend/app/cli/main.py` (Phase 7). Keep the `@app.callback()`
  there even if it stays a no-op — without it, Typer collapses an app with
  exactly one `@app.command()` into a bare single-command CLI and drops the
  subcommand name (`media-organizer scan ...` would stop parsing as
  written). Command bodies only orchestrate existing services; no new
  detection/extraction/classification logic belongs in `cli/`.
- **Language**: code, comments, specs, and commit messages in English.

## Testing on real data

Never point a work-in-progress scan at the user's real collection without being
asked. Use fixtures; if a real-folder check is needed, ask first and keep it
read-only.

## Skills in `.claude`

Local skills describe this project's workflows and should be followed when the
matching task is requested:

- `start-phase` — detect the next roadmap phase, gather requirements, create the
  spec directory and branch.
- `implement-phase` — execute `plan.md` and verify `validation.md`.
- `finish-phase` — update changelog/roadmap, then run the local finish and merge
  flow when asked.
- `changelog` — update `CHANGELOG.md` from Git history.
- `deep-review` — read-only review with prioritized findings before a merge.

Read the corresponding `SKILL.md` in `.claude/skills/<name>/` before running the
respective flow.

## MCP servers

No MCP server is required for the MVP — the project has no cloud backend, no
hosting provider, and no remote database. If a browser MCP is connected, it is
only useful from Stage G (frontend) onwards, as a complement to `pytest` and
Playwright, never as a substitute for them.

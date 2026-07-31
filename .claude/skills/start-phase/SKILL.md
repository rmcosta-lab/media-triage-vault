---
name: start-phase
description: Kick off the next incomplete roadmap phase: detect it from specs/roadmap.md, gather requirements via questions, then create the spec directory, branch, and spec files.
---

# Start phase

Kick off the next incomplete roadmap phase: gather requirements from the user, create a spec directory, branch, and spec files.

## Instructions

### 1. Detect next phase

- Read `specs/roadmap.md`.
- Phases are checkbox items grouped under `## Stage X` headings, in the form
  `- [ ] **Phase N — Name.** Description. *Done when …*`.
- Find the first item whose checkbox is still `- [ ]`.
- Extract the phase number, name, description, and the *Done when* criterion.
- If every phase is checked, tell the user and stop.
- Tell the user which phase was detected, its stage, its description, and its done criterion.

### 2. Ask the user about the feature spec

Use `AskUserQuestion` to ask **three grouped questions** before writing anything to disk:

**Question 1 — Scope**: Show the roadmap text for this phase and ask:

> "Here is the roadmap item for Phase N. Should it be implemented as written, or adjusted? Anything to add or leave out?"
> Options: "Implement as written", "I want to adjust scope" (+ let them type).

**Question 2 — Implementation approach**: Based on the phase content, ask:

> "Any preferences on the implementation approach? (e.g. module layout, library choice, data model shape, CLI surface)"
> Options: "You decide based on specs/tech-stack.md and specs/mission.md", "I have preferences" (+ let them type).

**Question 3 — Validation criteria**: Ask:

> "Any validation criteria beyond the roadmap's done criterion and the standard lint/type/test checks?"
> Options: "Standard checks are enough", "I have additional criteria" (+ let them type).

### 3. Create the spec directory

- Directory name: `specs/YYYY-MM-DD-phase-N-<slug>` using today's date, the phase number, and a kebab-case slug derived from the phase name (e.g. `specs/2026-08-02-phase-1-repo-bootstrap`).
- If a directory for this phase already exists, tell the user and stop instead of overwriting it.

### 4. Write spec files

Use the user's answers, `specs/mission.md`, `specs/tech-stack.md`, `AGENTS.md`, the roadmap item, and the README sections it cites to write three files. Write them in English, matching the existing specs.

**`requirements.md`**

- Title: `# Requirements — Phase N: <Phase Name>`
- Sections: Objective, Scope (In / Out), Source of truth (README sections and spec rules this phase implements), Decisions (table of decision / choice / rationale), Constraints (which mission principles constrain this phase — e.g. read-only, no network, no bare `PATH` lookups)
- Reflect the user's scope answers

**`plan.md`**

- Title: `# Plan — Phase N: <Phase Name>`
- Numbered task groups (e.g. 1. Models, 2. Service, 3. CLI wiring, 4. Tests)
- Each group has a bullet list of concrete tasks naming the files to create or change
- Final group is always "Verification" with the check commands
- Reflect the user's implementation approach answers

**`validation.md`**

- Title: `# Validation — Phase N: <Phase Name>`
- Sections with `### Category` headings and `- [ ]` checkboxes
- Standard categories: Functional (the roadmap's *Done when* criterion, broken into checks), Tests, Safety, Technical
- Add categories from the user's validation answers
- **Safety** always includes, where applicable to the phase: no network call is made, no source file is modified or deleted, external tools are invoked through the resolver with argument lists
- **Technical** always includes: `uv run ruff check .` clean, `uv run ruff format --check .` clean, `uv run mypy backend` clean, `uv run pytest` green

### 5. Create branch

- Create and switch to a new branch: `phase-N-<slug>` (e.g. `phase-1-repo-bootstrap`).

### 6. Summary

- Print a short summary: phase detected, spec directory created, branch name.
- Remind the user they can start implementing with `/implement-phase`.

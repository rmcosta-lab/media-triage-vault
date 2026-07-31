---
name: implement-phase
description: Implement the current roadmap phase by following its plan.md, then verify every criterion in validation.md (lint, types, tests, acceptance checks).
---

# Implement phase

Implement the current phase by following its plan, then verify all validation criteria.

## Instructions

### 1. Detect current phase

- Read the current branch name (e.g. `phase-4-scanner`).
- Extract the phase number and slug from the branch.
- Locate the matching spec directory under `specs/` (e.g. `specs/2026-08-05-phase-4-scanner/`).
- If no matching spec directory is found, tell the user and stop.

### 2. Load spec files

Read all three spec files from the phase's spec directory:

- `requirements.md` — objectives, scope, decisions, constraints.
- `plan.md` — the ordered list of implementation tasks.
- `validation.md` — the acceptance criteria to verify after implementation.

Also read `specs/mission.md`, `specs/tech-stack.md` and `AGENTS.md` for project-wide context, plus the README sections that `requirements.md` cites for the rules this phase implements.

### 3. Implement the plan

Execute each numbered task group in `plan.md` in order, top to bottom:

- Follow the plan faithfully — do not skip, reorder, or add tasks beyond what the plan specifies.
- Use `requirements.md` decisions to resolve ambiguity.
- Honour the non-negotiables in `AGENTS.md` at all times: no network calls, no writes to source media before Phase 14, external tools only via the resolver with `subprocess` argument lists.
- Write tests alongside the code they cover, not as an afterthought at the end.
- After completing each task group, briefly tell the user what was done before moving to the next.
- If a task is unclear or blocked, ask the user before proceeding.

### 4. Run automated checks

After all plan tasks are complete, run the checks from the Technical section of `validation.md`:

1. `uv run ruff check .` — no violations.
2. `uv run ruff format --check .` — no reformatting needed.
3. `uv run mypy backend` — no errors.
4. `uv run pytest` — all tests pass.

If any fails, fix the issue and re-run until all four pass. Report real output — never mark a check green from assumption.

### 5. Validate acceptance criteria

Go through every checkbox in `validation.md`, section by section:

- **Automatable checks** (lint, types, tests, CLI behaviour on fixtures): run the command and mark pass/fail.
- **Inspectable checks** (models, file layout, generated report contents, journal states): read the relevant source files or run the CLI against fixtures to verify the output.
- **Safety checks**: verify concretely — e.g. confirm fixture files are unmodified (compare mtime/hash before and after), confirm no outbound request path exists in the new code.
- **Manual checks** (anything needing the user's real collection or a Windows machine): list these separately as items the user must verify.

Present results as a checklist with status:

```text
### Section Name
- [x] Check that passed (how it was verified)
- [x] Another passing check
- [ ] Manual check — requires user verification
```

- Update `validation.md` with the results.

### 6. Fix failures

If any automatable or inspectable check fails:

- Fix the issue.
- Re-run the failed check to confirm the fix.
- Update the checklist.

Repeat until all non-manual checks pass.

### 7. Summary

Print a final summary:

- Total checks: passed / total (excluding manual).
- Whether the roadmap's *Done when* criterion for this phase is met.
- List any manual checks the user still needs to verify.
- Remind the user to run `/finish-phase` when satisfied.

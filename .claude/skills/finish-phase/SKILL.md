---
name: finish-phase
description: Wrap up the current roadmap phase: update the changelog, mark the phase complete in specs/roadmap.md, commit, merge to main, and delete the branch.
---

# Finish phase

Wrap up the current roadmap phase: update changelog, mark complete, commit, merge to main, and clean up the branch.

## Instructions

### 1. Detect current phase

- Read the current branch name (e.g. `phase-4-scanner`).
- Extract the phase number and slug from the branch.
- Open `specs/roadmap.md` and locate the matching `- [ ] **Phase N — …**` item.
- If no matching phase is found, stop and tell the user.

### 2. Confirm the phase is actually done

- Read the phase's `validation.md` and confirm every non-manual checkbox is ticked.
- Re-run the four checks: `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy backend`, `uv run pytest`.
- If anything fails or is still unchecked, report it and stop — do not merge a phase that does not meet its own criteria.

### 3. Update changelog

- Invoke the `changelog` skill to update `CHANGELOG.md` with recent commits.

### 4. Update tech-stack and AGENTS

- Update `specs/tech-stack.md` if the phase introduced or replaced a technology, or resolved a decision that was open.
- Update `AGENTS.md` if the phase added a convention or command future agents need, without duplicating content from `specs/tech-stack.md` or `specs/roadmap.md`.

### 5. Mark phase complete in roadmap

- In `specs/roadmap.md`, tick the phase's checkbox: `- [ ] **Phase N — Name.**` → `- [x] **Phase N — Name.**`.
- Leave the description and *Done when* text intact — later phases depend on reading it.
- Follow the same formatting used by previously completed phases.

### 6. Commit

- Stage only the changed files (`CHANGELOG.md`, `specs/roadmap.md`, the phase's spec directory, and the phase's code).
- Create a single commit. Use the message pattern: `Complete Phase N — <Phase Name>`.
- Do NOT push.

### 7. Merge to main

- Switch to `main`.
- Merge the phase branch with `git merge --no-ff <branch>` to preserve the merge commit.
- Do NOT push.

### 8. Delete the phase branch

- Delete the local phase branch: `git branch -d <branch>`.
- Do NOT delete remote branches.

### 9. Summary

- Print a short summary: what was merged, the merge commit hash, the next unchecked phase in the roadmap, and a reminder to `git push` when ready.

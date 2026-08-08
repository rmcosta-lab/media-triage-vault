# Plan — Phase 23: Offline AI runtime

## 1. Pin the optional AI environment

- Add `[project.optional-dependencies].ai` in `pyproject.toml` for stable
  PyTorch, Transformers, Accelerate, and Safetensors releases that install on
  Python 3.13/Windows and load both configured model layouts.
- Resolve with `uv`, commit the resulting `uv.lock`, and document the exact CPU
  and CUDA build tested; do not use nightly, Git, or editable AI dependencies.
- Record the exact local SigLIP/Qwen snapshot revisions/fingerprints and verify
  their model-card/license metadata before accepting either configured model.
- Register the `ai_real` pytest marker while keeping real-model tests skipped
  unless their explicit opt-in environment flag is present.
- Add `runtime/embeddings/` only when Phase 25 begins; Phase 23 creates no model
  or embedding cache inside the repository.

## 2. Persist AI settings without importing AI packages

- Add `backend/app/models/ai_settings.py` with the singleton `AiSettings` table
  defined in `requirements.md`; export it through `backend/app/models/__init__.py`
  so `SQLModel.metadata.create_all()` creates the new table.
- Add `backend/app/repositories/ai_settings_repository.py` with `get()` and
  `replace()` semantics. Validate one row only, allowed device values, positive
  batch overrides, and NFC-normalized absolute local paths.
- Add `backend/app/services/ai_settings.py` to merge persisted settings with
  optional environment/CLI overrides without changing the stored row.
- Unit-test first creation, replacement, invalid device/batch/path values, and
  precedence of runtime overrides.

## 3. Build the offline runtime boundary

- Create `backend/app/ai/` with dependency-free public types/errors and lazy
  runtime adapters; importing any non-AI backend module must not import
  `torch`, `transformers`, or `huggingface_hub`.
- In the loader module, set `HF_HUB_OFFLINE=1` and
  `TRANSFORMERS_OFFLINE=1` before the first Transformers import and pass
  `local_files_only=True` at every processor/model load call.
- Reject URLs, Hub-style identifiers, missing directories, incomplete model
  layouts, and remote-code requirements with stable error codes and actionable
  messages. Never set `trust_remote_code=True`.
- Validate SigLIP and Qwen manifests read-only. Compute/cache a SHA-256 manifest
  fingerprint covering configuration/tokenizer files and weight files so later
  phases can key persisted results to exact local artifacts.
- Add device-profile resolution: `auto` → CUDA when available else CPU; explicit
  unavailable CUDA → `AI_DEVICE_UNAVAILABLE`; CUDA default batch 8, CPU default
  batch 1; positive override wins; CUDA BF16 when supported, FP16 otherwise,
  CPU FP32.
- Expose an explicit unload helper that drops references, runs Python garbage
  collection, and clears the CUDA allocator only when CUDA was used.

## 4. Add configuration and diagnostic CLI commands

- Extend the single Typer app in `backend/app/cli/main.py` with `ai-config`:
  show current effective settings when called without changes; accept local
  SigLIP/Qwen paths, `auto|cpu|cuda`, batch override/reset, and embedding-default
  toggles; persist only after the complete request validates.
- Add `ai-doctor`: verify the optional packages, settings, both model manifests,
  resolved device/dtype/batch, then load and unload SigLIP from the local path.
- Print a concise machine-readable-friendly summary without exposing user media
  paths beyond the explicitly configured model directories.
- Map typed failures to a non-zero exit and stable codes such as
  `AI_RUNTIME_UNAVAILABLE`, `AI_MODEL_PATH_INVALID`,
  `AI_MODEL_INCOMPATIBLE`, and `AI_DEVICE_UNAVAILABLE`.

## 5. Test the runtime boundary

- Add unit tests for lazy optional imports, offline environment setup, local-path
  rejection, model-manifest validation/fingerprinting, device selection,
  precision, batch defaults/override, unload behavior, and typed errors. Use
  fake torch/Transformers adapters; no real weights are needed.
- Add CLI integration tests against a temporary SQLite database and synthetic
  model directory manifests for configuration, successful diagnostics, missing
  extra, missing files, invalid explicit CUDA, and non-zero failure exits.
- Add an opt-in `ai_real` integration test that blocks socket connections,
  loads the configured real SigLIP directory, performs a minimal processor/model
  smoke pass, reports the device, and unloads cleanly.
- Run the real test twice before merge: forced CPU and forced CUDA on the RTX
  4090. Validate the configured Qwen directory manifest in both passes without
  performing Qwen inference.
- Assert that model directories and a representative media fixture have
  identical hashes/timestamps before and after diagnostics.

## 6. Verification

- Base environment: `uv run ruff check .`
- Base environment: `uv run ruff format --check .`
- Base environment: `uv run mypy backend`
- Base environment: `uv run pytest`
- AI environment: `uv sync --extra ai`
- AI environment: `uv run --extra ai media-organizer ai-doctor`
- Real CPU suite: set the documented opt-in/model-path/device variables, then
  run `uv run --extra ai pytest -m ai_real`.
- Real CUDA suite: repeat with `device=cuda` on the RTX 4090.
- Inspect the diagnostic with network disabled and confirm a missing local file
  fails immediately rather than attempting a download.

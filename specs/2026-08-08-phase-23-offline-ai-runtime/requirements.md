# Requirements — Phase 23: Offline AI runtime

## Objective

Establish the optional, strictly offline runtime on which every later Stage H
phase depends. The base application must remain usable without AI packages,
while an AI-enabled installation can validate local SigLIP 2 and Qwen3-VL model
directories, select CPU or CUDA safely, persist runtime preferences, and load
SigLIP 2 for a diagnostic without opening a network connection.

This phase does not classify media. It proves that the dependency, settings,
device, model-validation, and offline-loading boundaries are sound before any
AI run or result table is introduced.

## Scope

### In

- An optional project extra named `ai` containing stable, Python 3.13-compatible
  releases of PyTorch, Transformers, Accelerate, and Safetensors. Select the
  newest mutually compatible stable releases available from official package
  indexes at implementation time; do not use a nightly build or a Git/source
  dependency. Record the resolved versions in `uv.lock` and the validation notes.
- A new `AiSettings` SQLModel table with a singleton row containing:
  - absolute local `siglip_model_path` and `qwen_model_path` values;
  - `preferred_device`: `auto`, `cpu`, or `cuda`;
  - nullable positive `batch_size_override`;
  - `store_embeddings_default`, defaulting to `True`;
  - created/updated timestamps.
- A repository/service boundary for reading and replacing the singleton settings
  without importing optional AI packages.
- An AI runtime package that:
  - imports PyTorch/Transformers lazily and converts missing packages into a
    typed `AI_RUNTIME_UNAVAILABLE` error;
  - sets `HF_HUB_OFFLINE=1` and `TRANSFORMERS_OFFLINE=1` before importing
    Transformers;
  - passes local filesystem paths and `local_files_only=True` to every
    `from_pretrained()` call;
  - rejects URLs and model IDs where a local directory is required;
  - validates the expected configuration, processor/tokenizer, Safetensors, and
    weight-index files without modifying the model directory;
  - produces a deterministic model-manifest fingerprint for later cache keys;
  - selects CUDA for `auto` only when PyTorch reports it available, otherwise
    CPU; explicit unavailable CUDA fails rather than silently falling back;
  - starts with conservative batch defaults of 8 on CUDA and 1 on CPU, unless a
    positive override is configured;
  - uses BF16 on CUDA when supported, FP16 otherwise, and FP32 on CPU.
- A SigLIP diagnostic that loads
  `google/siglip2-so400m-patch14-384` from the configured directory, reports the
  resolved device/dtype/model fingerprint, and unloads the model cleanly. The
  Qwen path is validated in this phase but Qwen inference begins in Phase 27.
- `media-organizer ai-config` to persist/show settings and
  `media-organizer ai-doctor` to validate packages, settings, local files,
  device selection, and SigLIP loading. Commands remain attached to the single
  Typer `app` in `backend/app/cli/main.py`.
- Standard tests with fake import/model adapters plus a dedicated opt-in
  `ai_real` test requiring real local weights. Before merge, the real test is
  run once with forced CPU and once with the RTX 4090.

### Out

- Model downloads, remote model IDs, Hugging Face Hub access, telemetry, or any
  other network-enabled fallback.
- Committing model weights, tokenizers, generated caches, or a golden dataset.
- `AiRun`, source selection, scanning, SHA-256 media fingerprints, cancellation,
  resume, or background AI jobs — Phase 24.
- Theme taxonomy, inference results, embeddings, or SigLIP classification —
  Phase 25.
- Golden-dataset calibration — Phase 26; Qwen inference — Phase 27.
- Local-AI HTTP endpoints — Phase 28; UI — Phases 29–31; move planning — Phase 32.
- FAISS/search, Florence-2, OCR, captions, video inference, TensorRT, or face
  clustering.

## Source of truth

- `specs/roadmap.md`, Phase 23 — optional runtime, persistent local paths,
  CPU/CUDA detection, conservative profiles, and a network-free real SigLIP
  diagnostic.
- `specs/mission.md` principles 1, 4, 6, and 7 — fully local processing,
  explainable results, deterministic rules before AI, and core/CLI before API/UI.
- `specs/tech-stack.md`, "Local AI" — selected models, optional installation,
  offline loading, supported devices, and Stage H exclusions.
- `README_models.md` §§6–10 and §§19–20 — SigLIP/Qwen responsibilities,
  cascading strategy, confidence caveat, hardware, and local-only principles.
- Official model cards for `google/siglip2-so400m-patch14-384` and
  `Qwen/Qwen3-VL-4B-Instruct`; official Transformers offline-loading guidance.

## Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Dependency isolation | Optional `ai` project extra | Keeps the existing application and normal tests free of heavyweight AI/GPU requirements. |
| Model acquisition | User downloads weights separately and configures absolute local directories | Preserves the project's unconditional no-network rule and keeps multi-gigabyte weights out of Git/installers. |
| Model identifiers | SigLIP 2 So400m for bulk; Qwen3-VL-4B-Instruct path validated now | Matches the approved Stage H cascade; Qwen execution intentionally waits for Phase 27. |
| Model licensing | Record the exact local snapshot revision/fingerprint and revalidate the model card/license (Apache-2.0 at planning time) before acceptance | A mutable local model directory must not inherit a license assumption solely from its configured display name. |
| Offline enforcement | Offline environment flags plus `local_files_only=True` and local-path validation | Defense in depth: a missing file must fail immediately, never trigger a Hub lookup or timeout. |
| Settings storage | New singleton SQLModel table; environment/CLI values may override at runtime without mutating the row | Gives the later UI persistent settings while preserving scriptable diagnostics and tests. New-table-only schema work remains compatible with `create_all`. |
| Device policy | `auto` prefers CUDA; explicit unavailable CUDA is an error; CPU is fully supported | Avoids surprising fallback while honoring the required CPU and RTX 4090 validation matrix. |
| Batch defaults | CUDA 8, CPU 1, positive manual override | Conservative starting values prioritize reliable first execution; Stage H records performance rather than gating on it. |
| Numeric precision | CUDA BF16 when supported, otherwise FP16; CPU FP32 | Fits the target GPU while retaining a portable, predictable CPU path. |
| Model lifecycle | The diagnostic owns one loaded model and releases it before returning | Establishes the no-simultaneous-model invariant required by the later cascade. |
| Real-model tests | Dedicated opt-in `ai_real` suite, mandatory before phase merge on CPU and RTX 4090 | Keeps normal CI portable while making the actual selected weights part of phase acceptance. |

## Constraints

- **No network:** no call path may resolve a model name, download a missing file,
  submit telemetry, or wait on a remote timeout. Tests must fail any attempted
  socket connection during model validation/loading.
- **Read-only model and source inputs:** diagnostics read model directories and
  may write only normal application state under SQLite/`runtime`; they never
  alter weights or media files.
- **Base installation stays healthy:** importing the backend, running the CLI,
  serving the API, and running `uv run pytest` without the `ai` extra must work.
- **No premature feature work:** Phase 23 introduces settings/runtime boundaries
  only; it must not add analysis jobs, theme records, embeddings, API routes, UI,
  or move behavior.
- **Pinned dependencies:** dependency additions are recorded here and in
  `specs/tech-stack.md` before code uses them, then locked with `uv`.
- **Existing schema compatibility:** use new tables only; do not change the
  meaning or columns of `Scan`, `MediaFile`, `Classification`, `Job`, or move
  models in this phase.

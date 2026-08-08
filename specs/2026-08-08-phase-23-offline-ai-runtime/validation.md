# Validation — Phase 23: Offline AI runtime

### Functional

- [ ] The base application imports, serves, and runs its normal CLI without the
      `ai` extra installed.
- [ ] `ai-config` persists valid absolute local SigLIP/Qwen paths, device,
      batch override, and embedding default; invalid input leaves the previous
      singleton settings unchanged.
- [ ] `auto` selects CUDA when available and CPU otherwise.
- [ ] Explicit `cuda` fails with `AI_DEVICE_UNAVAILABLE` when CUDA is absent;
      it never silently falls back to CPU.
- [ ] Automatic profiles resolve to batch 8 on CUDA and batch 1 on CPU unless a
      positive override is configured.
- [ ] `ai-doctor` validates both local model manifests, loads SigLIP 2 on the
      requested device, reports device/dtype/fingerprint, and unloads it.
- [ ] A missing optional package or incomplete model directory returns a stable,
      actionable error and non-zero CLI exit.

### Roadmap done criterion

- [ ] The real SigLIP 2 diagnostic passes with forced CPU using the configured
      local model directory and no network access.
- [ ] The same diagnostic passes with forced CUDA on the RTX 4090 and no network
      access.

### Tests

- [ ] Unit tests cover settings CRUD/validation/override precedence.
- [ ] Unit tests cover lazy imports, local-only enforcement, path/model
      validation, model fingerprinting, device/dtype/batch selection, unload,
      and every typed failure code.
- [ ] CLI integration tests cover show/update/invalid settings and doctor
      success/failure using synthetic local manifests.
- [ ] The dedicated `ai_real` test loads the real SigLIP processor/model and
      performs a minimal local smoke pass on CPU and CUDA.
- [ ] Qwen3-VL-4B's configured directory is validated read-only; no Qwen
      inference is introduced before Phase 27.
- [ ] The exact SigLIP/Qwen local snapshot fingerprints and verified licenses
      are recorded in the phase validation evidence.
- [ ] `uv run pytest` skips the opt-in real-model test cleanly and remains green
      without AI packages or weights.

### Safety

- [ ] Socket access is blocked during the real and fake loader tests; any
      attempted connection fails the test.
- [ ] Every Transformers load receives a local filesystem path and
      `local_files_only=True`; offline environment flags are set before import.
- [ ] URLs, Hub IDs, missing local files, and remote-code requirements fail
      immediately; no download or telemetry fallback exists.
- [ ] Model directories are read-only inputs and retain identical hashes,
      sizes, and timestamps after diagnostics.
- [ ] No source media file is modified, renamed, moved, or deleted.
- [ ] No model weight, tokenizer, generated cache, or golden-dataset media is
      added to Git.

### Compatibility

- [ ] The locked stable AI dependencies install with Python 3.13 on Windows 11.
- [ ] CPU SigLIP loading uses FP32 and completes on the target machine.
- [ ] RTX 4090 loading selects BF16 when supported (FP16 fallback otherwise)
      and releases model references/CUDA allocator state after the diagnostic.
- [ ] Adding the new table through `SQLModel.metadata.create_all()` leaves all
      existing tables and data unchanged.

### Technical

- [ ] `uv run ruff check .` clean.
- [ ] `uv run ruff format --check .` clean.
- [ ] `uv run mypy backend` clean.
- [ ] `uv run pytest` green without the `ai` extra.
- [ ] `uv run --extra ai pytest -m ai_real` green with forced CPU.
- [ ] `uv run --extra ai pytest -m ai_real` green with forced CUDA on the RTX
      4090.

### Manual

- [ ] With networking disabled, `media-organizer ai-doctor` reports both model
      manifests, resolved CPU profile, SigLIP load, and clean unload.
- [ ] Repeating with CUDA reports the RTX 4090 and the selected CUDA dtype.
- [ ] Renaming one required local model file makes the command fail immediately
      with `AI_MODEL_INCOMPATIBLE`; restoring it returns the diagnostic to green.

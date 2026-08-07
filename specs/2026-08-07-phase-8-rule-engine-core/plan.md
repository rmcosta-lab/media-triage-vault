# Plan — Phase 8: Rule engine core

## 1. Model

- New `backend/app/models/classification.py`: `Classification` table per
  README §24.3 — `id`, `media_file_id: int = Field(foreign_key="mediafile.id", unique=True)`,
  `media_kind`, `source_origin`, `image_format`,
  `automatic_routing_group`, `manual_routing_group: str | None = None`,
  `effective_routing_group`, `confidence: float`, `requires_review: bool`,
  `reasons_json: str`, `device_make: str | None`, `device_model: str | None`,
  `captured_at: datetime | None`, `gps_latitude: float | None`,
  `gps_longitude: float | None`, `country_code: str | None`,
  `country_name: str | None`. No `from __future__ import annotations`
  (declares `Relationship()`); `media_file: "MediaFile"` relationship,
  `MediaFile` imported under `TYPE_CHECKING`.
- `backend/app/models/media_file.py`: add
  `classification: Optional["Classification"] = Relationship(back_populates="media_file")`,
  `Classification` imported under `TYPE_CHECKING`.
- `backend/app/models/__init__.py`: export `Classification`.

## 2. Repository

- `backend/app/repositories/classification_repository.py`: thin
  `Repository[Classification]` subclass with
  `get_by_media_file_id(media_file_id: int) -> Classification | None`,
  mirroring `MediaMetadataRepository`.

## 3. Rule engine core

- New `backend/app/rules/__init__.py` (empty).
- New `backend/app/rules/engine.py`:
  - `ROUTING_GROUPS: tuple[str, ...]` — the six groups in priority order.
  - `DEFAULT_ROUTING_GROUP = "other"`.
  - `RuleResult` frozen dataclass: `label: str`, `score: float`,
    `reasons: list[str] = field(default_factory=list)`.
  - `ClassificationRule` `Protocol`: `name: str`;
    `evaluate(self, media: MediaFile, metadata: dict[str, Any]) -> RuleResult`.
  - `ClassificationResult` frozen dataclass: `media_kind: str`,
    `source_origin: str`, `image_format: str`, `routing_group: str`,
    `confidence: float`, `reasons: list[str]`, `requires_review: bool`.
  - `DEFAULT_REVIEW_THRESHOLD = 0.60`.
  - `resolve_routing_group(candidates: Mapping[str, RuleResult]) -> tuple[str, RuleResult | None]`:
    iterate `ROUTING_GROUPS` in order, return the first group present in
    `candidates` and its `RuleResult`; if none present, return
    `(DEFAULT_ROUTING_GROUP, None)`.
  - `build_classification_result(*, media_kind: str, image_format: str, candidates: Mapping[str, RuleResult], review_threshold: float = DEFAULT_REVIEW_THRESHOLD) -> ClassificationResult`:
    calls `resolve_routing_group`; on a winner, fills `source_origin`/
    `confidence`/`reasons` from it and sets
    `requires_review = confidence < review_threshold`; on no winner,
    returns `source_origin="unknown"`, `confidence=0.0`,
    `reasons=["No rule matched any routing group; defaulted to \"other\"."]`,
    `requires_review=True`.

## 4. Tests

- `backend/tests/unit/test_rule_engine.py`:
  - `resolve_routing_group` — synthetic candidates covering: single
    candidate, multiple candidates where a higher-priority group wins
    despite a lower score, empty mapping falls back to `other`/`None`,
    `other` explicitly present alongside a higher-priority group (higher
    priority still wins).
  - `build_classification_result` — winner present (confidence/reasons/
    source_origin copied through, `requires_review` true below threshold
    and false above/at it), no winner (fallback shape, `requires_review`
    is `True`), custom `review_threshold` override.
  - `ClassificationRule` protocol — a minimal synthetic implementation
    satisfies `isinstance(x, ClassificationRule)` (runtime-checkable) or,
    if not runtime-checkable, a `mypy`-only structural check via a small
    conforming class used directly as a `ClassificationRule`.
- `backend/tests/unit/test_models.py` (or a new
  `test_classification_model.py`): `Classification` round-trips through
  SQLite with a `MediaFile` foreign key, mirroring the existing
  `MediaMetadata` round-trip test.

## 5. Verification

- `uv run ruff check .`
- `uv run ruff format --check .`
- `uv run mypy backend`
- `uv run pytest`

"""Classification orchestrator — wires Phases 8-11 together, roadmap Phase 12.

Runs every concrete rule (Phase 9/10) against a scan's `image`/`video`
rows, resolves the winning routing group (Phase 8), resolves GPS to a
country (Phase 11), and persists one `Classification` row per file. A
manual override's `manual_routing_group`/`effective_routing_group`/
`override_timestamp` survive a re-run — only the automatic fields are
ever overwritten here.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from sqlmodel import Session

from backend.app.models.classification import Classification
from backend.app.models.media_file import MediaFile
from backend.app.models.media_metadata import MediaMetadata
from backend.app.repositories.classification_repository import ClassificationRepository
from backend.app.repositories.media_file_repository import MediaFileRepository
from backend.app.repositories.media_metadata_repository import MediaMetadataRepository
from backend.app.rules.engine import (
    DEFAULT_REVIEW_THRESHOLD,
    ClassificationResult,
    ClassificationRule,
    RuleResult,
    build_classification_result,
    resolve_routing_group,
)
from backend.app.rules.iphone import IPhoneRawRule, IPhoneRule
from backend.app.rules.screenshot import AUTO_CLASSIFY_THRESHOLD, ScreenshotRule
from backend.app.rules.video import VideoRule
from backend.app.rules.whatsapp import WhatsAppRule
from backend.app.services.country import extract_coordinates, get_default_resolver

# README §6.2 — RAW image extensions.
RAW_EXTENSIONS = frozenset({".dng", ".cr2", ".cr3", ".nef", ".arw", ".raf", ".rw2", ".orf"})

RULES: tuple[ClassificationRule, ...] = (
    VideoRule(),
    IPhoneRule(),
    IPhoneRawRule(),
    WhatsAppRule(),
    ScreenshotRule(),
)


@dataclass(frozen=True)
class ClassificationSummary:
    """Roll-up counters for a scan-level classification run."""

    routing_group_counts: dict[str, int] = field(default_factory=dict)
    requires_review: int = 0
    skipped: int = 0


def _load_metadata_dict(media_metadata: MediaMetadata | None) -> dict[str, Any]:
    if media_metadata is None or not media_metadata.raw_json:
        return {}
    result: dict[str, Any] = json.loads(media_metadata.raw_json)
    return result


def _determine_image_format(media: MediaFile) -> str:
    if media.media_kind == "video":
        return "not_applicable"
    if media.file_type == "DNG" or (media.extension or "").lower() in RAW_EXTENSIONS:
        return "raw"
    return "standard"


def _build_candidates(media: MediaFile, metadata: dict[str, Any]) -> dict[str, RuleResult]:
    candidates: dict[str, RuleResult] = {}
    for rule in RULES:
        result = rule.evaluate(media, metadata)
        if result.score > 0:
            candidates[rule.routing_group] = result
    return candidates


def _review_threshold_for(routing_group: str) -> float:
    if routing_group == ScreenshotRule.routing_group:
        return AUTO_CLASSIFY_THRESHOLD
    return DEFAULT_REVIEW_THRESHOLD


def _classify_one(media: MediaFile, metadata: dict[str, Any]) -> ClassificationResult:
    candidates = _build_candidates(media, metadata)
    routing_group, _winner = resolve_routing_group(candidates)
    threshold = _review_threshold_for(routing_group)
    return build_classification_result(
        media_kind=media.media_kind or "unsupported",
        image_format=_determine_image_format(media),
        candidates=candidates,
        review_threshold=threshold,
    )


def classify_scan(
    session: Session,
    scan_id: int,
    *,
    on_progress: Callable[[MediaFile, ClassificationResult], None] | None = None,
    should_cancel: Callable[[], bool] | None = None,
) -> ClassificationSummary:
    """Classify every `image`/`video` row of `scan_id` and persist `Classification` rows."""
    media_file_repository = MediaFileRepository(session)
    media_metadata_repository = MediaMetadataRepository(session)
    classification_repository = ClassificationRepository(session)

    routing_group_counts: dict[str, int] = {}
    requires_review = 0
    skipped = 0

    for media in media_file_repository.list_by_scan(scan_id):
        if should_cancel is not None and should_cancel():
            break
        if media.media_kind not in ("image", "video") or media.id is None:
            skipped += 1
            continue

        media_metadata = media_metadata_repository.get_by_media_file_id(media.id)
        metadata = _load_metadata_dict(media_metadata)

        result = _classify_one(media, metadata)

        coordinates = extract_coordinates(metadata)
        country = get_default_resolver().resolve(coordinates)

        existing = classification_repository.get_by_media_file_id(media.id)
        if existing is None:
            classification = Classification(
                media_file_id=media.id,
                media_kind=result.media_kind,
                source_origin=result.source_origin,
                image_format=result.image_format,
                automatic_routing_group=result.routing_group,
                effective_routing_group=result.routing_group,
                confidence=result.confidence,
                requires_review=result.requires_review,
                reasons_json=json.dumps(result.reasons),
                device_make=metadata.get("Make"),
                device_model=metadata.get("Model"),
                captured_at=media_metadata.capture_datetime if media_metadata else None,
                gps_latitude=coordinates.latitude if coordinates else None,
                gps_longitude=coordinates.longitude if coordinates else None,
                country_code=country.country_code,
                country_name=country.country_name,
            )
            classification_repository.create(classification)
        else:
            existing.media_kind = result.media_kind
            existing.source_origin = result.source_origin
            existing.image_format = result.image_format
            existing.automatic_routing_group = result.routing_group
            existing.confidence = result.confidence
            existing.requires_review = result.requires_review
            existing.reasons_json = json.dumps(result.reasons)
            existing.device_make = metadata.get("Make")
            existing.device_model = metadata.get("Model")
            existing.captured_at = media_metadata.capture_datetime if media_metadata else None
            existing.gps_latitude = coordinates.latitude if coordinates else None
            existing.gps_longitude = coordinates.longitude if coordinates else None
            existing.country_code = country.country_code
            existing.country_name = country.country_name
            if existing.manual_routing_group is None:
                existing.effective_routing_group = result.routing_group
            classification_repository.update(existing)

        routing_group_counts[result.routing_group] = (
            routing_group_counts.get(result.routing_group, 0) + 1
        )
        if result.requires_review:
            requires_review += 1
        if on_progress is not None:
            on_progress(media, result)

    return ClassificationSummary(
        routing_group_counts=routing_group_counts,
        requires_review=requires_review,
        skipped=skipped,
    )

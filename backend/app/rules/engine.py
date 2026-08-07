"""Classification rule engine core — README §15 "Motor de classificação", roadmap Phase 8.

Defines the shared contract concrete rules (Phase 9: video/iPhone/RAW;
Phase 10: WhatsApp/screenshot) implement against, plus the routing-priority
resolver that picks a single winning routing group when more than one
rule's candidate applies. No concrete rule lives here.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    from backend.app.models.media_file import MediaFile

# README §5.1 — fixed priority order; `other` is always the fallback.
ROUTING_GROUPS: tuple[str, ...] = (
    "video",
    "mobile_screenshot",
    "whatsapp_received",
    "iphone_raw",
    "iphone_photo",
    "other",
)
DEFAULT_ROUTING_GROUP = "other"
DEFAULT_REVIEW_THRESHOLD = 0.60


@dataclass(frozen=True)
class RuleResult:
    """A single rule's evaluation output — README §15's JSON schema."""

    label: str
    score: float
    reasons: list[str] = field(default_factory=list)


class ClassificationRule(Protocol):
    """README §15.1 — the interface every concrete rule implements."""

    name: str

    def evaluate(self, media: MediaFile, metadata: dict[str, Any]) -> RuleResult: ...


@dataclass(frozen=True)
class ClassificationResult:
    """README §15.2 — the assembled, explainable result for one file."""

    media_kind: str
    source_origin: str
    image_format: str
    routing_group: str
    confidence: float
    reasons: list[str]
    requires_review: bool


def resolve_routing_group(
    candidates: Mapping[str, RuleResult],
) -> tuple[str, RuleResult | None]:
    """Pick the highest-priority routing group among ``candidates``.

    ``candidates`` maps a routing-group name to the ``RuleResult`` that
    nominated it — a rule "fires" simply by being present as a key. Groups
    absent from ``candidates`` are treated as not applicable. Returns
    ``(DEFAULT_ROUTING_GROUP, None)`` when nothing applies.
    """
    for group in ROUTING_GROUPS:
        if group in candidates:
            return group, candidates[group]
    return DEFAULT_ROUTING_GROUP, None


def build_classification_result(
    *,
    media_kind: str,
    image_format: str,
    candidates: Mapping[str, RuleResult],
    review_threshold: float = DEFAULT_REVIEW_THRESHOLD,
) -> ClassificationResult:
    """Assemble a full ``ClassificationResult`` from resolved rule candidates."""
    routing_group, winner = resolve_routing_group(candidates)

    if winner is None:
        return ClassificationResult(
            media_kind=media_kind,
            source_origin="unknown",
            image_format=image_format,
            routing_group=routing_group,
            confidence=0.0,
            reasons=['No rule matched any routing group; defaulted to "other".'],
            requires_review=True,
        )

    return ClassificationResult(
        media_kind=media_kind,
        source_origin=winner.label,
        image_format=image_format,
        routing_group=routing_group,
        confidence=winner.score,
        reasons=list(winner.reasons),
        requires_review=winner.score < review_threshold,
    )

"""Unit tests for backend.app.rules.engine — see
specs/2026-08-07-phase-8-rule-engine-core/plan.md and validation.md.

Exercises the priority resolver and result assembly against synthetic
RuleResult data; no concrete rule exists yet (Phase 9/10).
"""

from __future__ import annotations

from typing import Any

from backend.app.models.media_file import MediaFile
from backend.app.rules.engine import (
    ClassificationRule,
    RuleResult,
    build_classification_result,
    resolve_routing_group,
)


def test_resolve_routing_group_single_candidate() -> None:
    candidates = {"iphone_photo": RuleResult(label="iphone_camera", score=0.95, reasons=["x"])}
    group, winner = resolve_routing_group(candidates)
    assert group == "iphone_photo"
    assert winner is not None
    assert winner.label == "iphone_camera"


def test_resolve_routing_group_higher_priority_wins_despite_lower_score() -> None:
    candidates = {
        "iphone_photo": RuleResult(label="iphone_camera", score=0.99, reasons=[]),
        "video": RuleResult(label="video", score=0.51, reasons=["MIME video/mp4"]),
    }
    group, winner = resolve_routing_group(candidates)
    assert group == "video"
    assert winner is not None
    assert winner.score == 0.51


def test_resolve_routing_group_empty_falls_back_to_other() -> None:
    group, winner = resolve_routing_group({})
    assert group == "other"
    assert winner is None


def test_resolve_routing_group_other_loses_to_higher_priority_candidate() -> None:
    candidates = {
        "other": RuleResult(label="other", score=1.0, reasons=[]),
        "whatsapp_received": RuleResult(label="whatsapp_received", score=0.7, reasons=[]),
    }
    group, _winner = resolve_routing_group(candidates)
    assert group == "whatsapp_received"


def test_resolve_routing_group_other_wins_when_alone() -> None:
    candidates = {"other": RuleResult(label="other", score=0.2, reasons=[])}
    group, winner = resolve_routing_group(candidates)
    assert group == "other"
    assert winner is not None


def test_build_classification_result_winner_above_threshold_no_review() -> None:
    candidates = {
        "iphone_photo": RuleResult(label="iphone_camera", score=0.95, reasons=["EXIF Make=Apple"])
    }
    result = build_classification_result(
        media_kind="image", image_format="standard", candidates=candidates
    )
    assert result.routing_group == "iphone_photo"
    assert result.source_origin == "iphone_camera"
    assert result.confidence == 0.95
    assert result.reasons == ["EXIF Make=Apple"]
    assert result.requires_review is False
    assert result.media_kind == "image"
    assert result.image_format == "standard"


def test_build_classification_result_winner_below_threshold_requires_review() -> None:
    candidates = {"iphone_photo": RuleResult(label="iphone_camera", score=0.40, reasons=["x"])}
    result = build_classification_result(
        media_kind="image", image_format="standard", candidates=candidates
    )
    assert result.requires_review is True


def test_build_classification_result_no_winner_falls_back_to_other() -> None:
    result = build_classification_result(media_kind="image", image_format="standard", candidates={})
    assert result.routing_group == "other"
    assert result.source_origin == "unknown"
    assert result.confidence == 0.0
    assert result.requires_review is True
    assert result.reasons


def test_build_classification_result_custom_review_threshold() -> None:
    candidates = {"video": RuleResult(label="video", score=0.55, reasons=["x"])}
    lenient = build_classification_result(
        media_kind="video",
        image_format="not_applicable",
        candidates=candidates,
        review_threshold=0.50,
    )
    strict = build_classification_result(
        media_kind="video",
        image_format="not_applicable",
        candidates=candidates,
        review_threshold=0.90,
    )
    assert lenient.requires_review is False
    assert strict.requires_review is True


def test_synthetic_rule_conforms_to_classification_rule_protocol() -> None:
    class _AlwaysVideoRule:
        name = "always_video"

        def evaluate(self, media: Any, metadata: dict[str, Any]) -> RuleResult:
            return RuleResult(label="video", score=1.0, reasons=["synthetic"])

    media = MediaFile(
        scan_id=1,
        absolute_path="a.mp4",
        relative_path="a.mp4",
        file_name="a.mp4",
        extension=".mp4",
        size_bytes=1,
        processing_status="pending",
    )
    rule: ClassificationRule = _AlwaysVideoRule()
    result = rule.evaluate(media=media, metadata={})
    assert result.label == "video"
    assert result.score == 1.0

"""Static report generation — README §19, roadmap Phase 13.

Joins `MediaFile` + `MediaMetadata` + `Classification` for a scan into
`report.json`/`.csv`/`.html` plus a regenerated `errors.log`, all written
under one `--output` directory so the README §43 first-delivery bundle
comes from a single command. Thumbnails (this phase's `thumbnails.py`)
land in a `thumbnails/` folder relative to `report.html` (README §19.4).
Coordinates are never included — same exclusion Phase 7's
`_media_metadata_to_dict` already applies (README §14.4/§28).
"""

from __future__ import annotations

import csv
import dataclasses
import json
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape
from sqlmodel import Session

from backend.app.cli.scan_report import _json_default, _media_metadata_to_dict, write_error_log
from backend.app.models.media_file import MediaFile
from backend.app.models.scan import Scan
from backend.app.repositories.classification_repository import ClassificationRepository
from backend.app.repositories.media_file_repository import MediaFileRepository
from backend.app.repositories.media_metadata_repository import MediaMetadataRepository
from backend.app.repositories.scan_repository import ScanRepository
from backend.app.services.thumbnails import ThumbnailResult, generate_thumbnails_for_scan

TEMPLATES_DIR = Path(__file__).resolve().parents[1] / "templates"

UNCLASSIFIED_GROUP = "unclassified"


@dataclass(frozen=True)
class ReportRow:
    """One file's flattened report record — no coordinates, ever."""

    media_file_id: int
    relative_path: str
    media_kind: str | None
    extension: str
    size_bytes: int
    width: int | None
    height: int | None
    duration_seconds: float | None
    capture_datetime: datetime | None
    make: str | None
    model: str | None
    software: str | None
    lens_model: str | None
    routing_group: str
    source_origin: str | None
    image_format: str | None
    confidence: float | None
    requires_review: bool
    reasons: list[str]
    country_code: str | None
    country_name: str | None
    manual_override: bool
    error_code: str | None
    error_message: str | None
    thumbnail_path: str | None


@dataclass(frozen=True)
class ReportSummary:
    """Roll-up counters and totals for one report generation run."""

    total_files: int
    total_bytes: int
    thumbnails_generated: int
    thumbnails_failed: int
    low_confidence_count: int
    error_count: int
    totals_by_group: dict[str, int] = field(default_factory=dict)
    totals_by_country: dict[str, int] = field(default_factory=dict)


def _build_rows(
    session: Session,
    media_files: list[MediaFile],
    thumbnail_results: dict[int, ThumbnailResult],
) -> list[ReportRow]:
    metadata_repository = MediaMetadataRepository(session)
    classification_repository = ClassificationRepository(session)
    scan_ids = {media.scan_id for media in media_files}
    if len(scan_ids) > 1:
        raise ValueError("Report rows must all belong to the same scan")
    scan_id = next(iter(scan_ids), None)
    metadata_items = metadata_repository.list_by_scan(scan_id) if scan_id is not None else []
    classification_items = (
        classification_repository.list_by_scan(scan_id) if scan_id is not None else []
    )
    metadata_by_file_id = {item.media_file_id: item for item in metadata_items}
    classification_by_file_id = {item.media_file_id: item for item in classification_items}
    rows: list[ReportRow] = []

    for media in media_files:
        if media.id is None:
            continue

        metadata = metadata_by_file_id.get(media.id)
        metadata_fields: dict[str, Any] = (
            _media_metadata_to_dict(metadata) if metadata is not None else {}
        )

        classification = classification_by_file_id.get(media.id)

        thumbnail_result = thumbnail_results.get(media.id)
        thumbnail_path = (
            f"thumbnails/{media.id}.jpg" if thumbnail_result and thumbnail_result.success else None
        )

        rows.append(
            ReportRow(
                media_file_id=media.id,
                relative_path=media.relative_path,
                media_kind=media.media_kind,
                extension=media.extension,
                size_bytes=media.size_bytes,
                width=media.width,
                height=media.height,
                duration_seconds=media.duration_seconds,
                capture_datetime=metadata_fields.get("capture_datetime"),
                make=metadata_fields.get("make"),
                model=metadata_fields.get("model"),
                software=metadata_fields.get("software"),
                lens_model=metadata_fields.get("lens_model"),
                routing_group=(
                    classification.effective_routing_group
                    if classification is not None
                    else UNCLASSIFIED_GROUP
                ),
                source_origin=classification.source_origin if classification is not None else None,
                image_format=classification.image_format if classification is not None else None,
                confidence=classification.confidence if classification is not None else None,
                requires_review=(
                    classification.requires_review if classification is not None else False
                ),
                reasons=(
                    json.loads(classification.reasons_json) if classification is not None else []
                ),
                country_code=classification.country_code if classification is not None else None,
                country_name=classification.country_name if classification is not None else None,
                manual_override=(
                    classification is not None and classification.manual_routing_group is not None
                ),
                error_code=media.error_code,
                error_message=media.error_message,
                thumbnail_path=thumbnail_path,
            )
        )
    return rows


def _summarize(
    rows: list[ReportRow], thumbnail_results: dict[int, ThumbnailResult]
) -> ReportSummary:
    totals_by_group: dict[str, int] = {}
    totals_by_country: dict[str, int] = {}
    low_confidence_count = 0
    error_count = 0

    for row in rows:
        totals_by_group[row.routing_group] = totals_by_group.get(row.routing_group, 0) + 1
        if row.country_code:
            totals_by_country[row.country_code] = totals_by_country.get(row.country_code, 0) + 1
        if row.requires_review:
            low_confidence_count += 1
        if row.error_code is not None:
            error_count += 1

    thumbnails_generated = sum(1 for result in thumbnail_results.values() if result.success)
    thumbnails_failed = len(thumbnail_results) - thumbnails_generated

    return ReportSummary(
        total_files=len(rows),
        total_bytes=sum(row.size_bytes for row in rows),
        thumbnails_generated=thumbnails_generated,
        thumbnails_failed=thumbnails_failed,
        low_confidence_count=low_confidence_count,
        error_count=error_count,
        totals_by_group=totals_by_group,
        totals_by_country=totals_by_country,
    )


def _report_payload(
    scan: Scan, rows: list[ReportRow], summary: ReportSummary, generated_at: datetime
) -> dict[str, Any]:
    return {
        "generated_at": generated_at,
        "source_root": scan.source_root,
        "total_files": summary.total_files,
        "total_bytes": summary.total_bytes,
        "totals_by_group": summary.totals_by_group,
        "totals_by_country": summary.totals_by_country,
        "files": [dataclasses.asdict(row) for row in rows],
    }


def _write_report_json(
    path: Path, scan: Scan, rows: list[ReportRow], summary: ReportSummary, generated_at: datetime
) -> None:
    payload = _report_payload(scan, rows, summary, generated_at)
    path.write_text(
        json.dumps(payload, default=_json_default, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def build_report_payload(session: Session, scan_id: int) -> dict[str, Any]:
    """Build the same `report.json` payload shape without writing files or thumbnails.

    Used by the API's `GET /api/scans/{scan_id}/report` (roadmap Phase 19) — the
    CLI `report` command (Phase 13) still owns actually generating thumbnails
    and writing `report.html`/`.csv`/`errors.log` to disk.
    """
    scan = ScanRepository(session).get(scan_id)
    if scan is None:
        raise ValueError(f"No scan found for scan_id={scan_id}")

    media_files = list(MediaFileRepository(session).list_by_scan(scan_id))
    rows = _build_rows(session, media_files, {})
    summary = _summarize(rows, {})
    return _report_payload(scan, rows, summary, datetime.now(UTC))


def _write_report_csv(path: Path, rows: list[ReportRow]) -> None:
    fieldnames = [field_.name for field_ in dataclasses.fields(ReportRow)]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            record = dataclasses.asdict(row)
            record["reasons"] = "; ".join(record["reasons"])
            writer.writerow(record)


def _write_report_html(
    path: Path, scan: Scan, rows: list[ReportRow], summary: ReportSummary, generated_at: datetime
) -> None:
    environment = Environment(
        loader=FileSystemLoader(str(TEMPLATES_DIR)),
        autoescape=select_autoescape(["html"]),
    )
    template = environment.get_template("report.html.jinja")
    html = template.render(scan=scan, rows=rows, summary=summary, generated_at=generated_at)
    path.write_text(html, encoding="utf-8")


def generate_report(
    session: Session,
    scan_id: int,
    output_dir: Path,
    *,
    on_progress: Callable[[MediaFile, ThumbnailResult], None] | None = None,
) -> ReportSummary:
    """Generate `report.json`/`.csv`/`.html` + `errors.log` for `scan_id` into `output_dir`."""
    scan = ScanRepository(session).get(scan_id)
    if scan is None:
        raise ValueError(f"No scan found for scan_id={scan_id}")

    output_dir.mkdir(parents=True, exist_ok=True)
    thumbnails_dir = output_dir / "thumbnails"

    media_files = list(MediaFileRepository(session).list_by_scan(scan_id))
    thumbnail_results = generate_thumbnails_for_scan(
        session, scan_id, thumbnails_dir, on_progress=on_progress
    )
    rows = _build_rows(session, media_files, thumbnail_results)
    summary = _summarize(rows, thumbnail_results)
    generated_at = datetime.now(UTC)

    _write_report_json(output_dir / "report.json", scan, rows, summary, generated_at)
    _write_report_csv(output_dir / "report.csv", rows)
    _write_report_html(output_dir / "report.html", scan, rows, summary, generated_at)
    write_error_log(output_dir / "errors.log", media_files)

    return summary

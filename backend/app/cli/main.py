"""`media-organizer` CLI entry point.

`scan` (roadmap Phase 7, README §37/US-001) wires scan -> media-type
detection -> batch metadata extraction. `classify`/`override` (roadmap
Phase 12, README §38/US-002) wire the rule engine + country resolution
and record manual corrections. Neither ever writes to the scanned source
tree — only to `--output` (report artifacts) and the SQLite database.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

import typer

from backend.app.cli.scan_report import write_error_log, write_inventory_json
from backend.app.core.db import create_db_and_tables, get_database_path, get_engine, get_session
from backend.app.repositories.classification_repository import ClassificationRepository
from backend.app.repositories.media_file_repository import MediaFileRepository
from backend.app.rules.engine import ROUTING_GROUPS, ClassificationResult
from backend.app.services.classification import classify_scan
from backend.app.services.media_type import detect_media_types_for_scan
from backend.app.services.metadata import extract_metadata_for_scan
from backend.app.services.scanner import ScanProgress, scan_folder

if TYPE_CHECKING:
    from backend.app.models.media_file import MediaFile

app = typer.Typer(name="media-organizer", help="Local, offline media triage and organization.")


@app.callback()
def _main() -> None:
    """Local, offline media triage and organization.

    Kept as an explicit callback so Typer always exposes subcommands
    (e.g. `scan`) instead of collapsing to a single top-level command,
    which is Typer's default when only one `@app.command()` is registered.
    """


@app.command("scan")
def scan_command(
    path: Path = typer.Argument(
        ...,
        exists=True,
        file_okay=False,
        dir_okay=True,
        resolve_path=True,
        help="Local folder to scan.",
    ),
    recursive: bool = typer.Option(True, "--recursive/--no-recursive", help="Walk subfolders."),
    output: Path = typer.Option(
        ..., "--output", help="Directory for the error log and JSON inventory."
    ),
    database: Path | None = typer.Option(
        None, "--database", hidden=True, help="Override the SQLite database path (testing only)."
    ),
) -> None:
    """Scan PATH, detect media types, extract metadata, and export the inventory."""
    output.mkdir(parents=True, exist_ok=True)
    database_path = database if database is not None else get_database_path()
    engine = get_engine(database_path)
    create_db_and_tables(engine)

    with get_session(engine) as session:
        typer.echo(f"Scanning {path} (recursive={recursive})...")
        scan = scan_folder(
            session,
            path,
            recursive=recursive,
            on_progress=_report_scan_progress,
        )
        assert scan.id is not None

        typer.echo("Detecting media types...")
        detect_media_types_for_scan(
            session, scan.id, on_progress=lambda n: typer.echo(f"  detected {n} files")
        )

        typer.echo("Extracting metadata...")
        summary = extract_metadata_for_scan(
            session, scan.id, on_progress=lambda n: typer.echo(f"  processed {n} files")
        )

        rows = list(MediaFileRepository(session).list_by_scan(scan.id))

        error_count = write_error_log(output / "errors.log", rows)
        write_inventory_json(output / "inventory.json", session, rows)

    typer.echo(
        "Done. "
        f"files={scan.total_files} extracted={summary.extracted} "
        f"video_ok={summary.video_ok} video_unreadable={summary.video_unreadable} "
        f"errors={error_count}"
    )
    typer.echo(f"Inventory: {output / 'inventory.json'}")
    typer.echo(f"Error log: {output / 'errors.log'}")


def _report_scan_progress(progress: ScanProgress) -> None:
    typer.echo(f"  scanned {progress.processed_files} files")


@app.command("classify")
def classify_command(
    scan_id: int = typer.Option(..., "--scan-id", help="ID of an existing scan to classify."),
    database: Path | None = typer.Option(
        None, "--database", hidden=True, help="Override the SQLite database path (testing only)."
    ),
) -> None:
    """Classify a scan's files: routing group, confidence, and reasons (README §38)."""
    database_path = database if database is not None else get_database_path()
    engine = get_engine(database_path)
    create_db_and_tables(engine)

    with get_session(engine) as session:
        summary = classify_scan(session, scan_id, on_progress=_report_classification)

    typer.echo(
        "Done. "
        f"requires_review={summary.requires_review} skipped={summary.skipped} "
        f"by_group={summary.routing_group_counts}"
    )


def _report_classification(media: MediaFile, result: ClassificationResult) -> None:
    typer.echo(
        f"  {media.relative_path} -> {result.routing_group} "
        f"(confidence={result.confidence:.2f}, requires_review={result.requires_review}) "
        f"reasons: {result.reasons}"
    )


@app.command("override")
def override_command(
    media_file_id: int = typer.Argument(..., help="MediaFile ID to override."),
    routing_group: str = typer.Argument(..., help=f"One of: {', '.join(ROUTING_GROUPS)}."),
    database: Path | None = typer.Option(
        None, "--database", hidden=True, help="Override the SQLite database path (testing only)."
    ),
) -> None:
    """Manually set a file's effective routing group (README §15.3)."""
    if routing_group not in ROUTING_GROUPS:
        typer.echo(f"Invalid routing group {routing_group!r}. Must be one of: {ROUTING_GROUPS}")
        raise typer.Exit(code=1)

    database_path = database if database is not None else get_database_path()
    engine = get_engine(database_path)
    create_db_and_tables(engine)

    with get_session(engine) as session:
        repository = ClassificationRepository(session)
        classification = repository.get_by_media_file_id(media_file_id)
        if classification is None:
            typer.echo(
                f"No classification found for media_file_id={media_file_id}. Run `classify` first."
            )
            raise typer.Exit(code=1)

        classification.manual_routing_group = routing_group
        classification.effective_routing_group = routing_group
        classification.override_timestamp = datetime.now(UTC)
        repository.update(classification)

    typer.echo(f"Overrode media_file_id={media_file_id}: effective_routing_group={routing_group}")


if __name__ == "__main__":
    app()

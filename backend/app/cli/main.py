"""`media-organizer` CLI entry point — roadmap Phase 7, README §37 (US-001).

Wires the Phase 4-6 engine (scan -> media-type detection -> batch metadata
extraction) behind one command. Never writes to the scanned source tree —
only to `--output` (report artifacts) and the SQLite database.
"""

from __future__ import annotations

from pathlib import Path

import typer

from backend.app.cli.scan_report import write_error_log, write_inventory_json
from backend.app.core.db import create_db_and_tables, get_database_path, get_engine, get_session
from backend.app.repositories.media_file_repository import MediaFileRepository
from backend.app.services.media_type import detect_media_types_for_scan
from backend.app.services.metadata import extract_metadata_for_scan
from backend.app.services.scanner import ScanProgress, scan_folder

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


if __name__ == "__main__":
    app()

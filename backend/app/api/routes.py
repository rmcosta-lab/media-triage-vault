"""API routes — README §25, roadmap Phases 17-18.

The `GET` routes (Phase 17) only read data the CLI already produced, plus
on-demand thumbnail generation reusing Phase 13's `generate_thumbnail`.
The `POST /scans*` routes and `GET /jobs/*` (Phase 18) queue and observe
background scan/classify jobs via `services.job_runner` — the response
returns immediately with a `Job`; the work happens on a separate thread.
Plan/execute triggers are still Phase 19's job.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy import Engine
from sqlmodel import Session

from backend.app.api.deps import get_session_dependency, get_thumbnail_cache_dir_dependency
from backend.app.api.schemas import (
    ClassificationRead,
    JobRead,
    MediaFileRead,
    MediaMetadataRead,
    ScanCreateRequest,
    ScanRead,
)
from backend.app.repositories.classification_repository import ClassificationRepository
from backend.app.repositories.job_repository import JobRepository
from backend.app.repositories.media_file_repository import MediaFileRepository
from backend.app.repositories.media_metadata_repository import MediaMetadataRepository
from backend.app.repositories.scan_repository import ScanRepository
from backend.app.services.job_runner import submit_classify_job, submit_scan_job
from backend.app.services.thumbnails import generate_thumbnail

JOB_TERMINAL_STATUSES = ("completed", "failed", "cancelled")
_SSE_POLL_INTERVAL_SECONDS = 0.3

router = APIRouter()


@router.get("/scans/{scan_id}", response_model=ScanRead)
def get_scan(scan_id: int, session: Session = Depends(get_session_dependency)) -> ScanRead:
    scan = ScanRepository(session).get(scan_id)
    if scan is None:
        raise HTTPException(status_code=404, detail=f"No scan found for scan_id={scan_id}")
    return ScanRead.model_validate(scan)


@router.get("/scans/{scan_id}/files", response_model=list[MediaFileRead])
def list_scan_files(
    scan_id: int,
    skip: int = 0,
    limit: int = 200,
    session: Session = Depends(get_session_dependency),
) -> list[MediaFileRead]:
    scan = ScanRepository(session).get(scan_id)
    if scan is None:
        raise HTTPException(status_code=404, detail=f"No scan found for scan_id={scan_id}")

    files = list(MediaFileRepository(session).list_by_scan(scan_id))
    page = files[skip : skip + limit]
    return [MediaFileRead.model_validate(media_file) for media_file in page]


@router.get("/files/{file_id}/classification", response_model=ClassificationRead)
def get_file_classification(
    file_id: int, session: Session = Depends(get_session_dependency)
) -> ClassificationRead:
    media_file = MediaFileRepository(session).get(file_id)
    if media_file is None:
        raise HTTPException(status_code=404, detail=f"No file found for file_id={file_id}")

    classification = ClassificationRepository(session).get_by_media_file_id(file_id)
    if classification is None:
        raise HTTPException(
            status_code=404, detail=f"No classification found for file_id={file_id}"
        )
    return ClassificationRead.model_validate(classification)


@router.get("/files/{file_id}/metadata", response_model=MediaMetadataRead)
def get_file_metadata(
    file_id: int, session: Session = Depends(get_session_dependency)
) -> MediaMetadataRead:
    media_file = MediaFileRepository(session).get(file_id)
    if media_file is None:
        raise HTTPException(status_code=404, detail=f"No file found for file_id={file_id}")

    media_metadata = MediaMetadataRepository(session).get_by_media_file_id(file_id)
    if media_metadata is None:
        raise HTTPException(status_code=404, detail=f"No metadata found for file_id={file_id}")
    return MediaMetadataRead.model_validate(media_metadata)


@router.get("/files/{file_id}/thumbnail")
def get_file_thumbnail(
    file_id: int,
    session: Session = Depends(get_session_dependency),
    cache_dir: Path = Depends(get_thumbnail_cache_dir_dependency),
) -> FileResponse:
    media_file = MediaFileRepository(session).get(file_id)
    if media_file is None:
        raise HTTPException(status_code=404, detail=f"No file found for file_id={file_id}")

    destination = cache_dir / f"{file_id}.jpg"

    if not destination.exists():
        result = generate_thumbnail(media_file, destination)
        if not result.success:
            raise HTTPException(
                status_code=422,
                detail=f"Could not generate thumbnail: {result.error_code} — "
                f"{result.error_message}",
            )

    return FileResponse(destination, media_type="image/jpeg")


@router.post("/scans", response_model=JobRead, status_code=202)
def create_scan(
    request: ScanCreateRequest, session: Session = Depends(get_session_dependency)
) -> JobRead:
    """Queue a background scan job (README §26). Returns immediately with the job."""
    source_path = Path(request.source_root)
    if not source_path.is_dir():
        raise HTTPException(
            status_code=400, detail=f"{request.source_root} does not exist or is not a directory"
        )

    job = submit_scan_job(session, request.source_root, request.recursive)
    return JobRead.model_validate(job)


@router.post("/scans/{scan_id}/classify", response_model=JobRead, status_code=202)
def create_classify_job(
    scan_id: int, session: Session = Depends(get_session_dependency)
) -> JobRead:
    """Queue a background classify job against an existing scan."""
    scan = ScanRepository(session).get(scan_id)
    if scan is None:
        raise HTTPException(status_code=404, detail=f"No scan found for scan_id={scan_id}")

    job = submit_classify_job(session, scan_id)
    return JobRead.model_validate(job)


@router.post("/scans/{scan_id}/cancel", response_model=JobRead)
def cancel_scan_job(scan_id: int, session: Session = Depends(get_session_dependency)) -> JobRead:
    """Request cancellation of the active job for `scan_id` (honored between files/batches)."""
    active_jobs = JobRepository(session).list_active_for_scan(scan_id)
    if not active_jobs:
        raise HTTPException(status_code=404, detail=f"No active job found for scan_id={scan_id}")

    job = active_jobs[0]
    job.cancel_requested = True
    JobRepository(session).update(job)
    return JobRead.model_validate(job)


@router.get("/jobs/{job_id}", response_model=JobRead)
def get_job(job_id: int, session: Session = Depends(get_session_dependency)) -> JobRead:
    job = JobRepository(session).get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"No job found for job_id={job_id}")
    return JobRead.model_validate(job)


@router.get("/jobs/{job_id}/events")
async def stream_job_events(
    job_id: int, session: Session = Depends(get_session_dependency)
) -> StreamingResponse:
    """Server-Sent Events stream of `job_id`'s progress until it reaches a terminal state."""
    job = JobRepository(session).get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"No job found for job_id={job_id}")

    # Reuse the already-injected session's engine (respects test dependency
    # overrides) rather than reopening the real default database.
    engine = session.get_bind()
    assert isinstance(engine, Engine)

    async def event_stream() -> AsyncIterator[str]:
        last_payload: str | None = None
        while True:
            with Session(engine) as poll_session:
                current = JobRepository(poll_session).get(job_id)
                if current is None:
                    break
                payload = json.dumps(JobRead.model_validate(current).model_dump(mode="json"))
                if payload != last_payload:
                    yield f"data: {payload}\n\n"
                    last_payload = payload
                if current.status in JOB_TERMINAL_STATUSES:
                    break
            await asyncio.sleep(_SSE_POLL_INTERVAL_SECONDS)

    return StreamingResponse(event_stream(), media_type="text/event-stream")

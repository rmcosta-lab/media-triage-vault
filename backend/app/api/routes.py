"""API routes — README §25, roadmap Phases 17-19.

The `GET` routes (Phase 17) only read data the CLI already produced, plus
on-demand thumbnail generation reusing Phase 13's `generate_thumbnail`.
The `POST /scans*` routes and `GET /jobs/*` (Phase 18) queue and observe
background scan/classify jobs via `services.job_runner` — the response
returns immediately with a `Job`; the work happens on a separate thread.
The destinations/move-plan/execute routes (Phase 19) close the loop:
`PUT .../destinations` and `POST .../move-plan` run synchronously (same
cost as the CLI's `destinations`/`plan` commands); `POST
/move-plans/{id}/execute` queues another background job (job_type=
"execute") whose `id` doubles as README §25's "move run" id.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy import Engine
from sqlmodel import Session

from backend.app.api.deps import get_session_dependency, get_thumbnail_cache_dir_dependency
from backend.app.api.schemas import (
    ClassificationOverrideRequest,
    ClassificationRead,
    DestinationConfigRequest,
    DestinationRuleRead,
    JobRead,
    MediaFileRead,
    MediaMetadataRead,
    MoveOperationRead,
    MovePlanCreateRequest,
    MovePlanRead,
    ScanCreateRequest,
    ScanRead,
)
from backend.app.models.job import Job
from backend.app.models.move_plan import MovePlan
from backend.app.repositories.classification_repository import ClassificationRepository
from backend.app.repositories.job_repository import JobRepository
from backend.app.repositories.media_file_repository import MediaFileRepository
from backend.app.repositories.media_metadata_repository import MediaMetadataRepository
from backend.app.repositories.move_operation_repository import MoveOperationRepository
from backend.app.repositories.move_plan_repository import MovePlanRepository
from backend.app.repositories.scan_repository import ScanRepository
from backend.app.rules.engine import ROUTING_GROUPS
from backend.app.services.destinations import DestinationConfig, set_destination_rules
from backend.app.services.job_runner import (
    submit_classify_job,
    submit_execute_job,
    submit_scan_job,
)
from backend.app.services.move_plan import generate_move_plan
from backend.app.services.move_report import build_move_report_payload
from backend.app.services.reports import build_report_payload
from backend.app.services.thumbnails import generate_thumbnail

JOB_TERMINAL_STATUSES = ("completed", "failed", "cancelled")
_SSE_POLL_INTERVAL_SECONDS = 0.3

router = APIRouter()


def _build_move_plan_read(session: Session, move_plan: MovePlan) -> MovePlanRead:
    assert move_plan.id is not None
    operations = list(MoveOperationRepository(session).list_by_plan(move_plan.id))
    total_planned = sum(1 for op in operations if op.status == "planned")
    total_blocked = sum(1 for op in operations if op.status == "blocked")
    total_bytes_planned = sum(op.source_size for op in operations if op.status == "planned")
    by_error_code: dict[str, int] = {}
    for op in operations:
        if op.status == "blocked" and op.error_code is not None:
            by_error_code[op.error_code] = by_error_code.get(op.error_code, 0) + 1

    return MovePlanRead(
        id=move_plan.id,
        scan_id=move_plan.scan_id,
        status=move_plan.status,
        collision_policy=move_plan.collision_policy,
        validation_mode=move_plan.validation_mode,
        created_at=move_plan.created_at,
        approved_at=move_plan.approved_at,
        total_planned=total_planned,
        total_blocked=total_blocked,
        total_bytes_planned=total_bytes_planned,
        by_error_code=by_error_code,
        operations=[MoveOperationRead.model_validate(op) for op in operations],
    )


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


@router.patch("/files/{file_id}/classification", response_model=ClassificationRead)
def override_file_classification(
    file_id: int,
    request: ClassificationOverrideRequest,
    session: Session = Depends(get_session_dependency),
) -> ClassificationRead:
    """Manually set a file's effective routing group (README §15.3)."""
    if request.routing_group not in ROUTING_GROUPS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid routing group {request.routing_group!r}. "
            f"Must be one of: {ROUTING_GROUPS}",
        )

    repository = ClassificationRepository(session)
    classification = repository.get_by_media_file_id(file_id)
    if classification is None:
        raise HTTPException(
            status_code=404,
            detail=f"No classification found for file_id={file_id}. Run classify first.",
        )

    classification.manual_routing_group = request.routing_group
    classification.effective_routing_group = request.routing_group
    classification.override_timestamp = datetime.now(UTC)
    repository.update(classification)
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


@router.put("/scans/{scan_id}/destinations", response_model=list[DestinationRuleRead])
def put_scan_destinations(
    scan_id: int,
    mapping: dict[str, DestinationConfigRequest],
    session: Session = Depends(get_session_dependency),
) -> list[DestinationRuleRead]:
    """Map each routing group to a destination folder (README §39, US-003)."""
    scan = ScanRepository(session).get(scan_id)
    if scan is None:
        raise HTTPException(status_code=404, detail=f"No scan found for scan_id={scan_id}")

    config = {
        routing_group: DestinationConfig(
            destination_root=entry.destination_root,
            country_subfolder_enabled=entry.country_subfolder_enabled,
        )
        for routing_group, entry in mapping.items()
    }
    try:
        rules = set_destination_rules(session, scan_id, config)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    return [DestinationRuleRead.model_validate(rule) for rule in rules]


@router.post("/scans/{scan_id}/move-plan", response_model=MovePlanRead, status_code=201)
def create_move_plan(
    scan_id: int,
    request: MovePlanCreateRequest,
    session: Session = Depends(get_session_dependency),
) -> MovePlanRead:
    """Generate a dry-run move plan (README §16 Etapa 5, US-003). Nothing is executed."""
    scan = ScanRepository(session).get(scan_id)
    if scan is None:
        raise HTTPException(status_code=404, detail=f"No scan found for scan_id={scan_id}")

    try:
        generate_move_plan(
            session,
            scan_id,
            collision_policy=request.collision_policy,
            validation_mode=request.validation_mode,
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    move_plan = MovePlanRepository(session).get_latest_for_scan(scan_id)
    assert move_plan is not None
    return _build_move_plan_read(session, move_plan)


@router.get("/move-plans/{plan_id}", response_model=MovePlanRead)
def get_move_plan(plan_id: int, session: Session = Depends(get_session_dependency)) -> MovePlanRead:
    move_plan = MovePlanRepository(session).get(plan_id)
    if move_plan is None:
        raise HTTPException(status_code=404, detail=f"No move plan found for plan_id={plan_id}")
    return _build_move_plan_read(session, move_plan)


@router.post("/move-plans/{plan_id}/approve", response_model=MovePlanRead)
def approve_move_plan(
    plan_id: int, session: Session = Depends(get_session_dependency)
) -> MovePlanRead:
    """Explicit confirmation step (README §16 Etapa 6) before `execute` will run this plan."""
    move_plan_repository = MovePlanRepository(session)
    move_plan = move_plan_repository.get(plan_id)
    if move_plan is None:
        raise HTTPException(status_code=404, detail=f"No move plan found for plan_id={plan_id}")

    move_plan.approved_at = datetime.now(UTC)
    move_plan_repository.update(move_plan)
    return _build_move_plan_read(session, move_plan)


@router.post("/move-plans/{plan_id}/execute", response_model=JobRead, status_code=202)
def execute_move_plan_route(
    plan_id: int, session: Session = Depends(get_session_dependency)
) -> JobRead:
    """Queue execution of an approved move plan. The returned `Job.id` is the move-run id."""
    move_plan = MovePlanRepository(session).get(plan_id)
    if move_plan is None:
        raise HTTPException(status_code=404, detail=f"No move plan found for plan_id={plan_id}")
    if move_plan.approved_at is None:
        raise HTTPException(status_code=400, detail="Plan must be approved before execution")

    job = submit_execute_job(session, plan_id)
    return JobRead.model_validate(job)


@router.get("/move-runs/{run_id}", response_model=JobRead)
def get_move_run(run_id: int, session: Session = Depends(get_session_dependency)) -> JobRead:
    job = _get_execute_job_or_404(session, run_id)
    return JobRead.model_validate(job)


@router.post("/move-runs/{run_id}/cancel", response_model=JobRead)
def cancel_move_run(run_id: int, session: Session = Depends(get_session_dependency)) -> JobRead:
    repository = JobRepository(session)
    job = _get_execute_job_or_404(session, run_id)
    job.cancel_requested = True
    repository.update(job)
    return JobRead.model_validate(job)


@router.get("/move-runs/{run_id}/report")
def get_move_run_report(
    run_id: int, session: Session = Depends(get_session_dependency)
) -> dict[str, Any]:
    job = _get_execute_job_or_404(session, run_id)
    assert job.move_plan_id is not None

    elapsed_seconds = 0.0
    if job.started_at is not None and job.finished_at is not None:
        elapsed_seconds = (job.finished_at - job.started_at).total_seconds()

    try:
        return build_move_report_payload(session, job.move_plan_id, elapsed_seconds)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@router.get("/scans/{scan_id}/report")
def get_scan_report(
    scan_id: int, session: Session = Depends(get_session_dependency)
) -> dict[str, Any]:
    try:
        return build_report_payload(session, scan_id)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


def _get_execute_job_or_404(session: Session, run_id: int) -> Job:
    job = JobRepository(session).get(run_id)
    if job is None or job.job_type != "execute":
        raise HTTPException(status_code=404, detail=f"No move run found for run_id={run_id}")
    return job

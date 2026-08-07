"""Read-only API routes — README §25, roadmap Phase 17.

Every route here only reads data the CLI already produced (`scan`,
`classify`, and on-demand thumbnail generation reusing Phase 13's
`generate_thumbnail`) — no scan/classify/plan/execute trigger exists
yet (Phase 18's job runner, Phase 19's write endpoints).
"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlmodel import Session

from backend.app.api.deps import get_session_dependency, get_thumbnail_cache_dir_dependency
from backend.app.api.schemas import (
    ClassificationRead,
    MediaFileRead,
    MediaMetadataRead,
    ScanRead,
)
from backend.app.repositories.classification_repository import ClassificationRepository
from backend.app.repositories.media_file_repository import MediaFileRepository
from backend.app.repositories.media_metadata_repository import MediaMetadataRepository
from backend.app.repositories.scan_repository import ScanRepository
from backend.app.services.thumbnails import generate_thumbnail

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

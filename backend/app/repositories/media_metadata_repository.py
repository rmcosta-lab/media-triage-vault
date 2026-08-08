from __future__ import annotations

from collections.abc import Sequence

from sqlmodel import Session, select

from backend.app.models.media_file import MediaFile
from backend.app.models.media_metadata import MediaMetadata
from backend.app.repositories.base import Repository


class MediaMetadataRepository(Repository[MediaMetadata]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, MediaMetadata)

    def get_by_media_file_id(self, media_file_id: int) -> MediaMetadata | None:
        statement = select(MediaMetadata).where(MediaMetadata.media_file_id == media_file_id)
        return self._session.exec(statement).first()

    def list_by_media_file_ids(self, media_file_ids: Sequence[int]) -> Sequence[MediaMetadata]:
        if not media_file_ids:
            return []
        statement = select(MediaMetadata).where(
            MediaMetadata.media_file_id.in_(media_file_ids)  # type: ignore[attr-defined]
        )
        return self._session.exec(statement).all()

    def list_by_scan(self, scan_id: int) -> Sequence[MediaMetadata]:
        """Load a scan without an SQLite-variable-sized ``IN`` clause."""
        statement = select(MediaMetadata).join(MediaFile).where(MediaFile.scan_id == scan_id)
        return self._session.exec(statement).all()

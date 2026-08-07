from __future__ import annotations

from sqlmodel import Session, select

from backend.app.models.media_metadata import MediaMetadata
from backend.app.repositories.base import Repository


class MediaMetadataRepository(Repository[MediaMetadata]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, MediaMetadata)

    def get_by_media_file_id(self, media_file_id: int) -> MediaMetadata | None:
        statement = select(MediaMetadata).where(MediaMetadata.media_file_id == media_file_id)
        return self._session.exec(statement).first()

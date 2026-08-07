from __future__ import annotations

from collections.abc import Sequence

from sqlmodel import Session, select

from backend.app.models.media_file import MediaFile
from backend.app.repositories.base import Repository


class MediaFileRepository(Repository[MediaFile]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, MediaFile)

    def list_by_scan(self, scan_id: int) -> Sequence[MediaFile]:
        statement = select(MediaFile).where(MediaFile.scan_id == scan_id)
        return self._session.exec(statement).all()

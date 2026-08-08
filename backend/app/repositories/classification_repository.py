from __future__ import annotations

from collections.abc import Sequence

from sqlmodel import Session, select

from backend.app.models.classification import Classification
from backend.app.models.media_file import MediaFile
from backend.app.repositories.base import Repository


class ClassificationRepository(Repository[Classification]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, Classification)

    def get_by_media_file_id(self, media_file_id: int) -> Classification | None:
        statement = select(Classification).where(Classification.media_file_id == media_file_id)
        return self._session.exec(statement).first()

    def list_by_media_file_ids(self, media_file_ids: Sequence[int]) -> Sequence[Classification]:
        if not media_file_ids:
            return []
        statement = select(Classification).where(
            Classification.media_file_id.in_(media_file_ids)  # type: ignore[attr-defined]
        )
        return self._session.exec(statement).all()

    def list_by_scan(self, scan_id: int) -> Sequence[Classification]:
        """Load a scan without an SQLite-variable-sized ``IN`` clause."""
        statement = select(Classification).join(MediaFile).where(MediaFile.scan_id == scan_id)
        return self._session.exec(statement).all()

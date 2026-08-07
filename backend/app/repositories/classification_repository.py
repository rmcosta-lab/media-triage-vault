from __future__ import annotations

from sqlmodel import Session, select

from backend.app.models.classification import Classification
from backend.app.repositories.base import Repository


class ClassificationRepository(Repository[Classification]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, Classification)

    def get_by_media_file_id(self, media_file_id: int) -> Classification | None:
        statement = select(Classification).where(Classification.media_file_id == media_file_id)
        return self._session.exec(statement).first()

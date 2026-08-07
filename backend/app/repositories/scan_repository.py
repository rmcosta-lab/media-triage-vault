from __future__ import annotations

from sqlmodel import Session

from backend.app.models.scan import Scan
from backend.app.repositories.base import Repository


class ScanRepository(Repository[Scan]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, Scan)

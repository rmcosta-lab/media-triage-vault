from __future__ import annotations

from collections.abc import Sequence

from sqlmodel import Session, select

from backend.app.models.job import Job
from backend.app.repositories.base import Repository


class JobRepository(Repository[Job]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, Job)

    def list_active_for_scan(self, scan_id: int) -> Sequence[Job]:
        statement = (
            select(Job).where(Job.scan_id == scan_id).where(Job.status.in_(("queued", "running")))  # type: ignore[attr-defined]
        )
        return self._session.exec(statement).all()

    def list_active_for_move_plan(self, move_plan_id: int) -> Sequence[Job]:
        statement = (
            select(Job)
            .where(Job.move_plan_id == move_plan_id)
            .where(Job.status.in_(("queued", "running")))  # type: ignore[attr-defined]
        )
        return self._session.exec(statement).all()

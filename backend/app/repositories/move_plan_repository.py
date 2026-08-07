from __future__ import annotations

from sqlmodel import Session, select

from backend.app.models.move_plan import MovePlan
from backend.app.repositories.base import Repository


class MovePlanRepository(Repository[MovePlan]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, MovePlan)

    def get_latest_for_scan(self, scan_id: int) -> MovePlan | None:
        statement = (
            select(MovePlan).where(MovePlan.scan_id == scan_id).order_by(MovePlan.created_at.desc())  # type: ignore[attr-defined]
        )
        return self._session.exec(statement).first()

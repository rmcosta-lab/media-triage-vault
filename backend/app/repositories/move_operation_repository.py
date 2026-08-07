from __future__ import annotations

from collections.abc import Sequence

from sqlmodel import Session, select

from backend.app.models.move_plan import MoveOperation
from backend.app.repositories.base import Repository


class MoveOperationRepository(Repository[MoveOperation]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, MoveOperation)

    def list_by_plan(self, move_plan_id: int) -> Sequence[MoveOperation]:
        statement = select(MoveOperation).where(MoveOperation.move_plan_id == move_plan_id)
        return self._session.exec(statement).all()

    def bulk_create(self, operations: list[MoveOperation]) -> None:
        for operation in operations:
            self._session.add(operation)
        self._session.commit()

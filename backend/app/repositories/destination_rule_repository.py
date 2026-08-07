from __future__ import annotations

from collections.abc import Sequence

from sqlmodel import Session, select

from backend.app.models.destination_rule import DestinationRule
from backend.app.repositories.base import Repository


class DestinationRuleRepository(Repository[DestinationRule]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, DestinationRule)

    def list_by_scan(self, scan_id: int) -> Sequence[DestinationRule]:
        statement = select(DestinationRule).where(DestinationRule.scan_id == scan_id)
        return self._session.exec(statement).all()

    def replace_for_scan(self, scan_id: int, rules: list[DestinationRule]) -> None:
        for existing in self.list_by_scan(scan_id):
            self._session.delete(existing)
        # Flush the deletes before adding the replacement rows: SQLAlchemy's default
        # flush order runs inserts before deletes, which would otherwise trip the
        # (scan_id, routing_group) unique constraint against the row being replaced.
        self._session.flush()
        for rule in rules:
            self._session.add(rule)
        self._session.commit()

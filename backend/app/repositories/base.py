"""Generic CRUD repository over a SQLModel table."""

from __future__ import annotations

from collections.abc import Sequence

from sqlmodel import Session, SQLModel, select


class Repository[T: SQLModel]:
    def __init__(self, session: Session, model: type[T]) -> None:
        self._session = session
        self._model = model

    def create(self, obj: T) -> T:
        self._session.add(obj)
        self._session.commit()
        self._session.refresh(obj)
        return obj

    def get(self, id_: int) -> T | None:
        return self._session.get(self._model, id_)

    def list(self) -> Sequence[T]:
        return self._session.exec(select(self._model)).all()

    def update(self, obj: T) -> T:
        self._session.add(obj)
        self._session.commit()
        self._session.refresh(obj)
        return obj

    def delete(self, id_: int) -> None:
        obj = self.get(id_)
        if obj is not None:
            self._session.delete(obj)
            self._session.commit()

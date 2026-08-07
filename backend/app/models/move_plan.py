"""``MovePlan`` and ``MoveOperation`` tables — README §24.5/§24.6 (= §18
diário transacional), roadmap Phases 14-15.

`MoveOperation` is the transactional journal in full. Phase 14 (planning)
only ever writes `status in {"planned", "blocked"}`; Phase 15's executor
(`services/move_executor.py`) drives a `"planned"` row through the
execution states (`validating`/`copying`/`verifying`/`renaming`/
`deleting_source`/`completed`/`failed`/`skipped`/`cancelled`). The table
was created in Phase 14 so the executor extends the same rows the planner
wrote rather than duplicating them.
"""

from datetime import UTC, datetime

from sqlmodel import Field, Relationship, SQLModel

MOVE_PLAN_STATUSES = ("draft", "generated")
MOVE_OPERATION_STATUSES = (
    "planned",
    "blocked",
    "validating",
    "copying",
    "verifying",
    "renaming",
    "deleting_source",
    "completed",
    "failed",
    "skipped",
    "cancelled",
)


class MovePlan(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    scan_id: int = Field(foreign_key="scan.id")
    status: str = "draft"
    collision_policy: str = "error"
    validation_mode: str = "standard"
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    approved_at: datetime | None = None

    operations: list["MoveOperation"] = Relationship(back_populates="move_plan")


class MoveOperation(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    move_plan_id: int = Field(foreign_key="moveplan.id")
    scan_id: int
    media_file_id: int = Field(foreign_key="mediafile.id")
    source_path: str
    planned_destination_path: str
    actual_destination_path: str | None = None
    source_size: int
    source_hash: str | None = None
    destination_size: int | None = None
    destination_hash: str | None = None
    status: str
    started_at: datetime | None = None
    finished_at: datetime | None = None
    error_code: str | None = None
    error_message: str | None = None

    move_plan: "MovePlan" = Relationship(back_populates="operations")

"""``Job`` table — background job runner state, README §26, roadmap Phase 18.

Every scan/classify job triggered through the API is one row here.
`cancel_requested` is the external "please stop" signal (set by `POST
/api/scans/{scan_id}/cancel`); `status` only becomes `"cancelled"` once
the worker thread has actually honored it between files/batches — never
mid-file.
"""

from datetime import UTC, datetime

from sqlmodel import Field, SQLModel

JOB_TYPES = ("scan", "classify")
JOB_STATUSES = ("queued", "running", "completed", "failed", "cancelled")


class Job(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    job_type: str
    scan_id: int | None = None
    status: str = "queued"
    params_json: str = "{}"
    cancel_requested: bool = False
    total: int = 0
    processed: int = 0
    message: str | None = None
    error_code: str | None = None
    error_message: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    started_at: datetime | None = None
    finished_at: datetime | None = None

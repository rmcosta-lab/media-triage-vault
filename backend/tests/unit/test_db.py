import time
from pathlib import Path

from sqlmodel import Session

from backend.app.core.db import create_db_and_tables, get_engine
from backend.app.models.job import Job
from backend.app.repositories.job_repository import JobRepository


def test_get_engine_enables_wal_and_busy_timeout(tmp_path: Path) -> None:
    engine = get_engine(tmp_path / "test.db")

    with engine.connect() as connection:
        journal_mode = connection.exec_driver_sql("PRAGMA journal_mode").scalar_one()
        busy_timeout = connection.exec_driver_sql("PRAGMA busy_timeout").scalar_one()

    assert journal_mode == "wal"
    assert busy_timeout == 30_000


def test_wal_reader_remains_available_during_uncommitted_write(tmp_path: Path) -> None:
    engine = get_engine(tmp_path / "test.db")
    create_db_and_tables(engine)
    with Session(engine) as session:
        job = JobRepository(session).create(Job(job_type="scan", status="queued"))
        assert job.id is not None
        job_id = job.id

    with engine.connect() as writer, engine.connect() as reader:
        writer.exec_driver_sql("BEGIN EXCLUSIVE")
        writer.exec_driver_sql(
            "UPDATE job SET status = 'running' WHERE id = ?",
            (job_id,),
        )

        started = time.monotonic()
        visible_status = reader.exec_driver_sql(
            "SELECT status FROM job WHERE id = ?",
            (job_id,),
        ).scalar_one()
        elapsed = time.monotonic() - started
        writer.rollback()

    assert visible_status == "queued"
    assert elapsed < 0.5

"""Unit tests for the destination-mapping service — README §16 Etapa 4, roadmap Phase 14."""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import Engine
from sqlmodel import Session

from backend.app.core.db import create_db_and_tables, get_engine, get_session
from backend.app.models.scan import Scan
from backend.app.repositories.destination_rule_repository import DestinationRuleRepository
from backend.app.repositories.scan_repository import ScanRepository
from backend.app.services.destinations import DestinationConfig, set_destination_rules


@pytest.fixture
def engine(tmp_path: Path) -> Engine:
    engine = get_engine(tmp_path / "test.db")
    create_db_and_tables(engine)
    return engine


def _make_scan(session: Session) -> int:
    scan = ScanRepository(session).create(
        Scan(source_root="D:/Fotos", recursive=True, status="pending")
    )
    assert scan.id is not None
    return scan.id


def test_set_destination_rules_creates_one_rule_per_group(engine: Engine) -> None:
    with get_session(engine) as session:
        scan_id = _make_scan(session)

        rules = set_destination_rules(
            session,
            scan_id,
            {
                "video": DestinationConfig(destination_root="D:/Midia/Videos"),
                "iphone_photo": DestinationConfig(
                    destination_root="D:/Midia/iPhone", country_subfolder_enabled=True
                ),
            },
        )

        assert {rule.routing_group for rule in rules} == {"video", "iphone_photo"}
        stored = DestinationRuleRepository(session).list_by_scan(scan_id)
        assert len(stored) == 2
        iphone_rule = next(r for r in stored if r.routing_group == "iphone_photo")
        assert iphone_rule.country_subfolder_enabled is True
        assert iphone_rule.enabled is True


def test_set_destination_rules_rejects_unknown_routing_group(engine: Engine) -> None:
    with get_session(engine) as session:
        scan_id = _make_scan(session)

        with pytest.raises(ValueError, match="not_a_group"):
            set_destination_rules(
                session,
                scan_id,
                {"not_a_group": DestinationConfig(destination_root="D:/Midia/Whatever")},
            )


def test_set_destination_rules_replaces_not_duplicates(engine: Engine) -> None:
    with get_session(engine) as session:
        scan_id = _make_scan(session)

        set_destination_rules(
            session, scan_id, {"video": DestinationConfig(destination_root="D:/Midia/Videos")}
        )
        set_destination_rules(
            session,
            scan_id,
            {"video": DestinationConfig(destination_root="D:/Midia/VideosRenamed")},
        )

        stored = DestinationRuleRepository(session).list_by_scan(scan_id)
        assert len(stored) == 1
        assert stored[0].destination_root == "D:/Midia/VideosRenamed"

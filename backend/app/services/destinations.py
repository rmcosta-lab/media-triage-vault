"""Destination-mapping service — README §16 Etapa 4, roadmap Phase 14.

Lets the user map each `routing_group` to a destination folder for a
scan. Replaces the whole mapping on every call rather than accumulating
partial updates, so a second `destinations` run always reflects exactly
what was passed in.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlmodel import Session

from backend.app.models.destination_rule import DestinationRule
from backend.app.repositories.destination_rule_repository import DestinationRuleRepository
from backend.app.rules.engine import ROUTING_GROUPS


@dataclass(frozen=True)
class DestinationConfig:
    destination_root: str
    country_subfolder_enabled: bool = False


def set_destination_rules(
    session: Session, scan_id: int, mapping: dict[str, DestinationConfig]
) -> list[DestinationRule]:
    """Replace `scan_id`'s destination mapping with `mapping`.

    Raises `ValueError` if a key isn't a valid routing group.
    """
    unknown = sorted(set(mapping) - set(ROUTING_GROUPS))
    if unknown:
        raise ValueError(f"Unknown routing group(s) {unknown}. Must be one of: {ROUTING_GROUPS}")

    rules = [
        DestinationRule(
            scan_id=scan_id,
            routing_group=routing_group,
            destination_root=config.destination_root,
            country_subfolder_enabled=config.country_subfolder_enabled,
            enabled=True,
        )
        for routing_group, config in mapping.items()
    ]

    repository = DestinationRuleRepository(session)
    repository.replace_for_scan(scan_id, rules)
    return rules

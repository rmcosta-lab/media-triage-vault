"""``DestinationRule`` table — README §24.4, roadmap Phase 14.

Maps one `routing_group` to a destination folder for a given scan (README
§16 Etapa 4). At most one rule per `(scan_id, routing_group)` pair —
`services/destinations.py` replaces the whole set on every call rather
than accumulating duplicates.
"""

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, SQLModel


class DestinationRule(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("scan_id", "routing_group"),)

    id: int | None = Field(default=None, primary_key=True)
    scan_id: int = Field(foreign_key="scan.id")
    routing_group: str
    destination_root: str
    country_subfolder_enabled: bool = False
    enabled: bool = True

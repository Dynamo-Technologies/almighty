"""Shared doctrine + Cumberland River geography for the blue crew.

Constants, named coordinates, and short doctrinal notes used across the
six agents' goals and backstories. Public, unclassified references only:

  - FM 3-21.20 — The Infantry Battalion (US Army field manual).
  - ATP 3-90.5 — Combined Arms Battalion.
  - ATP 2-01.3 — Intelligence Preparation of the Battlefield.

No specific real-world weapon system is named.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

# ---- Cumberland River anchor (per docs/architecture.md notional theater) -----

NASHVILLE_LAT_DEG: Final[float] = 36.18
NASHVILLE_LON_DEG: Final[float] = -86.78


@dataclass(frozen=True)
class NamedPoint:
    name: str
    lat_deg: float
    lon_deg: float
    alt_m: float


# West-bank defensive positions. v1 uses notional but plausible offsets
# from the river anchor. Not surveyed; do not use for actual operations.
WEST_BANK_BN_HQ = NamedPoint(
    name="BLUE-BN-HQ-1", lat_deg=36.1750, lon_deg=-86.7900, alt_m=170.0
)
WEST_BANK_OBSERVATION_POST = NamedPoint(
    name="BLUE-OP-1", lat_deg=36.1820, lon_deg=-86.7860, alt_m=185.0
)
COMPANY_A_POSITION = NamedPoint(
    name="BLUE-CO-A-1", lat_deg=36.1700, lon_deg=-86.7950, alt_m=170.0
)
COMPANY_B_POSITION = NamedPoint(
    name="BLUE-CO-B-1", lat_deg=36.1780, lon_deg=-86.7900, alt_m=172.0
)
COMPANY_C_POSITION = NamedPoint(
    name="BLUE-CO-C-1", lat_deg=36.1860, lon_deg=-86.7860, alt_m=175.0
)
EAST_BANK_NAMED_AREA_OF_INTEREST = NamedPoint(
    name="NAI-EAST-CROSSING", lat_deg=36.1810, lon_deg=-86.7720, alt_m=160.0
)

# ---- Doctrinal flavor strings ----

THEATER_BACKGROUND: Final[str] = (
    "You are part of a US BCT battalion holding the west bank of the "
    "Cumberland River north of Nashville. The notional opposing force "
    "(red) is expected to attempt a forced crossing in the next several "
    "turns. Your battalion's task is to detect the attempt early, "
    "shape the engagement zone with indirect fires, and deny use of "
    "the crossing. Civilian infrastructure on both banks is in scope; "
    "non-combatant safety is a hard constraint adjudicated by the "
    "white cell."
)

PUBLIC_DOCTRINE_REFERENCES: Final[str] = (
    "Operate within the public doctrine of FM 3-21.20 (Infantry "
    "Battalion), ATP 3-90.5 (Combined Arms Battalion), and ATP 2-01.3 "
    "(Intelligence Preparation of the Battlefield). Do not invent or "
    "name specific real-world weapon systems."
)

"""Loader for the us-bct.json capability profile (WS-107).

Self-contained so the crew can stand up without any caller-supplied
profile fixture. The profile file lives at the canonical repo path; we
resolve relative to this module's location.
"""

from __future__ import annotations

import json
from functools import cache
from pathlib import Path
from typing import Any

# agents/blue/src/almighty_blue_crew/profile.py -> repo root
_REPO_ROOT = Path(__file__).resolve().parents[4]
_US_BCT_PATH = _REPO_ROOT / "kernel" / "capability-profiles" / "us-bct.json"


@cache
def load_us_bct_profile() -> dict[str, Any]:
    """Return the us-bct.json capability profile as a dict.

    Cached at process scope; the profile is immutable per WS-106 § 5.
    """
    with _US_BCT_PATH.open() as f:
        return json.load(f)

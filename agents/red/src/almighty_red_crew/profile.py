"""Per-doctrine capability profile loader.

The three red doctrine flavors map to one capability profile each:

  peer       -> kernel/capability-profiles/peer.json
  near-peer  -> kernel/capability-profiles/near-peer.json
  hybrid     -> kernel/capability-profiles/hybrid-irregular.json
"""

from __future__ import annotations

import json
from functools import cache
from pathlib import Path
from typing import Any

from .doctrine import Doctrine

# agents/red/src/almighty_red_crew/profile.py -> repo root
_REPO_ROOT = Path(__file__).resolve().parents[4]
_PROFILES_DIR = _REPO_ROOT / "kernel" / "capability-profiles"

_FILENAME_BY_DOCTRINE: dict[Doctrine, str] = {
    "peer": "peer.json",
    "near-peer": "near-peer.json",
    "hybrid": "hybrid-irregular.json",
}


@cache
def load_profile(doctrine: Doctrine) -> dict[str, Any]:
    """Return the capability profile bound to the given doctrine.

    Cached at process scope; profiles are immutable per WS-106 § 5.
    """
    filename = _FILENAME_BY_DOCTRINE[doctrine]
    with (_PROFILES_DIR / filename).open() as f:
        return json.load(f)

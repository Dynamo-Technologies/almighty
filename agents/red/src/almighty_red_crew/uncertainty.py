"""Uncertainty band resolution for red profiles.

WS-106 § 6 specifies two band shapes:

  band_pct                — relative ± as a fraction (e.g., 0.20 = ±20%)
  {band_lower, band_upper} — absolute lower / upper bounds

When a red agent reasons about its own reach (effector range, sensor
range, jamming power), it is supposed to compute the upper edge of the
band — the "best case" reach — and then the validator caps emission at
the profile's posted ``effect_parameter_ranges[family]`` maximum.

The WS-202 validator does not yet implement post-hoc clamping (see
the Open Q in services/czml-validator/README.md). v1's contract is:

  reasoning_value = nominal × (1 + band_pct)        # or band_upper
  committed_value = min(reasoning_value, profile_cap)

The agent records both values in the step result so the test can
assert that band reasoning actually occurred.

This module is a small helper. Path syntax mirrors WS-106 § 6:
dot-separated segments, with array-by-id sugar ``[<id>]``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class UncertaintyResolution:
    """The result of resolving a profile path against an uncertainty band."""

    nominal: float
    upper_with_band: float
    chosen: float
    capped: bool
    band_kind: str  # "band_pct" | "band_lower_upper" | "absent"
    band_value: dict[str, Any]


_ARRAY_BY_ID = re.compile(r"^([^\[]+)\[([^\]]+)\]$")


def _walk_path(profile: dict[str, Any], path: str) -> Any:
    """Resolve a dotted path into ``profile``. Supports array-by-id
    sugar: ``effector.weapon_systems[notional.indirect.medium].effective_range_m``
    -> traverse to ``effector.weapon_systems``, find the entry whose
    ``id`` field equals ``notional.indirect.medium``, then index by
    ``effective_range_m``.
    """
    cursor: Any = profile
    for segment in path.split("."):
        # Re-join any segment fragments that had dots inside the [...] sugar.
        # The simple split above breaks "weapon_systems[notional.indirect.medium]"
        # because of the inner dots; we instead parse the path with a careful
        # walker.
        raise AssertionError("use _walk_path_safe instead")
    return cursor


def _walk_path_safe(profile: dict[str, Any], path: str) -> Any:
    """Path walker that respects [...] groups so the inner dots don't
    split the path."""
    cursor: Any = profile
    # Tokenize: split on '.' but only outside [...].
    tokens: list[str] = []
    buf = ""
    depth = 0
    for ch in path:
        if ch == "[":
            depth += 1
            buf += ch
        elif ch == "]":
            depth -= 1
            buf += ch
        elif ch == "." and depth == 0:
            if buf:
                tokens.append(buf)
                buf = ""
        else:
            buf += ch
    if buf:
        tokens.append(buf)

    for token in tokens:
        m = _ARRAY_BY_ID.match(token)
        if m:
            key, item_id = m.group(1), m.group(2)
            arr = cursor[key]
            match = next((x for x in arr if x.get("id") == item_id), None)
            if match is None:
                raise KeyError(
                    f"no item with id={item_id!r} in profile array {key!r}"
                )
            cursor = match
        else:
            cursor = cursor[token]
    return cursor


def resolve_uncertain_value(
    profile: dict[str, Any],
    path: str,
    profile_cap: float | None = None,
) -> UncertaintyResolution:
    """Resolve the value at ``path`` and apply the matching uncertainty
    band, returning what the agent should reason about and what it
    should commit.

    If ``profile_cap`` is supplied, ``chosen`` is ``min(upper_with_band,
    profile_cap)`` and ``capped`` reports whether the cap took effect.
    Without a cap, ``chosen`` equals ``upper_with_band``.
    """
    nominal = float(_walk_path_safe(profile, path))
    band = (profile.get("uncertainty") or {}).get(path, {})
    if "band_pct" in band:
        upper_with_band = nominal * (1.0 + float(band["band_pct"]))
        kind = "band_pct"
    elif "band_upper" in band:
        upper_with_band = float(band["band_upper"])
        kind = "band_lower_upper"
    else:
        upper_with_band = nominal
        kind = "absent"

    if profile_cap is not None:
        chosen = min(upper_with_band, profile_cap)
        capped = chosen < upper_with_band
    else:
        chosen = upper_with_band
        capped = False

    return UncertaintyResolution(
        nominal=nominal,
        upper_with_band=upper_with_band,
        chosen=chosen,
        capped=capped,
        band_kind=kind,
        band_value=dict(band),
    )

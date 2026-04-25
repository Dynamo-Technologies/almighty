"""End-to-end tests for the WS-202 validator against the four WS-107 profiles."""

from __future__ import annotations

import json

import pytest

from almighty_czml_validator.families import FAMILY_EMITTING_VERBS
from almighty_czml_validator.models import ValidateRequest

from conftest import (
    PROFILE_FAMILY_PAIRS,
    PROFILE_NAMES,
    TEMPLATES_DIR,
    family_to_template_id,
)


def _load_template(family: str) -> dict:
    template_id = family_to_template_id(family)
    with (TEMPLATES_DIR / f"{template_id}.czml.json").open() as f:
        return json.load(f)


def _midpoint_params(template: dict, profile_ranges: dict) -> dict[str, float]:
    """Build a params dict with each constrained param set to the midpoint of
    intersect(template_range, profile_range)."""
    out: dict[str, float] = {}
    for param, t_range in template["capability_constraints"].items():
        p_range = profile_ranges.get(param)
        if p_range:
            lo = max(t_range["min"], p_range["min"])
            hi = min(t_range["max"], p_range["max"])
        else:
            lo, hi = t_range["min"], t_range["max"]
        # Midpoint, rounded to keep integer-typed params integer where possible.
        mid = (lo + hi) / 2
        out[param] = mid
    return out


# ---------- Happy path ----------

@pytest.mark.parametrize("profile_name,family", PROFILE_FAMILY_PAIRS)
def test_accept_midpoint(profile_name: str, family: str, profiles, validator):
    profile = profiles[profile_name]
    # Skip if the profile authorizes the family but lacks the verb (data quirk).
    emitting = FAMILY_EMITTING_VERBS[family]
    if not (emitting & set(profile["action_verbs_available"])):
        pytest.skip(
            f"profile '{profile_name}' has '{family}' in ranges but no emitting verb "
            f"in action_verbs_available — data quirk in the profile, not a validator bug"
        )
    template = _load_template(family)
    params = _midpoint_params(template, profile["effect_parameter_ranges"][family])
    request = ValidateRequest(
        template_id=family_to_template_id(family),
        params=params,
        agent_id=f"test-agent-{profile_name}",
        capability_profile=profile,
    )
    result = validator.validate(request)
    assert result.accepted, f"expected accept; reasons: {result.reasons}"


# ---------- Reject path: out-of-range value ----------

@pytest.mark.parametrize("profile_name,family", PROFILE_FAMILY_PAIRS)
def test_reject_out_of_range(profile_name: str, family: str, profiles, validator):
    profile = profiles[profile_name]
    emitting = FAMILY_EMITTING_VERBS[family]
    if not (emitting & set(profile["action_verbs_available"])):
        pytest.skip(f"data quirk; see test_accept_midpoint")
    template = _load_template(family)
    profile_ranges = profile["effect_parameter_ranges"][family]
    # Pick the first param that has both a template constraint and a profile range,
    # blow it past the intersect upper bound.
    target_param = None
    for p in template["capability_constraints"]:
        if p in profile_ranges:
            target_param = p
            break
    assert target_param is not None, (
        f"no overlapping constrained param between template '{family}' and "
        f"profile '{profile_name}'"
    )

    params = _midpoint_params(template, profile_ranges)
    t_range = template["capability_constraints"][target_param]
    p_range = profile_ranges[target_param]
    eff_max = min(t_range["max"], p_range["max"])
    params[target_param] = eff_max + abs(eff_max) + 100  # safely over the upper bound

    request = ValidateRequest(
        template_id=family_to_template_id(family),
        params=params,
        agent_id=f"test-agent-{profile_name}",
        capability_profile=profile,
    )
    result = validator.validate(request)
    assert not result.accepted, "expected reject"
    assert len(result.reasons) >= 1
    assert target_param in result.reasons[0], (
        f"reject reason should name the violating param '{target_param}'; "
        f"got: {result.reasons[0]}"
    )
    assert "out of range" in result.reasons[0]


# ---------- Reject path: profile lacks the emitting verb ----------

def test_reject_missing_verb(profiles, validator):
    """us-bct.json has no `jam` verb, so any jamming-circle packet rejects
    at the verb-emission gate."""
    profile = profiles["us-bct"]
    assert "jam" not in profile["action_verbs_available"]
    request = ValidateRequest(
        template_id="jamming-circle",
        params={"radius_m": 1000, "power_w": 100},
        agent_id="test-agent-us-bct",
        capability_profile=profile,
    )
    result = validator.validate(request)
    assert not result.accepted
    assert "no verb that emits family 'jamming_circle'" in result.reasons[0]


# ---------- Reject path: family not in profile's effect_parameter_ranges ----------

def test_reject_family_not_authorized(profiles, validator):
    """Construct a synthetic profile that has the verb but no
    effect_parameter_ranges entry; expect family-not-authorized rejection."""
    base = profiles["peer"]
    synthetic = {
        **base,
        "effect_parameter_ranges": {
            k: v for k, v in base["effect_parameter_ranges"].items() if k != "jamming_circle"
        },
    }
    assert "jam" in synthetic["action_verbs_available"]
    assert "jamming_circle" not in synthetic["effect_parameter_ranges"]
    request = ValidateRequest(
        template_id="jamming-circle",
        params={"radius_m": 1000, "power_w": 100},
        agent_id="test-agent-synthetic",
        capability_profile=synthetic,
    )
    result = validator.validate(request)
    assert not result.accepted
    assert "does not authorize effect family 'jamming_circle'" in result.reasons[0]


# ---------- Reject path: unknown template ----------

def test_reject_unknown_template(profiles, validator):
    request = ValidateRequest(
        template_id="this-template-does-not-exist",
        params={},
        agent_id="test",
        capability_profile=profiles["us-bct"],
    )
    result = validator.validate(request)
    assert not result.accepted
    assert "unknown template" in result.reasons[0]


# ---------- Reject path: missing constrained param ----------

def test_reject_missing_param(profiles, validator):
    """If a template declares a capability-constrained param, it MUST be
    present in the substitution payload."""
    profile = profiles["us-bct"]
    # indirect_fire_arc has 4 constrained params; supply only 3.
    request = ValidateRequest(
        template_id="indirect-fire-arc",
        params={
            "range_m": 5000,
            "time_of_flight_s": 30,
            "dispersion_ellipse_a_m": 50,
            # dispersion_ellipse_b_m intentionally missing
        },
        agent_id="test",
        capability_profile=profile,
    )
    result = validator.validate(request)
    assert not result.accepted
    assert "missing constrained parameter 'dispersion_ellipse_b_m'" in result.reasons[0]


# ---------- Coverage sentinel ----------

def test_all_four_profiles_loaded(profiles):
    """Sentinel: confirm the runbook DoD ('unit-tested against all four profiles')
    is satisfied by name."""
    assert set(profiles.keys()) == set(PROFILE_NAMES)
    for name in PROFILE_NAMES:
        assert profiles[name]["display_name"], f"profile {name} missing display_name"

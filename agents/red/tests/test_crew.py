"""End-to-end tests for the v1 deterministic red OpFor crew (WS-404 DoD).

Covers two requirements from #24:
  1. Crew runs one full between-turn cycle producing valid PyRapide
     events — for *each* of the three doctrine flavors.
  2. Uncertainty bands are exercised — Co B's engage step records the
     band reasoning (nominal, upper_with_band, chosen, capped) and the
     committed value is the profile-cap-bounded result.
"""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest

from almighty_red_crew.crew import _build_script, run_red_crew
from almighty_red_crew.doctrine import VALID_DOCTRINES


@pytest.mark.parametrize("doctrine", VALID_DOCTRINES)
def test_crew_runs_one_full_cycle_per_doctrine(crew_ctx, doctrine):
    result = run_red_crew(crew_ctx, doctrine=doctrine)
    expected_step_count = len(_build_script(doctrine))
    assert result.crew == "red"
    assert result.metadata["doctrine"] == doctrine
    assert result.metadata["events_committed"] == expected_step_count
    assert result.metadata["validator_rejections"] == 0
    assert result.duration_ms >= 0


def test_step_count_per_doctrine(crew_ctx):
    """Peer / near-peer have 10 steps (S2.detect + S3.issue_order +
    S3.request_support + Co A.assume_posture + Co A.send + Co B.halt +
    Co B.engage + Co C.move_to + S6.send + S6.report). Hybrid has 9
    (S3.issue_order + S3.request_support replaced by a single
    S3.send_shadow)."""
    assert len(_build_script("peer")) == 10
    assert len(_build_script("near-peer")) == 10
    assert len(_build_script("hybrid")) == 9


@pytest.mark.parametrize("doctrine", VALID_DOCTRINES)
def test_uncertainty_band_exercised_on_engage(crew_ctx, doctrine):
    """The Co B engage step must carry an `uncertainty_reasoning` block,
    and the chosen value must be the profile-capped result of the
    band-reasoned upper edge."""
    result = run_red_crew(crew_ctx, doctrine=doctrine)
    engage_step = next(s for s in result.metadata["steps"] if s["step"] == "co_b.engage")
    reasoning = engage_step["uncertainty_reasoning"]
    # Required keys.
    for key in (
        "path", "nominal", "upper_with_band", "chosen", "capped",
        "band_kind", "band_value", "profile_cap",
    ):
        assert key in reasoning, f"missing {key!r} in uncertainty_reasoning"
    # band_kind matches one of the two shapes WS-106 § 6 defines.
    assert reasoning["band_kind"] in ("band_pct", "band_lower_upper")
    # All three doctrine indirect weapons declare a band on
    # effective_range_m, so upper_with_band > nominal.
    assert reasoning["upper_with_band"] > reasoning["nominal"]
    # Each profile's posted indirect_fire_arc.range_m max equals the
    # weapon's nominal effective_range_m (cap = nominal), so the
    # band's upper edge always exceeds the cap → chosen == cap < upper.
    assert reasoning["chosen"] == reasoning["profile_cap"]
    assert reasoning["chosen"] < reasoning["upper_with_band"]
    assert reasoning["capped"] is True


@pytest.mark.parametrize("doctrine", VALID_DOCTRINES)
def test_every_step_has_a_unique_event_id(crew_ctx, doctrine):
    result = run_red_crew(crew_ctx, doctrine=doctrine)
    event_ids = [step["event_id"] for step in result.metadata["steps"]]
    assert len(event_ids) == len(set(event_ids))
    assert all(eid for eid in event_ids)


def test_default_doctrine_is_peer(crew_ctx):
    """No explicit doctrine arg, no env var → peer."""
    with patch.dict(os.environ, {}, clear=True):
        # Belt and suspenders: ensure ALMIGHTY_RED_DOCTRINE is unset for this assertion.
        os.environ.pop("ALMIGHTY_RED_DOCTRINE", None)
        result = run_red_crew(crew_ctx)
    assert result.metadata["doctrine"] == "peer"


def test_env_var_overrides_default(crew_ctx):
    with patch.dict(os.environ, {"ALMIGHTY_RED_DOCTRINE": "near-peer"}):
        result = run_red_crew(crew_ctx)
    assert result.metadata["doctrine"] == "near-peer"


def test_explicit_arg_overrides_env_var(crew_ctx):
    with patch.dict(os.environ, {"ALMIGHTY_RED_DOCTRINE": "hybrid"}):
        result = run_red_crew(crew_ctx, doctrine="peer")
    assert result.metadata["doctrine"] == "peer"


def test_invalid_doctrine_raises():
    from almighty_red_crew.doctrine import select_doctrine

    with pytest.raises(ValueError) as exc:
        select_doctrine("super-peer")  # type: ignore[arg-type]
    assert "invalid doctrine" in str(exc.value)


def test_runner_export_is_callable(crew_ctx):
    from almighty_red_crew import RED_RUNNER

    out = RED_RUNNER(crew_ctx)
    assert out.crew == "red"
    assert out.metadata["doctrine"] in VALID_DOCTRINES

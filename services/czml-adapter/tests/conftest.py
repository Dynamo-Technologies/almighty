"""Shared fixtures: WS-201 templates, WS-107 us-bct + peer profiles,
WS-202 validator. All real, no mocks of upstream contracts."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID, uuid4

import pytest

from almighty_czml_validator import Validator
from almighty_czml_validator.templates import TemplateLoader
from almighty_kernel.dag import KernelEvent

from almighty_czml_adapter.models import EntityPosition

REPO_ROOT = Path(__file__).resolve().parents[3]
PROFILES_DIR = REPO_ROOT / "kernel" / "capability-profiles"
TEMPLATES_DIR = REPO_ROOT / "czml" / "templates"

TENANT = UUID("11111111-1111-4111-8111-111111111111")
SCENARIO = UUID("22222222-2222-4222-8222-222222222222")
ENTITY = UUID("33333333-3333-4333-8333-333333333333")


@pytest.fixture(scope="session")
def template_loader() -> TemplateLoader:
    return TemplateLoader(templates_dir=TEMPLATES_DIR)


@pytest.fixture(scope="session")
def validator(template_loader: TemplateLoader) -> Validator:
    return Validator(template_loader=template_loader)


def _load_profile(name: str) -> dict:
    with (PROFILES_DIR / f"{name}.json").open() as f:
        return json.load(f)


@pytest.fixture(scope="session")
def us_bct_profile() -> dict:
    return _load_profile("us-bct")


@pytest.fixture(scope="session")
def peer_profile() -> dict:
    """The peer profile authorizes families us-bct doesn't (jam, ew_cone,
    uas_corridor) — useful for cross-family coverage."""
    return _load_profile("peer")


@pytest.fixture()
def position() -> EntityPosition:
    """Anchor at Nashville west-bank BN HQ from the WS-403 doctrine."""
    return EntityPosition(lat_deg=36.1750, lon_deg=-86.7900, alt_m=170.0)


def make_event(
    *,
    action_verb: str,
    source_officer_type: str,
    payload: dict | None = None,
    turn: int = 1,
    tenant_id: UUID = TENANT,
    scenario_id: UUID = SCENARIO,
    source_entity_id: UUID = ENTITY,
) -> KernelEvent:
    return KernelEvent(
        event_id=uuid4(),
        tenant_id=tenant_id,
        scenario_id=scenario_id,
        turn=turn,
        source_officer_type=source_officer_type,
        source_entity_id=source_entity_id,
        action_verb=action_verb,
        payload=payload or {},
        causal_predecessors=[],
        ts=datetime(2026, 4, 25, 18, 0, 0, tzinfo=timezone.utc),
    )

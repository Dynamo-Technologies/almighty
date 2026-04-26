"""Test fixtures.

Loads the WS-107 capability profiles from the repo and constructs an
OfficerToolContext bound to a real :class:`NamespacedDag` and the real
WS-202 :class:`Validator`. No mocks of those: when a tool fires, it
genuinely commits to the in-memory DAG and genuinely consults the
validator. That keeps the contract honest end-to-end.
"""

from __future__ import annotations

import json
from pathlib import Path
from uuid import UUID, uuid4

import pytest

from almighty_czml_validator import Validator
from almighty_kernel.dag import NamespacedDag

from almighty_officer_tools import OfficerToolContext, build_all_tools
from almighty_officer_tools.base import OfficerToolBase

REPO_ROOT = Path(__file__).resolve().parents[3]
PROFILES_DIR = REPO_ROOT / "kernel" / "capability-profiles"


def _load_profile(name: str) -> dict:
    with (PROFILES_DIR / f"{name}.json").open() as f:
        return json.load(f)


@pytest.fixture(scope="session")
def us_bct_profile() -> dict:
    return _load_profile("us-bct")


@pytest.fixture(scope="session")
def peer_profile() -> dict:
    return _load_profile("peer")


@pytest.fixture(scope="session")
def hybrid_profile() -> dict:
    return _load_profile("hybrid-irregular")


@pytest.fixture()
def kernel_dag() -> NamespacedDag:
    return NamespacedDag()


@pytest.fixture(scope="session")
def validator() -> Validator:
    return Validator()


@pytest.fixture()
def context_factory(kernel_dag: NamespacedDag, validator: Validator):
    """Returns a callable to mint an OfficerToolContext bound to the
    fixture's DAG + validator. Tests pass in the profile they want."""

    def _make(
        profile: dict,
        *,
        turn: int = 0,
        tenant_id: UUID | None = None,
        scenario_id: UUID | None = None,
        agent_entity_id: UUID | None = None,
    ) -> OfficerToolContext:
        return OfficerToolContext(
            tenant_id=tenant_id or UUID("11111111-1111-4111-8111-111111111111"),
            scenario_id=scenario_id or UUID("22222222-2222-4222-8222-222222222222"),
            turn=turn,
            agent_entity_id=agent_entity_id or uuid4(),
            capability_profile=profile,
            kernel_dag=kernel_dag,
            validator=validator,
        )

    return _make


@pytest.fixture()
def all_tools_us_bct(context_factory, us_bct_profile) -> dict[str, OfficerToolBase]:
    return build_all_tools(context_factory(us_bct_profile))


@pytest.fixture()
def all_tools_peer(context_factory, peer_profile) -> dict[str, OfficerToolBase]:
    return build_all_tools(context_factory(peer_profile))

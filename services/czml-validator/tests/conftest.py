"""Test fixtures. Load WS-107 profiles and WS-201 templates from disk so tests
stay in sync with the canonical artifacts on main."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from almighty_czml_validator.templates import TemplateLoader
from almighty_czml_validator.validator import Validator


REPO_ROOT = Path(__file__).resolve().parents[3]
PROFILES_DIR = REPO_ROOT / "kernel" / "capability-profiles"
TEMPLATES_DIR = REPO_ROOT / "czml" / "templates"

PROFILE_NAMES = ["us-bct", "peer", "near-peer", "hybrid-irregular"]


@pytest.fixture(scope="session")
def template_loader() -> TemplateLoader:
    return TemplateLoader(templates_dir=TEMPLATES_DIR)


@pytest.fixture(scope="session")
def validator(template_loader: TemplateLoader) -> Validator:
    return Validator(template_loader=template_loader)


@pytest.fixture(scope="session")
def profiles() -> dict[str, dict]:
    out: dict[str, dict] = {}
    for name in PROFILE_NAMES:
        with (PROFILES_DIR / f"{name}.json").open() as f:
            out[name] = json.load(f)
    return out


def family_to_template_id(family: str) -> str:
    """Inverse of `template_id_to_family`."""
    return family.replace("_", "-")


def discover_profile_family_pairs() -> list[tuple[str, str]]:
    """For each profile, enumerate the spatial families it authorizes."""
    pairs: list[tuple[str, str]] = []
    for name in PROFILE_NAMES:
        with (PROFILES_DIR / f"{name}.json").open() as f:
            profile = json.load(f)
        for family in profile.get("effect_parameter_ranges", {}):
            pairs.append((name, family))
    return pairs


PROFILE_FAMILY_PAIRS = discover_profile_family_pairs()

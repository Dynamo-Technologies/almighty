"""Effect family <-> template_id mapping and verb-emission table.

The mapping is the canonical contract from WS-108 (artifact taxonomy).
Templates use hyphenated IDs (`jamming-circle`); profiles use underscored
family keys (`jamming_circle`). The two are isomorphic via `s/-/_/`.
"""

from __future__ import annotations


def template_id_to_family(template_id: str) -> str:
    """Convert hyphenated template id (e.g. 'jamming-circle') to underscored
    family key used in capability profile `effect_parameter_ranges`."""
    return template_id.replace("-", "_")


# Verbs that emit each spatial family, per docs/schema/artifacts.md (WS-108) § 6.
# A profile is allowed to emit a family iff at least one of these verbs is in
# `action_verbs_available`.
FAMILY_EMITTING_VERBS: dict[str, frozenset[str]] = {
    "ew_cone":           frozenset({"detect", "jam"}),
    "uas_corridor":      frozenset({"relay"}),
    "radar_fan":         frozenset({"detect", "track"}),
    "jamming_circle":    frozenset({"jam"}),
    "satellite_swath":   frozenset({"detect", "track"}),
    "indirect_fire_arc": frozenset({"engage", "suppress", "destroy", "disable"}),
    "ir_plume":          frozenset({"destroy", "disable"}),
    "masint_cell":       frozenset({"detect", "classify"}),
    "keyhole_footprint": frozenset({"classify"}),
}

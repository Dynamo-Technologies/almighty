"""Pure event -> CZML packet projection.

No I/O. Caller supplies:

  - template_loader   : almighty_czml_validator.TemplateLoader
  - validator         : almighty_czml_validator.Validator (in-process)
  - entity_position_lookup : Callable[[UUID], EntityPosition] | None
  - capability_profile : dict[str, Any] (the WS-106 / WS-107 profile)

Returns an :class:`AdapterResult` per input event:

  ACCEPTED  : packet ready to publish on `czml_packets`.
  REJECTED  : validator rejected; caller emits `czml_rejected` audit.
  SKIPPED   : event has no spatial family (Mover / Commander / etc.).
"""

from __future__ import annotations

from typing import Any, Callable

from almighty_czml_validator import ValidateRequest, Validator
from almighty_czml_validator.templates import TemplateLoader
from almighty_kernel.dag import KernelEvent

from .families import find_handler, new_artifact_id
from .models import AdapterResult, EntityPosition

EntityPositionLookup = Callable[[KernelEvent], EntityPosition]


# Substitution defaults --------------------------------------------------------

_DEFAULT_POSITION = EntityPosition(lat_deg=36.18, lon_deg=-86.78, alt_m=170.0)


def _default_lookup(_event: KernelEvent) -> EntityPosition:
    """Fallback when the caller doesn't supply a lookup. v1 returns a
    Nashville-anchored point so v1 demos render somewhere visible.
    Production callers MUST supply a real lookup."""
    return _DEFAULT_POSITION


# Token substitution -----------------------------------------------------------


def _substitute(node: Any, tokens: dict[str, Any]) -> Any:
    """Recursively replace ``{{token}}`` strings inside the template's
    ``base`` block. Two modes per WS-201's README:

      - Whole-value: a string equal to ``"{{token}}"`` becomes the
        token's native-typed value (number, bool, list, etc.).
      - Interpolated: ``{{token}}`` inside a longer string is
        stringified and substituted in place.
    """
    if isinstance(node, str):
        # Whole-value: exactly "{{key}}" with no other characters.
        if (
            node.startswith("{{")
            and node.endswith("}}")
            and node.count("{{") == 1
            and node.count("}}") == 1
        ):
            key = node[2:-2]
            if key in tokens:
                return tokens[key]
            return node  # unknown token; leave unsubstituted
        # Interpolated.
        result = node
        for key, value in tokens.items():
            placeholder = "{{" + key + "}}"
            if placeholder in result:
                result = result.replace(placeholder, str(value))
        return result
    if isinstance(node, dict):
        return {k: _substitute(v, tokens) for k, v in node.items()}
    if isinstance(node, list):
        return [_substitute(x, tokens) for x in node]
    return node


# Public entry point -----------------------------------------------------------


def translate_event(
    event: KernelEvent,
    *,
    template_loader: TemplateLoader,
    validator: Validator,
    capability_profile: dict[str, Any],
    entity_position_lookup: EntityPositionLookup | None = None,
) -> AdapterResult:
    """Translate one PyRapide event into an :class:`AdapterResult`."""
    handler = find_handler(event)
    if handler is None:
        return AdapterResult.skipped(
            event_id=event.event_id,
            reason=f"no spatial family for verb '{event.action_verb}'",
        )

    lookup = entity_position_lookup or _default_lookup
    position = lookup(event)
    artifact_id = new_artifact_id()
    tokens = handler.token_builder(event, position, artifact_id)
    validator_params = {k: tokens[k] for k in handler.validator_param_keys if k in tokens}

    template = template_loader.load(handler.template_id)
    result = validator.validate(
        ValidateRequest(
            template_id=handler.template_id,
            template_version=int(template.get("version", 1)),
            params=validator_params,
            agent_id=str(event.source_entity_id),
            capability_profile=capability_profile,
        )
    )
    if not result.accepted:
        return AdapterResult.rejected(
            event_id=event.event_id,
            family=handler.family,
            reason="; ".join(result.reasons) or "validator rejected",
            validator_params=validator_params,
        )

    packet = _substitute(template["base"], tokens)
    return AdapterResult.accepted(
        event_id=event.event_id,
        family=handler.family,
        packet=packet,
        validator_params=validator_params,
    )

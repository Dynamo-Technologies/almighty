"""Capability-gated CZML validator core. WS-202.

Logic per the runbook prompt:

  1. Look up the template referenced by template_id (+ version).
  2. Compute the effect family from the template_id.
  3. Verify the agent's profile has at least one verb that emits this
     family (per WS-108 verb-emission table) AND the family appears in
     `effect_parameter_ranges`. A missing family in the profile is "this
     entity cannot emit this family at all" -> reject.
  4. For each parameter declared in the template's `capability_constraints`,
     intersect (template range, profile range) and bound-check the
     post-substitution param value.
  5. Reject on the first violating reason; accept if everything passes.
"""

from __future__ import annotations

from typing import Any

from .families import FAMILY_EMITTING_VERBS, template_id_to_family
from .models import ValidateRequest, ValidationResult
from .templates import TemplateLoader, TemplateNotFound


class Validator:
    def __init__(self, template_loader: TemplateLoader | None = None) -> None:
        self.template_loader = template_loader or TemplateLoader()

    def validate(self, request: ValidateRequest) -> ValidationResult:
        # Step 1: load template
        try:
            template = self.template_loader.load(request.template_id, request.template_version)
        except TemplateNotFound as exc:
            return ValidationResult.reject(f"unknown template: {exc}")

        # Step 2: derive family
        family = template_id_to_family(request.template_id)
        if family not in FAMILY_EMITTING_VERBS:
            return ValidationResult.reject(
                f"template '{request.template_id}' has no registered effect family"
            )

        profile = request.capability_profile

        # Step 3a: verb-emission check
        emitting_verbs = FAMILY_EMITTING_VERBS[family]
        verbs_available = set(profile.get("action_verbs_available", []))
        if not (emitting_verbs & verbs_available):
            return ValidationResult.reject(
                f"profile '{profile.get('display_name', '<unnamed>')}' has no verb "
                f"that emits family '{family}' "
                f"(needs one of {sorted(emitting_verbs)}; "
                f"profile has {sorted(verbs_available)})"
            )

        # Step 3b: family-presence check in effect_parameter_ranges
        profile_ranges_all = profile.get("effect_parameter_ranges", {})
        if family not in profile_ranges_all:
            return ValidationResult.reject(
                f"profile '{profile.get('display_name', '<unnamed>')}' does not authorize "
                f"effect family '{family}' (no entry in effect_parameter_ranges)"
            )
        profile_ranges = profile_ranges_all[family]

        # Step 4: per-parameter bound check
        template_constraints = template.get("capability_constraints", {})
        for param_name, template_range in template_constraints.items():
            if param_name not in request.params:
                # Required-by-template missing from substitution payload.
                # Distinguish from optional template params (those without
                # capability_constraints entries are not policed here).
                return ValidationResult.reject(
                    f"missing constrained parameter '{param_name}' for family '{family}'"
                )
            value = request.params[param_name]
            if not isinstance(value, (int, float)):
                return ValidationResult.reject(
                    f"parameter '{param_name}' for family '{family}' must be numeric, "
                    f"got {type(value).__name__}"
                )
            t_min, t_max = template_range["min"], template_range["max"]
            profile_range = profile_ranges.get(param_name)
            if profile_range is None:
                # Profile silent on this parameter -> only template bound applies.
                eff_min, eff_max = t_min, t_max
                bound_source = f"template[{request.template_id}]"
            else:
                eff_min = max(t_min, profile_range["min"])
                eff_max = min(t_max, profile_range["max"])
                bound_source = f"intersect(template[{request.template_id}], profile[{family}])"
            if eff_min > eff_max:
                return ValidationResult.reject(
                    f"empty intersection on '{param_name}' for family '{family}': "
                    f"template=[{t_min},{t_max}] profile=[{profile_range['min']},{profile_range['max']}]"
                )
            if value < eff_min or value > eff_max:
                return ValidationResult.reject(
                    f"'{param_name}'={value} out of range [{eff_min}, {eff_max}] "
                    f"({bound_source})"
                )

        # All checks passed
        return ValidationResult.accept()


def validate(
    *,
    template_id: str,
    template_version: int = 1,
    params: dict[str, Any],
    agent_id: str,
    capability_profile: dict[str, Any],
    template_loader: TemplateLoader | None = None,
) -> ValidationResult:
    """Convenience function for callers that don't want to instantiate a Validator."""
    request = ValidateRequest(
        template_id=template_id,
        template_version=template_version,
        params=params,
        agent_id=agent_id,
        capability_profile=capability_profile,
    )
    return Validator(template_loader=template_loader).validate(request)

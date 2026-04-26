"""OfficerToolBase — common gate-then-validate-then-commit machinery.

Each verb subclasses this and declares:

- ``OFFICER_TYPE`` — one of SENSOR/EFFECTOR/MOVER/COMMUNICATOR/COMMANDER.
- ``VERB`` — the lowercase verb name (matches WS-105).
- ``EFFECT_FAMILY`` — the spatial-family key used by the validator
  (e.g., ``jamming_circle``); ``None`` for non-CZML verbs.
- ``args_schema`` — a pydantic model describing the verb's parameter set
  per WS-105.
- ``_build_event_payload(args)`` — converts the validated args into the
  ``KernelEvent.payload`` dict.
- ``_build_validator_params(args)`` — only required when EFFECT_FAMILY is
  not None; returns the post-substitution param dict the WS-202
  validator gates on.

The base handles, in order:

  1. Capability-verb gate. If ``self.VERB`` is not in
     ``profile.action_verbs_available``, raise ``ToolError`` immediately
     **without** touching the validator. (Per WS-105 / runbook §1093.)
  2. (CZML-emitting verbs only) Build params and call the validator
     in-process. On ``accepted=False``, raise ``ToolError(reason)``.
  3. Build a ``KernelEvent`` and commit via ``NamespacedDag.commit()`` —
     the only sanctioned write path per
     ``docs/better-late-than-never.md`` (Schema and data model § "Don't
     INSERT INTO events directly").

Returns the committed event_id and the validator outcome (or "skipped"
for non-CZML verbs) as a dict so a CrewAI agent can chain on it.
"""

from __future__ import annotations

from abc import abstractmethod
from typing import Any, ClassVar
from uuid import uuid4

from almighty_czml_validator import ValidateRequest
from almighty_kernel.dag import KernelEvent
from crewai.tools import BaseTool
from pydantic import BaseModel, ConfigDict, PrivateAttr

from .context import OfficerToolContext, ToolError


class OfficerToolBase(BaseTool):
    """Common base for the 20 officer interface tools."""

    OFFICER_TYPE: ClassVar[str]
    VERB: ClassVar[str]
    EFFECT_FAMILY: ClassVar[str | None] = None  # default non-spatial

    # Pydantic v2 fields the BaseTool subclass requires; we set them in
    # `__init__` from class-level constants so each verb file just needs
    # to define `_TOOL_NAME` and `_TOOL_DESCRIPTION` plus its args schema.
    name: str = "almighty.officer-tool.base"
    description: str = "abstract base"

    model_config = ConfigDict(arbitrary_types_allowed=True)
    _ctx: OfficerToolContext = PrivateAttr()

    def __init__(self, ctx: OfficerToolContext, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._ctx = ctx

    # ---- subclass hooks ---------------------------------------------------

    @abstractmethod
    def _build_event_payload(self, args: BaseModel) -> dict[str, Any]:
        """Return the ``payload`` dict for the KernelEvent."""

    def _build_validator_params(self, args: BaseModel) -> dict[str, Any]:
        """Required when ``EFFECT_FAMILY`` is set. Default raises so
        non-CZML verbs don't accidentally call the validator path."""
        raise NotImplementedError(
            f"{type(self).__name__} declares EFFECT_FAMILY={self.EFFECT_FAMILY!r} "
            f"but did not implement _build_validator_params"
        )

    def _effect_family_for(self, args: BaseModel) -> str | None:
        """Resolve the effect family for this call. Default returns the
        class-level ``EFFECT_FAMILY``. Verbs whose family depends on
        runtime args (e.g. ``Sensor.detect`` on modality) override."""
        del args
        return self.EFFECT_FAMILY

    # ---- core flow --------------------------------------------------------

    def _run(self, **kwargs: Any) -> dict[str, Any]:
        ctx = self._ctx
        # Step 1: capability-verb gate. Raises before any validator call.
        verbs = set(ctx.capability_profile.get("action_verbs_available", []))
        if self.VERB not in verbs:
            raise ToolError(
                f"capability gate: agent profile lacks verb '{self.VERB}'"
            )

        # Parse / validate the args via the pydantic schema.
        if self.args_schema is None:
            raise ToolError(f"{type(self).__name__}: args_schema is required")
        args = self.args_schema.model_validate(kwargs)

        # Step 2 (CZML verbs only): build params and call validator.
        validator_outcome: str
        family = self._effect_family_for(args)
        if family is not None:
            template_id = family.replace("_", "-")
            params = self._build_validator_params(args)
            request = ValidateRequest(
                template_id=template_id,
                template_version=1,
                params=params,
                agent_id=str(ctx.agent_entity_id),
                capability_profile=ctx.capability_profile,
            )
            result = ctx.validator.validate(request)
            if not result.accepted:
                raise ToolError(
                    f"validator rejected '{self.VERB}': {'; '.join(result.reasons)}"
                )
            validator_outcome = "accepted"
        else:
            validator_outcome = "skipped"

        # Step 3: commit the event through the namespaced DAG.
        event = KernelEvent(
            event_id=uuid4(),
            tenant_id=ctx.tenant_id,
            scenario_id=ctx.scenario_id,
            turn=ctx.turn,
            source_officer_type=self.OFFICER_TYPE,
            source_entity_id=ctx.agent_entity_id,
            action_verb=self.VERB,
            payload=self._build_event_payload(args),
            causal_predecessors=[],
        )
        ctx.kernel_dag.commit(event)

        return {
            "event_id": str(event.event_id),
            "verb": self.VERB,
            "officer_type": self.OFFICER_TYPE,
            "validator": validator_outcome,
        }

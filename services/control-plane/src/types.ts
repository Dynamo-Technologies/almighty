import { z } from "zod";

export const CellRole = z.enum(["white", "blue", "red", "observer"]);
export type CellRole = z.infer<typeof CellRole>;

export const JwtClaims = z.object({
  tenant_id: z.string().uuid(),
  cell_role: CellRole,
  sub: z.string().optional(),
});
export type JwtClaims = z.infer<typeof JwtClaims>;

export const TenantStatus = z.enum(["active", "archived"]);
export type TenantStatus = z.infer<typeof TenantStatus>;

export const ScenarioStatus = z.enum(["draft", "active", "archived"]);
export type ScenarioStatus = z.infer<typeof ScenarioStatus>;

export const Tenant = z.object({
  tenant_id: z.string().uuid(),
  display_name: z.string(),
  status: TenantStatus,
  created_at: z.coerce.date(),
  updated_at: z.coerce.date(),
});
export type Tenant = z.infer<typeof Tenant>;

export const Scenario = z.object({
  scenario_id: z.string().uuid(),
  tenant_id: z.string().uuid(),
  display_name: z.string(),
  status: ScenarioStatus,
  description: z.string(),
  created_at: z.coerce.date(),
  updated_at: z.coerce.date(),
});
export type Scenario = z.infer<typeof Scenario>;

export const CreateTenantBody = z.object({
  display_name: z.string().min(1).max(200),
});
export const UpdateTenantBody = z.object({
  display_name: z.string().min(1).max(200).optional(),
});

export const CreateScenarioBody = z.object({
  display_name: z.string().min(1).max(200),
  description: z.string().max(10_000).default(""),
});
export const UpdateScenarioBody = z.object({
  display_name: z.string().min(1).max(200).optional(),
  description: z.string().max(10_000).optional(),
  status: ScenarioStatus.optional(),
});

export const TenantIdParams = z.object({ id: z.string().uuid() });
export const ScenarioIdParams = z.object({ id: z.string().uuid(), sid: z.string().uuid() });

// ---------- WS-303 override gateway ----------

export const OverrideScope = z.enum(["per-event", "per-agent-per-turn", "per-turn"]);
export type OverrideScope = z.infer<typeof OverrideScope>;

export const OverrideAction = z.enum(["review", "auto-approve", "auto-block"]);
export type OverrideAction = z.infer<typeof OverrideAction>;

export const OverridePolicyStatus = z.enum(["active", "revoked"]);
export type OverridePolicyStatus = z.infer<typeof OverridePolicyStatus>;

export const OverrideDecisionOutcome = z.enum([
  "auto-approve",
  "auto-block",
  "review-pending",
  "review-approved",
  "review-blocked",
  "default-review",
]);
export type OverrideDecisionOutcome = z.infer<typeof OverrideDecisionOutcome>;

export const OverridePolicy = z.object({
  policy_id: z.string().uuid(),
  tenant_id: z.string().uuid(),
  scenario_id: z.string().uuid(),
  scope: OverrideScope,
  event_id: z.string().uuid().nullable(),
  agent_entity_id: z.string().uuid().nullable(),
  target_turn: z.number().int().nonnegative().nullable(),
  action: OverrideAction,
  ttl_turns: z.number().int().nonnegative(),
  created_in_turn: z.number().int().nonnegative(),
  rationale: z.string(),
  created_by: z.string().uuid(),
  status: OverridePolicyStatus,
  created_at: z.coerce.date(),
  updated_at: z.coerce.date(),
});
export type OverridePolicy = z.infer<typeof OverridePolicy>;

// Request body for POST /overrides. Per-scope shape rules enforced by superRefine.
export const CreateOverridePolicyBody = z
  .object({
    scope: OverrideScope,
    action: OverrideAction,
    ttl_turns: z.number().int().nonnegative().default(0),
    rationale: z.string().max(2000).default(""),
    event_id: z.string().uuid().optional(),
    agent_entity_id: z.string().uuid().optional(),
    target_turn: z.number().int().nonnegative().optional(),
  })
  .superRefine((val, ctx) => {
    const has = {
      event_id: val.event_id !== undefined,
      agent_entity_id: val.agent_entity_id !== undefined,
      target_turn: val.target_turn !== undefined,
    };
    if (val.scope === "per-event") {
      if (!has.event_id || has.agent_entity_id || has.target_turn) {
        ctx.addIssue({
          code: z.ZodIssueCode.custom,
          message: "scope=per-event requires event_id and forbids agent_entity_id / target_turn",
        });
      }
    } else if (val.scope === "per-agent-per-turn") {
      if (!has.agent_entity_id || !has.target_turn || has.event_id) {
        ctx.addIssue({
          code: z.ZodIssueCode.custom,
          message:
            "scope=per-agent-per-turn requires agent_entity_id and target_turn, forbids event_id",
        });
      }
    } else if (val.scope === "per-turn") {
      if (!has.target_turn || has.event_id || has.agent_entity_id) {
        ctx.addIssue({
          code: z.ZodIssueCode.custom,
          message: "scope=per-turn requires target_turn and forbids event_id / agent_entity_id",
        });
      }
    }
  });

export const ManualDecisionBody = z.object({
  outcome: z.enum(["review-approved", "review-blocked"]),
  rationale: z.string().max(2000).default(""),
});

export const OverrideIdParams = z.object({
  id: z.string().uuid(),
  sid: z.string().uuid(),
  oid: z.string().uuid(),
});

export const EventIdParams = z.object({
  id: z.string().uuid(),
  sid: z.string().uuid(),
  eid: z.string().uuid(),
});

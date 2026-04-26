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

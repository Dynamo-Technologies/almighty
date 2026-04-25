-- 0005_turn_snapshots.sql
-- Owned by WS-302 (#18).
--
-- Captures full simulation state at each turn boundary. v1 keeps every
-- snapshot indefinitely (branching and rollback are future work). The
-- snapshot_json column stores a structured object: { entities: [...],
-- events: [...] } where events are the last N for the turn that just
-- closed.

CREATE TABLE IF NOT EXISTS turn_snapshots (
    snapshot_id  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id    uuid NOT NULL REFERENCES tenants(tenant_id)   ON DELETE RESTRICT,
    scenario_id  uuid NOT NULL REFERENCES scenarios(scenario_id) ON DELETE RESTRICT,
    turn         int NOT NULL CHECK (turn >= 0),
    snapshot_json jsonb NOT NULL,
    created_at   timestamptz NOT NULL DEFAULT now(),

    -- One snapshot per (tenant, scenario, turn). The turn controller
    -- (WS-302) takes the snapshot at the END of the turn that is
    -- closing, so each (scenario, turn) pair is unique.
    CONSTRAINT turn_snapshots_unique_per_turn
        UNIQUE (tenant_id, scenario_id, turn)
);

CREATE INDEX IF NOT EXISTS turn_snapshots_namespace_idx
    ON turn_snapshots (tenant_id, scenario_id);

CREATE INDEX IF NOT EXISTS turn_snapshots_namespace_turn_idx
    ON turn_snapshots (tenant_id, scenario_id, turn DESC);

-- WS-302: turn-state machine on scenarios + turn_snapshots table.
-- Source-of-truth doc: docs/dummy-instructions.md WS-302 + this PR.

-- Up Migration

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'scenario_turn_state') THEN
        CREATE TYPE scenario_turn_state AS ENUM ('open', 'advancing', 'closed');
    END IF;
END$$;

ALTER TABLE scenarios
    ADD COLUMN IF NOT EXISTS current_turn int NOT NULL DEFAULT 0
        CHECK (current_turn >= 0);

ALTER TABLE scenarios
    ADD COLUMN IF NOT EXISTS turn_state scenario_turn_state NOT NULL DEFAULT 'open';

CREATE TABLE IF NOT EXISTS turn_snapshots (
    snapshot_id   uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id     uuid NOT NULL REFERENCES tenants (tenant_id)   ON DELETE RESTRICT,
    scenario_id   uuid NOT NULL,
    turn          int NOT NULL CHECK (turn >= 0),
    snapshot_json jsonb NOT NULL,
    created_at    timestamptz NOT NULL DEFAULT now(),

    -- Composite FK: snapshot belongs to the (tenant, scenario) pair. The
    -- scenarios.UNIQUE(tenant_id, scenario_id) added by WS-301 makes this
    -- legal.
    CONSTRAINT turn_snapshots_scenario_fk
        FOREIGN KEY (tenant_id, scenario_id)
        REFERENCES scenarios (tenant_id, scenario_id)
        ON DELETE RESTRICT,

    -- One snapshot per (tenant, scenario, turn). The controller takes the
    -- snapshot at the END of the closing turn, so the pair is unique.
    CONSTRAINT turn_snapshots_unique_per_turn
        UNIQUE (tenant_id, scenario_id, turn)
);

CREATE INDEX IF NOT EXISTS turn_snapshots_namespace_idx
    ON turn_snapshots (tenant_id, scenario_id);
CREATE INDEX IF NOT EXISTS turn_snapshots_namespace_turn_idx
    ON turn_snapshots (tenant_id, scenario_id, turn DESC);

-- Down Migration

DROP TABLE IF EXISTS turn_snapshots;
ALTER TABLE scenarios DROP COLUMN IF EXISTS turn_state;
ALTER TABLE scenarios DROP COLUMN IF EXISTS current_turn;
DROP TYPE IF EXISTS scenario_turn_state;

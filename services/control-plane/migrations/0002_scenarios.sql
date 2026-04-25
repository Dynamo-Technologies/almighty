-- 0002_scenarios.sql
-- Substrate for WS-301 (#17). WS-302 owns the turn_state machine and
-- current_turn fields; WS-301 will add the CRUD endpoints.

CREATE TABLE IF NOT EXISTS scenarios (
    scenario_id  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id    uuid NOT NULL REFERENCES tenants(tenant_id) ON DELETE RESTRICT,
    display_name text NOT NULL CHECK (length(display_name) > 0),
    status       text NOT NULL DEFAULT 'draft'
        CHECK (status IN ('draft', 'active', 'completed', 'archived')),

    -- Turn machine — owned by WS-302.
    current_turn int NOT NULL DEFAULT 0 CHECK (current_turn >= 0),
    turn_state   text NOT NULL DEFAULT 'open'
        CHECK (turn_state IN ('open', 'advancing', 'closed')),

    created_at   timestamptz NOT NULL DEFAULT now(),
    updated_at   timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS scenarios_tenant_idx ON scenarios (tenant_id);

DROP TRIGGER IF EXISTS scenarios_set_updated_at ON scenarios;
CREATE TRIGGER scenarios_set_updated_at
    BEFORE UPDATE ON scenarios
    FOR EACH ROW
    EXECUTE FUNCTION almighty_set_updated_at();

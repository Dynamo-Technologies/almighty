-- WS-301: tenant + scenario tables for the control plane.

-- Up Migration

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'tenant_status') THEN
        CREATE TYPE tenant_status AS ENUM ('active', 'archived');
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'scenario_status') THEN
        CREATE TYPE scenario_status AS ENUM ('draft', 'active', 'archived');
    END IF;
END$$;

CREATE TABLE IF NOT EXISTS tenants (
    tenant_id     uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    display_name  text NOT NULL CHECK (length(display_name) > 0),
    status        tenant_status NOT NULL DEFAULT 'active',
    created_at    timestamptz NOT NULL DEFAULT now(),
    updated_at    timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS tenants_status_idx ON tenants (status);

DROP TRIGGER IF EXISTS tenants_set_updated_at ON tenants;
CREATE TRIGGER tenants_set_updated_at
    BEFORE UPDATE ON tenants
    FOR EACH ROW EXECUTE FUNCTION almighty_set_updated_at();

CREATE TABLE IF NOT EXISTS scenarios (
    scenario_id   uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id     uuid NOT NULL REFERENCES tenants (tenant_id) ON DELETE RESTRICT,
    display_name  text NOT NULL CHECK (length(display_name) > 0),
    status        scenario_status NOT NULL DEFAULT 'draft',
    description   text NOT NULL DEFAULT '',
    created_at    timestamptz NOT NULL DEFAULT now(),
    updated_at    timestamptz NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, scenario_id)
);

CREATE INDEX IF NOT EXISTS scenarios_tenant_idx ON scenarios (tenant_id);
CREATE INDEX IF NOT EXISTS scenarios_tenant_status_idx ON scenarios (tenant_id, status);

DROP TRIGGER IF EXISTS scenarios_set_updated_at ON scenarios;
CREATE TRIGGER scenarios_set_updated_at
    BEFORE UPDATE ON scenarios
    FOR EACH ROW EXECUTE FUNCTION almighty_set_updated_at();

-- Down Migration

DROP TABLE IF EXISTS scenarios;
DROP TABLE IF EXISTS tenants;
DROP TYPE IF EXISTS scenario_status;
DROP TYPE IF EXISTS tenant_status;

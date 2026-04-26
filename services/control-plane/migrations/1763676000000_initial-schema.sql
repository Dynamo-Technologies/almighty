-- WS-301: applies the WS-101 entity/event DDL plus the gen_random_uuid()
-- extension. Source-of-truth doc: docs/schema/entity-event.md.

-- Up Migration

CREATE EXTENSION IF NOT EXISTS pgcrypto;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'force_affiliation') THEN
        CREATE TYPE force_affiliation AS ENUM ('BLUE', 'RED', 'WHITE', 'NEUTRAL');
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'entity_type_category') THEN
        CREATE TYPE entity_type_category AS ENUM (
            'PLATFORM', 'GROUND_UNIT', 'AIR_UNIT', 'MARITIME_UNIT',
            'SPACE_UNIT', 'NON_KINETIC', 'OTHER'
        );
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'officer_type') THEN
        CREATE TYPE officer_type AS ENUM (
            'SENSOR', 'EFFECTOR', 'MOVER', 'COMMUNICATOR', 'COMMANDER'
        );
    END IF;
END$$;

CREATE TABLE IF NOT EXISTS entities (
    entity_id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id              uuid NOT NULL,
    scenario_id            uuid NOT NULL,
    type_category          entity_type_category NOT NULL,
    type_subtype_ref       text NOT NULL CHECK (length(type_subtype_ref) > 0),
    display_name           text NOT NULL CHECK (length(display_name) > 0),
    force_affiliation      force_affiliation NOT NULL,
    position_lat_deg       double precision NOT NULL CHECK (position_lat_deg BETWEEN -90.0 AND 90.0),
    position_lon_deg       double precision NOT NULL CHECK (position_lon_deg BETWEEN -180.0 AND 180.0),
    position_alt_m         double precision NOT NULL,
    position_ecef_x_m      double precision NOT NULL,
    position_ecef_y_m      double precision NOT NULL,
    position_ecef_z_m      double precision NOT NULL,
    velocity_ecef_vx_mps   double precision NOT NULL,
    velocity_ecef_vy_mps   double precision NOT NULL,
    velocity_ecef_vz_mps   double precision NOT NULL,
    orientation_qw         double precision NOT NULL,
    orientation_qx         double precision NOT NULL,
    orientation_qy         double precision NOT NULL,
    orientation_qz         double precision NOT NULL,
    CONSTRAINT entities_orientation_unit_quat
        CHECK (
            abs(orientation_qw * orientation_qw
              + orientation_qx * orientation_qx
              + orientation_qy * orientation_qy
              + orientation_qz * orientation_qz - 1.0) < 1e-6
        ),
    capability_set_ref     text NOT NULL CHECK (length(capability_set_ref) > 0),
    created_at             timestamptz NOT NULL DEFAULT now(),
    updated_at             timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT entities_namespace_unique UNIQUE (tenant_id, scenario_id, entity_id)
);

CREATE INDEX IF NOT EXISTS entities_namespace_idx
    ON entities (tenant_id, scenario_id);
CREATE INDEX IF NOT EXISTS entities_namespace_force_idx
    ON entities (tenant_id, scenario_id, force_affiliation);

CREATE OR REPLACE FUNCTION almighty_set_updated_at()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS entities_set_updated_at ON entities;
CREATE TRIGGER entities_set_updated_at
    BEFORE UPDATE ON entities
    FOR EACH ROW EXECUTE FUNCTION almighty_set_updated_at();

CREATE TABLE IF NOT EXISTS events (
    event_id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id             uuid NOT NULL,
    scenario_id           uuid NOT NULL,
    turn                  int NOT NULL CHECK (turn >= 0),
    source_officer_type   officer_type NOT NULL,
    source_entity_id      uuid NOT NULL,
    action_verb           text NOT NULL CHECK (length(action_verb) > 0),
    payload               jsonb NOT NULL DEFAULT '{}'::jsonb,
    causal_predecessors   uuid[] NOT NULL DEFAULT '{}'::uuid[],
    ts                    timestamptz NOT NULL,
    created_at            timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT events_source_entity_in_namespace
        FOREIGN KEY (tenant_id, scenario_id, source_entity_id)
        REFERENCES entities (tenant_id, scenario_id, entity_id)
        ON DELETE RESTRICT
);

CREATE INDEX IF NOT EXISTS events_namespace_turn_idx
    ON events (tenant_id, scenario_id, turn);
CREATE INDEX IF NOT EXISTS events_namespace_source_idx
    ON events (tenant_id, scenario_id, source_entity_id);
CREATE INDEX IF NOT EXISTS events_causal_predecessors_gin_idx
    ON events USING gin (causal_predecessors);

-- Down Migration

DROP TABLE IF EXISTS events;
DROP TABLE IF EXISTS entities;
DROP FUNCTION IF EXISTS almighty_set_updated_at();
DROP TYPE IF EXISTS officer_type;
DROP TYPE IF EXISTS entity_type_category;
DROP TYPE IF EXISTS force_affiliation;

-- Almighty kernel — entities table DDL stub
-- Authoritative spec: docs/schema/entity-event.md (WS-101)
-- Migration owner: WS-301 (#17). This file is committed as a stub; no
-- migration runner has been wired yet.

-- Required extensions:
--   - pgcrypto OR uuid-ossp for gen_random_uuid()
--   - The control plane (WS-301) is responsible for ensuring extensions
--     exist on the per-tenant database before applying this DDL.

-- Enums shared with events.sql. Defined here so loading entities.sql
-- before events.sql works.

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'force_affiliation') THEN
        CREATE TYPE force_affiliation AS ENUM ('BLUE', 'RED', 'WHITE', 'NEUTRAL');
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'entity_type_category') THEN
        CREATE TYPE entity_type_category AS ENUM (
            'PLATFORM',
            'GROUND_UNIT',
            'AIR_UNIT',
            'MARITIME_UNIT',
            'SPACE_UNIT',
            'NON_KINETIC',
            'OTHER'
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

    -- Geodetic position (WGS-84)
    position_lat_deg       double precision NOT NULL CHECK (position_lat_deg BETWEEN -90.0 AND 90.0),
    position_lon_deg       double precision NOT NULL CHECK (position_lon_deg BETWEEN -180.0 AND 180.0),
    position_alt_m         double precision NOT NULL,

    -- Earth-centered earth-fixed position (meters)
    position_ecef_x_m      double precision NOT NULL,
    position_ecef_y_m      double precision NOT NULL,
    position_ecef_z_m      double precision NOT NULL,

    -- ECEF velocity (m/s)
    velocity_ecef_vx_mps   double precision NOT NULL,
    velocity_ecef_vy_mps   double precision NOT NULL,
    velocity_ecef_vz_mps   double precision NOT NULL,

    -- Unit quaternion orientation
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

    -- Capability profile FK (resolved at WS-106 land time)
    capability_set_ref     text NOT NULL CHECK (length(capability_set_ref) > 0),

    created_at             timestamptz NOT NULL DEFAULT now(),
    updated_at             timestamptz NOT NULL DEFAULT now(),

    -- (tenant_id, scenario_id, entity_id) is the natural composite key for
    -- cross-table FKs (events.source_entity_id references this triple).
    CONSTRAINT entities_namespace_unique UNIQUE (tenant_id, scenario_id, entity_id)
);

-- Namespace scan — every read parameterizes on (tenant_id, scenario_id).
CREATE INDEX IF NOT EXISTS entities_namespace_idx
    ON entities (tenant_id, scenario_id);

-- EXCON sidebar listings filter by friendly side within the namespace.
CREATE INDEX IF NOT EXISTS entities_namespace_force_idx
    ON entities (tenant_id, scenario_id, force_affiliation);

-- Maintain updated_at on row update. Trigger function shared with events.
CREATE OR REPLACE FUNCTION almighty_set_updated_at()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS entities_set_updated_at ON entities;
CREATE TRIGGER entities_set_updated_at
    BEFORE UPDATE ON entities
    FOR EACH ROW
    EXECUTE FUNCTION almighty_set_updated_at();

-- TODO (WS-301): row-level security policies parameterized on tenant_id +
-- scenario_id pulled from the JWT-derived session GUC.

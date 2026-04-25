-- Almighty kernel — events table DDL stub
-- Authoritative spec: docs/schema/entity-event.md (WS-101)
-- Migration owner: WS-301 (#17). This file is committed as a stub; no
-- migration runner has been wired yet.

-- Depends on: entities.sql (must be loaded first — defines force_affiliation
-- and the entities table this references).

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'officer_type') THEN
        CREATE TYPE officer_type AS ENUM (
            'SENSOR',
            'EFFECTOR',
            'MOVER',
            'COMMUNICATOR',
            'COMMANDER'
        );
    END IF;
END$$;

CREATE TABLE IF NOT EXISTS events (
    event_id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id             uuid NOT NULL,
    scenario_id           uuid NOT NULL,
    turn                  int NOT NULL CHECK (turn >= 0),

    source_officer_type   officer_type NOT NULL,
    source_entity_id      uuid NOT NULL,

    -- action_verb is the 20-verb vocabulary from WS-105.
    -- The CHECK constraint is intentionally absent here — WS-105 (#9) will
    -- ALTER TABLE ADD CONSTRAINT once the canonical verb list is locked.
    -- For now, application-level enforcement (WS-402 tools) is the gate.
    action_verb           text NOT NULL CHECK (length(action_verb) > 0),

    payload               jsonb NOT NULL DEFAULT '{}'::jsonb,

    causal_predecessors   uuid[] NOT NULL DEFAULT '{}'::uuid[],

    ts                    timestamptz NOT NULL,
    created_at            timestamptz NOT NULL DEFAULT now(),

    -- Cross-table FK: source_entity_id must exist in the SAME
    -- (tenant_id, scenario_id) namespace.
    CONSTRAINT events_source_entity_in_namespace
        FOREIGN KEY (tenant_id, scenario_id, source_entity_id)
        REFERENCES entities (tenant_id, scenario_id, entity_id)
        ON DELETE RESTRICT
);

-- Namespace + turn scan — drives the AAR replay timeline (WS-506) and the
-- turn-controller snapshot fetch (WS-302).
CREATE INDEX IF NOT EXISTS events_namespace_turn_idx
    ON events (tenant_id, scenario_id, turn);

-- "All events emitted by this entity" — used by the override gateway
-- (WS-303) when applying per-agent-per-turn policies.
CREATE INDEX IF NOT EXISTS events_namespace_source_idx
    ON events (tenant_id, scenario_id, source_entity_id);

-- Causal predecessor lookup — used by the PyRapide DAG (WS-104) for
-- ancestor/descendant traversals.
CREATE INDEX IF NOT EXISTS events_causal_predecessors_gin_idx
    ON events USING gin (causal_predecessors);

-- Predecessor-cross-scenario validation. Postgres cannot express this as a
-- declarative FK on an array column, so it lands as a trigger. Disabled by
-- default — WS-104 (#8) flips it on after benchmarking the per-event cost.
CREATE OR REPLACE FUNCTION events_validate_predecessors()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    bad_count int;
BEGIN
    IF NEW.causal_predecessors IS NULL OR array_length(NEW.causal_predecessors, 1) IS NULL THEN
        RETURN NEW;
    END IF;

    SELECT count(*)
      INTO bad_count
      FROM events e
     WHERE e.event_id = ANY (NEW.causal_predecessors)
       AND (e.tenant_id <> NEW.tenant_id OR e.scenario_id <> NEW.scenario_id);

    IF bad_count > 0 THEN
        RAISE EXCEPTION 'causal_predecessors must reference events in the same (tenant_id, scenario_id) namespace; % offending entries', bad_count;
    END IF;

    -- Detect missing predecessor IDs (referenced but not in events table at all).
    SELECT cardinality(NEW.causal_predecessors) - count(*)
      INTO bad_count
      FROM events e
     WHERE e.event_id = ANY (NEW.causal_predecessors);

    IF bad_count > 0 THEN
        RAISE EXCEPTION 'causal_predecessors include % event_ids that do not exist', bad_count;
    END IF;

    RETURN NEW;
END;
$$;

-- Trigger declaration intentionally commented out. WS-104 owns the
-- decision to enable it after measuring the write-path cost. Until then,
-- the kernel commit API enforces the invariant in application code.
-- DROP TRIGGER IF EXISTS events_validate_predecessors_trg ON events;
-- CREATE TRIGGER events_validate_predecessors_trg
--     BEFORE INSERT ON events
--     FOR EACH ROW
--     EXECUTE FUNCTION events_validate_predecessors();

-- TODO (WS-105): ALTER TABLE events ADD CONSTRAINT events_action_verb_chk
--     CHECK (action_verb IN ('detect', 'track', 'classify', 'lose_track',
--                            'engage', 'suppress', 'destroy', 'disable',
--                            'move_to', 'follow_route', 'halt', 'assume_posture',
--                            'send', 'relay', 'jam', 'report',
--                            'issue_order', 'request_support', 'delegate', 'escalate'));

-- TODO (WS-301): row-level security policies parameterized on tenant_id +
-- scenario_id pulled from the JWT-derived session GUC.

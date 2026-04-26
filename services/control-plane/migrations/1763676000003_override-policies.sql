-- WS-303: override gateway and policy plane.
-- Source-of-truth doc: docs/dummy-instructions.md WS-303 + this PR.
--
-- Two tables:
--   override_policies   — authored rules ('per-event'/'per-agent-per-turn'/'per-turn')
--                         that gate uncommitted agent-emitted events.
--   override_decisions  — append-only audit log of every gateway firing,
--                         auto and manual. Joined with events on
--                         (tenant_id, scenario_id, ts) by AAR (WS-506).
--
-- TTL model: a policy is valid in turn T if
--   created_in_turn ≤ T ≤ created_in_turn + ttl_turns
-- so ttl_turns=0 means "single turn" (the turn it was authored in).
--
-- Composability: per-event > per-agent-per-turn > per-turn. The evaluator
-- in src/override-gateway.ts encodes this; the schema permits all three
-- to coexist.

-- Up Migration

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'override_scope') THEN
        CREATE TYPE override_scope AS ENUM (
            'per-event',
            'per-agent-per-turn',
            'per-turn'
        );
    END IF;
END$$;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'override_action') THEN
        CREATE TYPE override_action AS ENUM (
            'review',
            'auto-approve',
            'auto-block'
        );
    END IF;
END$$;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'override_policy_status') THEN
        CREATE TYPE override_policy_status AS ENUM (
            'active',
            'revoked'
        );
    END IF;
END$$;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'override_decision_outcome') THEN
        CREATE TYPE override_decision_outcome AS ENUM (
            'auto-approve',
            'auto-block',
            'review-pending',
            'review-approved',
            'review-blocked',
            'default-review'
        );
    END IF;
END$$;

-- ---------- override_policies ----------

CREATE TABLE IF NOT EXISTS override_policies (
    policy_id        uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id        uuid NOT NULL REFERENCES tenants (tenant_id) ON DELETE RESTRICT,
    scenario_id      uuid NOT NULL,
    scope            override_scope NOT NULL,
    -- Discrete polymorphic target columns. Exactly one combination is set
    -- per scope; the CHECK below enforces it.
    event_id         uuid,                       -- per-event scope only
    agent_entity_id  uuid,                       -- per-agent-per-turn scope only
                                                 -- ("agent" = the entity acting through an officer
                                                 --  per WS-101 events.source_entity_id semantics).
    target_turn      int CHECK (target_turn IS NULL OR target_turn >= 0),
                                                 -- per-agent-per-turn AND per-turn scopes
    action           override_action NOT NULL,
    ttl_turns        int NOT NULL DEFAULT 0 CHECK (ttl_turns >= 0),
    created_in_turn  int NOT NULL CHECK (created_in_turn >= 0),
    rationale        text NOT NULL DEFAULT '',
    created_by       uuid NOT NULL,              -- white cell operator id (sub claim)
    status           override_policy_status NOT NULL DEFAULT 'active',
    created_at       timestamptz NOT NULL DEFAULT now(),
    updated_at       timestamptz NOT NULL DEFAULT now(),

    CONSTRAINT override_policies_scenario_fk
        FOREIGN KEY (tenant_id, scenario_id)
        REFERENCES scenarios (tenant_id, scenario_id)
        ON DELETE RESTRICT,

    -- Per-scope shape constraints. Per-event needs event_id only;
    -- per-agent-per-turn needs (agent_entity_id, target_turn);
    -- per-turn needs target_turn only.
    CONSTRAINT override_policies_scope_shape CHECK (
        (scope = 'per-event'
            AND event_id IS NOT NULL
            AND agent_entity_id IS NULL
            AND target_turn IS NULL)
        OR (scope = 'per-agent-per-turn'
            AND event_id IS NULL
            AND agent_entity_id IS NOT NULL
            AND target_turn IS NOT NULL)
        OR (scope = 'per-turn'
            AND event_id IS NULL
            AND agent_entity_id IS NULL
            AND target_turn IS NOT NULL)
    )
);

-- Lookup-chain indexes. Evaluator hits these in priority order:
--   per-event   → exact event_id lookup
--   per-agent-per-turn → (agent_entity_id, target_turn) lookup
--   per-turn    → (target_turn) lookup
-- All three are namespace-scoped on (tenant_id, scenario_id) and filter
-- on status='active'.
CREATE INDEX IF NOT EXISTS override_policies_per_event_idx
    ON override_policies (tenant_id, scenario_id, event_id)
    WHERE status = 'active' AND scope = 'per-event';

CREATE INDEX IF NOT EXISTS override_policies_per_agent_turn_idx
    ON override_policies (tenant_id, scenario_id, agent_entity_id, target_turn)
    WHERE status = 'active' AND scope = 'per-agent-per-turn';

CREATE INDEX IF NOT EXISTS override_policies_per_turn_idx
    ON override_policies (tenant_id, scenario_id, target_turn)
    WHERE status = 'active' AND scope = 'per-turn';

-- General namespace index for list endpoints.
CREATE INDEX IF NOT EXISTS override_policies_namespace_idx
    ON override_policies (tenant_id, scenario_id, created_at DESC);

-- ---------- override_decisions ----------

CREATE TABLE IF NOT EXISTS override_decisions (
    decision_id      uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id        uuid NOT NULL REFERENCES tenants (tenant_id) ON DELETE RESTRICT,
    scenario_id      uuid NOT NULL,
    event_id         uuid NOT NULL,             -- the event being adjudicated
    turn             int NOT NULL CHECK (turn >= 0),
    outcome          override_decision_outcome NOT NULL,
    -- The matching policy when one fired; NULL when the default-review
    -- path applied (no policy in scope) OR when a manual decision was made
    -- with no underlying matching policy.
    policy_id        uuid REFERENCES override_policies (policy_id) ON DELETE SET NULL,
    matched_scope    override_scope,            -- redundant w/ policy.scope but persists after fork-revoke
    decided_by       uuid,                      -- NULL for auto outcomes; set for review-* / manual
    rationale        text NOT NULL DEFAULT '',
    decided_at       timestamptz NOT NULL DEFAULT now(),

    CONSTRAINT override_decisions_scenario_fk
        FOREIGN KEY (tenant_id, scenario_id)
        REFERENCES scenarios (tenant_id, scenario_id)
        ON DELETE RESTRICT
);

CREATE INDEX IF NOT EXISTS override_decisions_namespace_idx
    ON override_decisions (tenant_id, scenario_id, decided_at DESC);

CREATE INDEX IF NOT EXISTS override_decisions_event_idx
    ON override_decisions (tenant_id, scenario_id, event_id);

-- Down Migration

DROP TABLE IF EXISTS override_decisions;
DROP TABLE IF EXISTS override_policies;
DROP TYPE IF EXISTS override_decision_outcome;
DROP TYPE IF EXISTS override_policy_status;
DROP TYPE IF EXISTS override_action;
DROP TYPE IF EXISTS override_scope;

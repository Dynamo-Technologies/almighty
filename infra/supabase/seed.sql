-- Hackathon demo seed.
-- Idempotent: re-runnable without duplicates.

BEGIN;

-- 1. Demo tenant ------------------------------------------------------------
INSERT INTO tenants (tenant_id, display_name)
VALUES ('00000000-0000-4d00-8000-000000000001', 'Demo (hackathon)')
ON CONFLICT (tenant_id) DO NOTHING;

-- 2. Nashville Cumberland River crossing scenario --------------------------
INSERT INTO scenarios (
    tenant_id, scenario_id, display_name,
    status, current_turn, turn_state, description
)
VALUES (
    '00000000-0000-4d00-8000-000000000001',
    '00000000-0000-4101-8000-000000000001',
    'Nashville Cumberland River crossing',
    'active', 0, 'open',
    'Hackathon demo scenario. Six-turn forced river crossing; only turn 1 runs in the live demo.'
)
ON CONFLICT (tenant_id, scenario_id) DO UPDATE
   SET current_turn = 0,
       turn_state   = 'open',
       status       = 'active';

-- 3. Auto-approve override policies for all six turns ----------------------
-- The demo hides the manual-review flow (spec §7). Six per-turn rules,
-- one per turn, action='auto-approve'. Re-runnable: revoke prior demo
-- policies first, then re-insert.
UPDATE override_policies
   SET status = 'revoked'
 WHERE tenant_id   = '00000000-0000-4d00-8000-000000000001'
   AND scenario_id = '00000000-0000-4101-8000-000000000001'
   AND status      = 'active';

INSERT INTO override_policies (
    tenant_id, scenario_id, scope, target_turn,
    action, ttl_turns, created_in_turn, rationale, created_by
)
SELECT
    '00000000-0000-4d00-8000-000000000001'::uuid,
    '00000000-0000-4101-8000-000000000001'::uuid,
    'per-turn'::override_scope,
    t,
    'auto-approve'::override_action,
    6,
    0,
    'Demo seed: auto-approve all events. Manual review out of scope (spec §7).',
    '00000000-0000-4d00-8000-000000000099'::uuid -- synthetic white-cell operator id
FROM generate_series(1, 6) AS t;

COMMIT;

-- Verification queries (run after the seed):
--   SELECT current_turn, turn_state FROM scenarios
--    WHERE scenario_id = '00000000-0000-4101-8000-000000000001';
--   SELECT scope, target_turn, action FROM override_policies
--    WHERE scenario_id = '00000000-0000-4101-8000-000000000001'
--      AND status = 'active'
--    ORDER BY target_turn;

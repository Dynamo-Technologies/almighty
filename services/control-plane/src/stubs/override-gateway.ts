/**
 * WS-303 stub.
 *
 * The real override gateway (#19) intercepts agent-emitted events and
 * applies per-event / per-agent-per-turn / per-turn policies before they
 * commit. Inside the turn-advance flow it's the third step (after
 * agent runtime, before snapshot). Stubbed as a no-op for WS-302.
 */

// TODO WS-303: replace stub with real call into the override gateway.
export async function applyOverrides(input: {
  tenantId: string;
  scenarioId: string;
  turn: number;
}): Promise<{ ok: true; processedEvents: number }> {
  void input;
  return { ok: true, processedEvents: 0 };
}

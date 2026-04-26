/**
 * WS-401 stub.
 *
 * The real between-turn agent runtime (#21) will run blue → red → white
 * crews and signal completion back to the turn controller. Until that
 * lands, this stub just sleeps briefly and returns success so the
 * turn-advance flow exercises end-to-end timing.
 */

// TODO WS-401: replace stub with real call into the agent runtime.
export async function runBetweenTurnAgents(input: {
  tenantId: string;
  scenarioId: string;
  turn: number;
}): Promise<{ ok: true; durationMs: number }> {
  const startedAt = Date.now();
  await new Promise<void>((resolve) => setTimeout(resolve, 100));
  void input;
  return { ok: true, durationMs: Date.now() - startedAt };
}

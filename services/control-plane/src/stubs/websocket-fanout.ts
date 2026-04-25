/**
 * WS-304 stub.
 *
 * The real WebSocket fan-out (#20) publishes turn_state events on the
 * tenant-scoped channel. Step 6 of the turn-advance flow emits a
 * turn_state notification once the new turn opens. Stubbed as a no-op
 * for WS-302; the call site captures all relevant fields so wiring this
 * up to the real fan-out is one swap.
 */

export interface TurnStateNotification {
  tenantId: string;
  scenarioId: string;
  turn: number;
  state: "open" | "advancing" | "closed";
  notifiedAt: string;
}

// TODO WS-304: replace stub with real publish onto the turn_state channel.
export async function publishTurnState(
  notification: TurnStateNotification,
): Promise<{ ok: true; channel: string }> {
  return {
    ok: true,
    channel: `tenant:${notification.tenantId}:turn_state`,
  };
}

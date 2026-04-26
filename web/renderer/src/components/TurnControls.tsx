import { useEffect, useState } from "react";
import { fetchTurnState, type TurnSnapshot } from "../api/mock";
import { advanceTurn } from "../api/whiteCell";
import { TurnState } from "./TurnState";

export function TurnControls() {
  const [snapshot, setSnapshot] = useState<TurnSnapshot | null>(null);
  const [advancing, setAdvancing] = useState(false);
  const [lastAdvanced, setLastAdvanced] = useState<string | null>(null);

  useEffect(() => {
    void fetchTurnState().then(setSnapshot);
  }, []);

  const onAdvance = async () => {
    if (!snapshot || advancing) return;
    setAdvancing(true);
    setSnapshot({ ...snapshot, turn_state: "advancing" });
    try {
      const result = await advanceTurn();
      setSnapshot({
        current_turn: result.next_turn,
        turn_state: "open",
        last_advanced_at: result.snapshot_at,
      });
      setLastAdvanced(result.snapshot_at);
    } finally {
      setAdvancing(false);
    }
  };

  const isAdvancing = snapshot?.turn_state === "advancing" || advancing;

  return (
    <section className="white-cell-section">
      <h2>Turn advancement</h2>
      <div className="turn-controls__row">
        <TurnState snapshot={snapshot} />
        <button
          type="button"
          className="white-cell-btn white-cell-btn--primary"
          onClick={onAdvance}
          disabled={isAdvancing}
        >
          {isAdvancing ? "advancing…" : "Advance turn"}
        </button>
      </div>
      <p className="white-cell-hint">
        Last snapshot: <code>{lastAdvanced ?? snapshot?.last_advanced_at ?? "—"}</code>
      </p>
    </section>
  );
}

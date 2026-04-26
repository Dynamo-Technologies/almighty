import type { TurnSnapshot } from "../api/mock";

type TurnStateProps = {
  snapshot: TurnSnapshot | null;
};

export function TurnState({ snapshot }: TurnStateProps) {
  if (!snapshot) return <div className="turn-state turn-state--loading">turn: …</div>;
  const isAdvancing = snapshot.turn_state === "advancing";
  return (
    <div className={`turn-state ${isAdvancing ? "turn-state--advancing" : "turn-state--open"}`}>
      <span className="turn-state__num">turn {snapshot.current_turn}</span>
      <span className="turn-state__dot" />
      <span className="turn-state__label">{snapshot.turn_state.toUpperCase()}</span>
    </div>
  );
}

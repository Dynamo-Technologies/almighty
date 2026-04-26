import type { DagEvent, OverrideDecision } from "../api/aar";

type Row =
  | { kind: "event"; ts: string; data: DagEvent }
  | { kind: "decision"; ts: string; data: OverrideDecision };

type EventLogProps = {
  events: DagEvent[];
  overrideDecisions: OverrideDecision[];
  onSeek: (ts: string) => void;
};

export function EventLog({ events, overrideDecisions, onSeek }: EventLogProps) {
  const rows: Row[] = [
    ...events.map<Row>((e) => ({ kind: "event", ts: e.ts, data: e })),
    ...overrideDecisions.map<Row>((d) => ({ kind: "decision", ts: d.ts, data: d })),
  ].sort((a, b) => a.ts.localeCompare(b.ts));

  return (
    <div className="event-log">
      <h2>Event log</h2>
      {rows.length === 0 && <p className="white-cell-hint">No events captured.</p>}
      <ul>
        {rows.map((row) => (
          <li
            key={row.kind === "event" ? row.data.event_id : row.data.decision_id}
            className={`event-log__row event-log__row--${row.kind}`}
            onClick={() => onSeek(row.ts)}
            title="Click to seek timeline"
          >
            <span className="event-log__time">{shortTime(row.ts)}</span>
            {row.kind === "event" ? (
              <>
                <span className="event-log__verb"><code>{row.data.action_verb}</code></span>
                <span className="event-log__officer">{row.data.source_officer_type}</span>
                <span className="event-log__turn">turn {row.data.turn}</span>
              </>
            ) : (
              <>
                <span className={`event-log__decision pill pill--${row.data.action}`}>{row.data.action}</span>
                <span className="event-log__decision-meta">{row.data.scope} → {row.data.target_id}</span>
              </>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}

function shortTime(iso: string): string {
  return iso.slice(11, 19);
}

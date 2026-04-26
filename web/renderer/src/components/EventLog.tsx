import { useCallback, useRef } from "react";
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
  const rowRefs = useRef<Map<string, HTMLLIElement>>(new Map());
  const eventById = new Map(events.map((e) => [e.event_id, e]));

  const handleParentClick = useCallback((parentId: string) => {
    const node = rowRefs.current.get(parentId);
    if (!node) return;
    node.scrollIntoView({ behavior: "smooth", block: "center" });
    node.classList.add("event-log__row--flash");
    window.setTimeout(() => node.classList.remove("event-log__row--flash"), 1200);
  }, []);

  const rows: Row[] = [
    ...events.map<Row>((e) => ({ kind: "event", ts: e.ts, data: e })),
    ...overrideDecisions.map<Row>((d) => ({ kind: "decision", ts: d.ts, data: d })),
  ].sort((a, b) => a.ts.localeCompare(b.ts));

  return (
    <div className="event-log">
      <h2>Event log</h2>
      {rows.length === 0 && <p className="white-cell-hint">No events captured.</p>}
      <ul>
        {rows.map((row) => {
          const id = row.kind === "event" ? row.data.event_id : row.data.decision_id;
          return (
            <li
              key={id}
              ref={(el) => {
                if (el) rowRefs.current.set(id, el);
                else rowRefs.current.delete(id);
              }}
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
                  <CausalChips
                    predecessors={row.data.causal_predecessors}
                    eventById={eventById}
                    onParentClick={handleParentClick}
                  />
                </>
              ) : (
                <>
                  <span className={`event-log__decision pill pill--${row.data.action}`}>
                    {row.data.action}
                  </span>
                  <span className="event-log__decision-meta">
                    {row.data.scope} → {row.data.target_id}
                  </span>
                </>
              )}
            </li>
          );
        })}
      </ul>
    </div>
  );
}

function CausalChips({
  predecessors,
  eventById,
  onParentClick,
}: {
  predecessors: string[];
  eventById: Map<string, DagEvent>;
  onParentClick: (id: string) => void;
}) {
  if (!predecessors || predecessors.length === 0) return null;
  return (
    <span className="event-log__causal" onClick={(e) => e.stopPropagation()}>
      <span className="event-log__causal-arrow">← caused by</span>
      {predecessors.map((pid) => {
        const parent = eventById.get(pid);
        const label = parent ? parent.action_verb : `${pid.slice(0, 8)}…`;
        return (
          <button
            key={pid}
            type="button"
            className="event-log__causal-chip"
            onClick={() => onParentClick(pid)}
            title={`Jump to event ${pid.slice(0, 8)}…`}
          >
            <code>{label}</code>
          </button>
        );
      })}
    </span>
  );
}

function shortTime(iso: string): string {
  return iso.slice(11, 19);
}

import type { EntitySummary } from "../api/mock";

type EntitySidebarProps = {
  entities: EntitySummary[];
  selectedId: string | null;
  onSelect: (id: string | null) => void;
  loading: boolean;
};

export function EntitySidebar({ entities, selectedId, onSelect, loading }: EntitySidebarProps) {
  return (
    <div className="entity-sidebar">
      <h2>Entities under command</h2>
      {loading && <p className="entity-sidebar__loading">loading…</p>}
      <ul>
        {entities.map((e) => (
          <li
            key={e.entity_id}
            className={`entity-sidebar__row ${selectedId === e.entity_id ? "is-selected" : ""}`}
            onClick={() => onSelect(selectedId === e.entity_id ? null : e.entity_id)}
          >
            <div className="entity-sidebar__name">{e.display_name}</div>
            <div className="entity-sidebar__meta">{e.type_subtype_ref}</div>
            <div className="entity-sidebar__coord">
              {e.position_lat_deg.toFixed(4)}, {e.position_lon_deg.toFixed(4)}
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}

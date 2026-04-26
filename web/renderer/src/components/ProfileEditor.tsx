import { useEffect, useState } from "react";
import { type CapabilityProfile, listProfiles, saveProfile } from "../api/whiteCell";
import type { TurnSnapshot } from "../api/mock";

type ProfileEditorProps = {
  turn: TurnSnapshot | null;
};

export function ProfileEditor({ turn }: ProfileEditorProps) {
  const [profiles, setProfiles] = useState<CapabilityProfile[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [draftJson, setDraftJson] = useState<string>("");
  const [parseError, setParseError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [savedAt, setSavedAt] = useState<string | null>(null);

  // Profile authoring is pre-scenario only; locked once turn >= 1 per WS-106
  // versioning rule. We surface the lock here but the stub still accepts the
  // call so the demo loop is exercisable.
  const locked = (turn?.current_turn ?? 0) >= 1;

  useEffect(() => {
    void listProfiles().then((p) => {
      setProfiles(p);
      if (p.length > 0) {
        setSelectedId(p[0].profile_id);
        setDraftJson(JSON.stringify(p[0].body, null, 2));
      }
    });
  }, []);

  const select = (id: string) => {
    setSelectedId(id);
    const p = profiles.find((q) => q.profile_id === id);
    if (p) setDraftJson(JSON.stringify(p.body, null, 2));
    setParseError(null);
    setSavedAt(null);
  };

  const onSave = async () => {
    const profile = profiles.find((q) => q.profile_id === selectedId);
    if (!profile) return;
    let parsed: Record<string, unknown>;
    try {
      parsed = JSON.parse(draftJson);
    } catch (err) {
      setParseError(err instanceof Error ? err.message : String(err));
      return;
    }
    setParseError(null);
    setSaving(true);
    try {
      const updated = await saveProfile({ ...profile, body: parsed });
      setProfiles((prev) => prev.map((q) => (q.profile_id === updated.profile_id ? updated : q)));
      setSavedAt(new Date().toISOString());
    } finally {
      setSaving(false);
    }
  };

  return (
    <section className="white-cell-section">
      <h2>Capability profiles</h2>
      {locked && (
        <p className="white-cell-hint white-cell-hint--warn">
          Scenario at turn {turn?.current_turn} — profile authoring is locked per WS-106 versioning rule. Edits forking a new profile_id only.
        </p>
      )}
      <div className="profile-editor__row">
        <select value={selectedId ?? ""} onChange={(e) => select(e.target.value)} className="profile-editor__select">
          {profiles.map((p) => (
            <option key={p.profile_id} value={p.profile_id}>
              {p.display_name} (v{p.version})
            </option>
          ))}
        </select>
        <button
          type="button"
          className="white-cell-btn white-cell-btn--primary"
          onClick={onSave}
          disabled={saving || !selectedId}
        >
          {saving ? "saving…" : "Save profile"}
        </button>
      </div>
      <textarea
        className="profile-editor__textarea"
        value={draftJson}
        onChange={(e) => setDraftJson(e.target.value)}
        spellCheck={false}
        rows={14}
      />
      {parseError && <p className="white-cell-hint white-cell-hint--err">JSON parse error: {parseError}</p>}
      {savedAt && !parseError && <p className="white-cell-hint">Saved at {savedAt}</p>}
    </section>
  );
}

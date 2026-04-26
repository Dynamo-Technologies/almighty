import { useEffect, useMemo, useState } from "react";
import {
  type OfficerType,
  VERBS,
  type VerbField,
  type VerbSpec,
  getVerb,
  verbsByOfficer,
} from "../verbs/registry";

const OFFICER_TYPES: readonly OfficerType[] = ["Sensor", "Effector", "Mover", "Communicator", "Commander"];

export type FormValues = Record<string, string | number | boolean | null>;

type OrderFormProps = {
  /** Officers this console can issue orders for. EXCON blue/red can do all five; refine later if needed. */
  allowedOfficers?: readonly OfficerType[];
  /** Locked when the turn is advancing. */
  locked: boolean;
  onDraft: (verb: VerbSpec | null, values: FormValues) => void;
  onSubmit: (verb: VerbSpec, values: FormValues) => void | Promise<void>;
  submitting: boolean;
};

export function OrderForm({
  allowedOfficers = OFFICER_TYPES,
  locked,
  onDraft,
  onSubmit,
  submitting,
}: OrderFormProps) {
  const [officer, setOfficer] = useState<OfficerType>(allowedOfficers[0]);
  const verbsForOfficer = useMemo(() => verbsByOfficer(officer), [officer]);
  const [verbName, setVerbName] = useState<string>(verbsForOfficer[0]?.verb ?? "");
  const verb = getVerb(verbName);
  const [values, setValues] = useState<FormValues>({});

  // When the verb changes, reset values and seed defaults where useful.
  useEffect(() => {
    setValues({});
  }, [verbName]);

  // Surface the current draft upward (for ghost preview / debug).
  useEffect(() => {
    onDraft(verb ?? null, values);
  }, [verb, values, onDraft]);

  const setField = (name: string, value: string | number | boolean | null) => {
    setValues((prev) => ({ ...prev, [name]: value }));
  };

  const validate = (): { ok: boolean; reason?: string } => {
    if (!verb) return { ok: false, reason: "no verb selected" };
    for (const f of verb.fields) {
      if (!f.required) continue;
      const v = values[f.name];
      if (v === undefined || v === null || v === "") return { ok: false, reason: `${f.name} required` };
    }
    return { ok: true };
  };
  const validity = validate();

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!validity.ok || !verb || locked) return;
    void onSubmit(verb, values);
  };

  return (
    <form className="order-form" onSubmit={handleSubmit}>
      <h2>Order entry</h2>

      <label className="order-form__row">
        <span>Officer</span>
        <select
          value={officer}
          disabled={locked}
          onChange={(e) => {
            const next = e.target.value as OfficerType;
            setOfficer(next);
            const firstVerb = verbsByOfficer(next)[0]?.verb ?? "";
            setVerbName(firstVerb);
          }}
        >
          {allowedOfficers.map((o) => (
            <option key={o} value={o}>
              {o}
            </option>
          ))}
        </select>
      </label>

      <label className="order-form__row">
        <span>Verb</span>
        <select value={verbName} disabled={locked} onChange={(e) => setVerbName(e.target.value)}>
          {verbsForOfficer.map((v) => (
            <option key={v.verb} value={v.verb}>
              {v.verb}
            </option>
          ))}
        </select>
      </label>

      {verb?.fields.length === 0 && (
        <p className="order-form__hint">
          <em>{verb.verb}</em> has no parameters.
        </p>
      )}

      {verb?.fields.map((f) => (
        <FieldInput
          key={f.name}
          field={f}
          value={values[f.name] ?? ""}
          disabled={locked}
          onChange={(v) => setField(f.name, v)}
        />
      ))}

      {locked && <p className="order-form__locked">Turn is advancing — orders locked.</p>}

      <button
        type="submit"
        className="order-form__submit"
        disabled={locked || submitting || !validity.ok}
      >
        {submitting ? "submitting…" : "Issue order"}
      </button>
      {!validity.ok && validity.reason && (
        <p className="order-form__validity">{validity.reason}</p>
      )}
    </form>
  );
}

function FieldInput({
  field,
  value,
  disabled,
  onChange,
}: {
  field: VerbField;
  value: string | number | boolean | null;
  disabled: boolean;
  onChange: (v: string | number | boolean | null) => void;
}) {
  const label = (
    <span>
      {field.name}
      {field.units && <span className="order-form__units"> ({field.units})</span>}
      {field.required && <span className="order-form__required"> *</span>}
    </span>
  );

  if (field.type === "enum") {
    return (
      <label className="order-form__row">
        {label}
        <select
          value={String(value ?? "")}
          disabled={disabled}
          onChange={(e) => onChange(e.target.value || null)}
        >
          <option value="">—</option>
          {field.enumValues?.map((v) => (
            <option key={v} value={v}>
              {v}
            </option>
          ))}
        </select>
      </label>
    );
  }

  if (field.type === "bool") {
    return (
      <label className="order-form__row">
        {label}
        <input
          type="checkbox"
          checked={Boolean(value)}
          disabled={disabled}
          onChange={(e) => onChange(e.target.checked)}
        />
      </label>
    );
  }

  if (field.type === "number") {
    return (
      <label className="order-form__row">
        {label}
        <input
          type="number"
          value={value === null || value === undefined ? "" : String(value)}
          disabled={disabled}
          min={field.min}
          max={field.max}
          step="any"
          onChange={(e) => onChange(e.target.value === "" ? null : Number(e.target.value))}
        />
      </label>
    );
  }

  // string / uuid / object → text input. object accepts JSON; renderer doesn't parse here.
  return (
    <label className="order-form__row">
      {label}
      <input
        type="text"
        value={String(value ?? "")}
        disabled={disabled}
        placeholder={field.description ?? ""}
        onChange={(e) => onChange(e.target.value)}
      />
    </label>
  );
}

export const ALL_VERBS_COUNT = VERBS.length;

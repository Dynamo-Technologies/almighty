export type DemoKey = "catalog" | "vignette";

export const DEMO_URLS: Record<DemoKey, string> = {
  catalog: "/czml/effect-catalog.czml",
  vignette: "/czml/nashville-vignette.czml",
};

const DEMO_LABELS: Record<DemoKey, string> = {
  catalog: "Effect catalog",
  vignette: "Nashville vignette",
};

type CzmlSelectorProps = {
  value: DemoKey | null;
  onChange: (next: DemoKey | null) => void;
};

export function CzmlSelector({ value, onChange }: CzmlSelectorProps) {
  return (
    <div className="czml-selector" role="radiogroup" aria-label="Static CZML demo">
      <button
        type="button"
        className={`czml-selector__btn ${value === null ? "is-active" : ""}`}
        onClick={() => onChange(null)}
      >
        None
      </button>
      {(Object.keys(DEMO_URLS) as DemoKey[]).map((key) => (
        <button
          type="button"
          key={key}
          className={`czml-selector__btn ${value === key ? "is-active" : ""}`}
          onClick={() => onChange(key)}
        >
          {DEMO_LABELS[key]}
        </button>
      ))}
    </div>
  );
}

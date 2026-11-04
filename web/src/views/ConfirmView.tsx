import { useEffect, useState } from "react";
import { api, type Case, type FieldName, type Item } from "../api";
import { Says, type Mood } from "../Saarthi";

const FIELD_LABELS: [FieldName, string][] = [
  ["dose", "How much"],
  ["frequency", "How often"],
  ["duration", "For how long"],
  ["instructions", "Extra note"],
  ["route", "How it's taken"],
  ["name", "Medicine name"],
];
const REQUIRED: FieldName[] = ["name", "dose", "frequency", "duration"];
const ROUTE_WORDS: Record<string, string> = { oral: "By mouth", eye: "In the eye", inhalation: "Breathed in", topical: "On the skin" };

function shown(item: Item, f: FieldName): string | null {
  const value = item.fields[f].value;
  if (!value) return null;
  if (f === "route") return ROUTE_WORDS[value.toLowerCase()] ?? value;
  if (f === "frequency" && item.frequency_plain && item.frequency_plain.toLowerCase() !== value.toLowerCase()) {
    return `${item.frequency_plain} (written as ${value})`;
  }
  return value;
}

function ItemPanel({ item, caseId, onChange }: {
  item: Item;
  caseId: string;
  onChange: (c: Case) => void;
}) {
  const held = item.status === "NEEDS_CONFIRMATION";
  const initial = () => Object.fromEntries(FIELD_LABELS.map(([f]) => [f, item.fields[f].value ?? ""])) as Record<FieldName, string>;
  const [values, setValues] = useState(initial);
  const [editing, setEditing] = useState(held);
  const [error, setError] = useState("");
  const [missing, setMissing] = useState<string[]>([]);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    setValues(initial());
    setEditing(item.status === "NEEDS_CONFIRMATION");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [item]);

  const confirm = async () => {
    setSaving(true);
    setError("");
    setMissing([]);
    try {
      onChange(await api.confirm(caseId, item.index, values));
    } catch (e) {
      const err = e as Error & { missing?: string[] };
      setError(err.message);
      setMissing(err.missing ?? []);
    } finally {
      setSaving(false);
    }
  };

  const fields = FIELD_LABELS.filter(([f]) => f !== "name" || editing);

  return (
    <article className={held ? "panel item held" : "panel item"} aria-label={item.fields.name.value ?? "Unknown medicine"}>
      <header className="item-head">
        <h2>{item.fields.name.value ?? "A medicine I can't name"}</h2>
        {item.status === "CONFIRMED" && <span className="pill positive">Checked</span>}
        {item.status === "CLEAR" && <span className="pill neutral">Looks clear</span>}
        {held && <span className="pill warning">Let's check this one</span>}
        {!editing && <button className="text-button push" onClick={() => setEditing(true)}>Change</button>}
      </header>
      {held && (
        <div className="check-note">
          <ul>{item.reasons.map((r) => <li key={r.code}>{r.text}</li>)}</ul>
          <p>You haven't done anything wrong. Please show this to your pharmacist or doctor, and write in what they tell you.</p>
        </div>
      )}
      <div className="field-grid">
        {fields.map(([f, label]) => {
          const blank = !values[f].trim() && REQUIRED.includes(f);
          const id = `item-${item.index}-${f}`;
          return (
            <div key={f} className="field">
              <div className="label-row">
                <label htmlFor={id}>{label}</label>
                {held && blank && <span className="conf ask">Ask your pharmacist</span>}
              </div>
              {editing
                ? <input id={id} className={blank || missing.includes(f) ? "needs" : ""} value={values[f]} onChange={(e) => setValues({ ...values, [f]: e.target.value })} autoComplete="off" />
                : <p id={id} className="value">{shown(item, f) ?? <span className="dash">Nothing written</span>}</p>}
            </div>
          );
        })}
      </div>
      {editing && (
        <footer className="item-foot">
          <button className="secondary" disabled={saving} onClick={confirm}>
            {saving ? "Saving…" : "My pharmacist confirmed this"}
          </button>
          {error && <p className="inline-error compact" role="alert">{error}</p>}
        </footer>
      )}
    </article>
  );
}

export function ConfirmView({ current, onChange, onContinue, onStartOver }: {
  current: Case;
  onChange: (c: Case) => void;
  onContinue: () => void;
  onStartOver: () => void;
}) {
  const { items, ocr, injection_hits: hits, threshold } = current;
  const ready = items.filter((i) => i.usable).length;
  const held = items.length - ready;
  const hello = current.patient ? `${current.patient}, ` : "";
  const heldNames = items.filter((i) => !i.usable).map((i) => i.fields.name.value ?? "one medicine").join(" and ");

  let mood: Mood = "happy";
  let title = `${hello}here's what I found.`;
  let note = "Please look at it next to your paper. Does it match?";
  if (items.length === 0) {
    mood = "careful";
    title = "I couldn't find any medicines here.";
    note = "That's okay. Try a sharper photo, type it in, or ask your pharmacist.";
  } else if (held > 0) {
    mood = "careful";
    title = `Let's double-check ${heldNames}.`;
    note = ready > 0
      ? `${ready} ${ready === 1 ? "medicine is" : "medicines are"} clear. I won't guess the rest, so it stays out of your plan until your pharmacist has checked it.`
      : "I won't guess, so it stays out of your plan until your pharmacist has checked it.";
  }
  const isInjected = (line: string) => hits.some((h) => line.toLowerCase().includes(h.toLowerCase()));

  return (
    <>
      <Says mood={mood}>
        <h1>{title}</h1>
        <p>{note}</p>
      </Says>

      {hits.length > 0 && (
        <div className="notice" role="alert">
          <strong>I found a note that isn't meant for you.</strong> Someone wrote “{hits.join("”, “")}” on this paper, aimed at the computer. I ignored it and it changed nothing. Please check every line with your pharmacist.
        </div>
      )}

      <div className="grid-confirm">
        <section className="panel source" aria-labelledby="source-heading">
          <h2 id="source-heading">Your prescription</h2>
          {current.has_image
            ? <img className="rx-image" src={`/api/cases/${current.id}/image`} alt="The prescription you gave me" />
            : <pre className="rx-text">{ocr.lines.map((l) => l.text).join("\n")}</pre>}
          <details className="advanced">
            <summary>How sure am I about each line?</summary>
            <p className="meta explain">1.00 means completely sure. Below {threshold.toFixed(2)}, I ask for a second opinion. Read by {ocr.engine === "typed" ? "your typing" : ocr.engine}.</p>
            <table className="lines">
              <thead>
                <tr><th scope="col">Line</th><th scope="col" className="num">How sure</th></tr>
              </thead>
              <tbody>
                {ocr.lines.map((l, i) => (
                  <tr key={i} className={isInjected(l.text) ? "ignored" : ""}>
                    <td>
                      {l.text}
                      {isInjected(l.text) && <span className="pill warning inline">Ignored</span>}
                    </td>
                    <td className={l.confidence < threshold ? "num low" : "num"}>{l.confidence.toFixed(2)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </details>
        </section>

        <div className="items">
          {items.map((it) => (
            <ItemPanel key={it.index} item={it} caseId={current.id} onChange={onChange} />
          ))}
          {items.length === 0 && (
            <div className="panel empty">
              <button className="secondary" onClick={onStartOver}>Try another prescription</button>
            </div>
          )}
          {items.length > 0 && (
            <div className="next-row">
              <button className="primary big" disabled={ready === 0} onClick={onContinue}>
                {ready === 0 ? "Waiting for your pharmacist's check" : held > 0 ? `See my plan for the ${ready} that ${ready === 1 ? "is" : "are"} clear` : "See my plan"}
              </button>
            </div>
          )}
        </div>
      </div>
    </>
  );
}

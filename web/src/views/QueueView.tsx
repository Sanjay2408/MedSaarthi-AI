import { useCallback, useEffect, useState } from "react";
import { api, parseTime, type FieldName, type QueueItem } from "../api";
import { Says } from "../Saarthi";

const FIELDS: [FieldName, string][] = [
  ["name", "Medicine"], ["dose", "Dose"], ["frequency", "How often"], ["duration", "For how long"], ["route", "Route"], ["instructions", "Instructions"],
];
const REQUIRED: FieldName[] = ["name", "dose", "frequency", "duration"];
const ago = (iso: string) => {
  const m = Math.max(0, Math.round((Date.now() - parseTime(iso).getTime()) / 60000));
  return m < 1 ? "just now" : m < 60 ? `${m} min ago` : m < 1440 ? `${Math.round(m / 60)} h ago` : `${Math.round(m / 1440)} d ago`;
};

function Detail({ q, onBack, onDone }: { q: QueueItem; onBack: () => void; onDone: () => void }) {
  const [values, setValues] = useState(() => Object.fromEntries(FIELDS.map(([f]) => [f, q.item.fields[f].value ?? ""])) as Record<FieldName, string>);
  const [note, setNote] = useState("");
  const [declining, setDeclining] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [missing, setMissing] = useState<string[]>([]);
  const pending = q.status === "pending";

  const run = async (fn: () => Promise<unknown>) => {
    setBusy(true);
    setError("");
    setMissing([]);
    try {
      await fn();
      onDone();
    } catch (e) {
      const err = e as Error & { missing?: string[] };
      setError(err.message);
      setMissing(err.missing ?? []);
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="panel review-detail" aria-label={`Review ${q.item.fields.name.value ?? "item"}`}>
      <button className="text-button back" onClick={onBack}>Back to the list</button>
      <header className="item-head">
        <h2>{q.item.fields.name.value ?? "Unnamed medicine"}</h2>
        <span className="pill neutral">{q.patient}</span>
        <span className="meta push">Asked {ago(q.requested_at)}</span>
      </header>

      {q.injection_hits.length > 0 && (
        <div className="notice compact" role="alert"><strong>This paper contains text aimed at software:</strong> “{q.injection_hits.join("”, “")}”. It was ignored. Check every value.</div>
      )}
      {q.item.reasons.length > 0 && (
        <ul className="reasons">{q.item.reasons.map((r) => <li key={r.code}>{r.text}</li>)}</ul>
      )}

      <div className="review-grid">
        <div>
          <h3>Text read from the paper</h3>
          <pre className="rx-text">{q.ocr_lines.map((l) => l.text).join("\n")}</pre>
          <p className="meta">The photo itself is not stored. Check these lines against the paper in front of you.</p>
        </div>
        <div>
          <h3>What I will sign</h3>
          <div className="field-grid">
            {FIELDS.map(([f, label]) => {
              const blank = !values[f].trim() && REQUIRED.includes(f);
              return (
                <div className="field" key={f}>
                  <label htmlFor={`rv-${q.id}-${f}`}>{label}</label>
                  <input id={`rv-${q.id}-${f}`} className={blank || missing.includes(f) ? "needs" : ""} value={values[f]} disabled={!pending}
                         onChange={(e) => setValues({ ...values, [f]: e.target.value })} autoComplete="off" />
                </div>
              );
            })}
          </div>
        </div>
      </div>

      {error && <div className="inline-error" role="alert">{error}</div>}
      {pending ? (
        <footer className="item-foot">
          {declining ? (
            <div className="confirm-col">
              <div className="field"><label htmlFor={`note-${q.id}`}>Message to the patient</label>
                <textarea id={`note-${q.id}`} rows={3} maxLength={300} value={note} onChange={(e) => setNote(e.target.value)} placeholder="Dose unclear. Please see Dr. Rao." /></div>
              <div className="row"><button className="danger-button" disabled={busy} onClick={() => run(() => api.decline(q.id, note))}>Send back unverified</button><button className="text-button" onClick={() => setDeclining(false)}>Cancel</button></div>
            </div>
          ) : (
            <>
              <button className="primary" disabled={busy} onClick={() => run(() => api.verify(q.id, values))}>{busy ? "Signing…" : "Verify and sign"}</button>
              <button className="secondary" onClick={() => setDeclining(true)}>I can't verify this</button>
              <p className="meta">Your name and the time are stored with the item and shown on the patient's plan.</p>
            </>
          )}
        </footer>
      ) : (
        <p className="meta">{q.status === "verified" ? `Verified by ${q.reviewed_by}.` : `Sent back by ${q.reviewed_by}.`}</p>
      )}
    </section>
  );
}

export function QueueView() {
  const [tab, setTab] = useState<"pending" | "done">("pending");
  const [rows, setRows] = useState<QueueItem[] | null>(null);
  const [open, setOpen] = useState<number | null>(null);
  const [error, setError] = useState("");

  const load = useCallback(() => {
    setError("");
    api.queue(tab).then(setRows).catch((e: Error) => setError(e.message));
  }, [tab]);
  useEffect(() => { setRows(null); setOpen(null); load(); }, [load]);

  const current = rows?.find((r) => r.id === open) ?? null;
  const waiting = tab === "pending" ? rows?.length ?? 0 : 0;

  return (
    <>
      <Says mood={waiting ? "careful" : "hello"}>
        <h1>{tab === "pending" ? (waiting ? `${waiting} ${waiting === 1 ? "item is" : "items are"} waiting for you.` : "Nothing is waiting.") : "What you've checked."}</h1>
        <p>People share an unclear item when they want a pharmacist to look at it. You see only what they chose to share.</p>
      </Says>

      <div className="segmented" role="tablist" aria-label="Review lists">
        <button role="tab" aria-selected={tab === "pending"} className={tab === "pending" ? "on" : ""} onClick={() => setTab("pending")}>Waiting</button>
        <button role="tab" aria-selected={tab === "done"} className={tab === "done" ? "on" : ""} onClick={() => setTab("done")}>Done by me</button>
      </div>

      {error && <div className="inline-error" role="alert">{error} <button className="text-button" onClick={load}>Try again</button></div>}

      <div className={current ? "queue has-detail" : "queue"}>
        <ul className="queue-list" aria-label="Items to review">
          {rows === null && !error && <li className="panel skeleton" aria-hidden="true" />}
          {rows?.length === 0 && <li className="panel empty-line">{tab === "pending" ? "All caught up." : "You haven't reviewed anything yet."}</li>}
          {rows?.map((r) => (
            <li key={r.id}>
              <button className={r.id === open ? "queue-row on" : "queue-row"} onClick={() => setOpen(r.id)} aria-current={r.id === open}>
                <strong>{r.item.fields.name.value ?? "Unnamed medicine"}</strong>
                <span className="meta">{r.patient} · {ago(r.requested_at)}</span>
                <span className="meta">{r.item.reasons[0]?.text ?? "Shared for a check"}</span>
              </button>
            </li>
          ))}
        </ul>
        {current && <Detail key={current.id} q={current} onBack={() => setOpen(null)} onDone={() => { setOpen(null); load(); }} />}
        {!current && rows && rows.length > 0 && <div className="panel queue-hint">Choose an item to review it.</div>}
      </div>
    </>
  );
}

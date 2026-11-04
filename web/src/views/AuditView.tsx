import { useCallback, useEffect, useState } from "react";
import { api, type AuditRow } from "../api";

const STEP_LABELS: Record<string, string> = {
  consent: "You agreed to the notice",
  extract: "Medicines read",
  ambiguity_llm: "Double-checked for anything unclear",
  human_confirm: "You confirmed a medicine",
  rag_summary: "Leaflet summarised",
  simplify: "Instructions written",
  translate: "Translated",
};

const clock = (ts: unknown) => String(ts).slice(11, 19);

export function AuditView({ onDeleted }: { onDeleted: () => void }) {
  const [rows, setRows] = useState<AuditRow[] | null>(null);
  const [error, setError] = useState("");
  const [asking, setAsking] = useState(false);
  const [deleted, setDeleted] = useState("");

  const load = useCallback(() => {
    setError("");
    api.audit().then((a) => setRows(a.rows)).catch((e: Error) => setError(e.message));
  }, []);

  useEffect(load, [load]);

  const remove = async () => {
    try {
      const res = await api.deleteSession();
      setAsking(false);
      setDeleted(`Done. I've forgotten ${res.removed} ${res.removed === 1 ? "prescription" : "prescriptions"}.`);
      onDeleted();
      load();
    } catch (e) {
      setError((e as Error).message);
    }
  };

  return (
    <>
      <div className="title-row">
        <div>
          <h1>Your privacy</h1>
          <p className="subline">What I keep: a list of the steps below, each with a scrambled fingerprint of its input. Your prescription's words aren't in it.</p>
        </div>
      </div>

      <section className="panel table-panel" aria-label="Steps in this visit">
        {error && (
          <div className="inline-error" role="alert">
            {error} <button className="text-button" onClick={load}>Try again</button>
          </div>
        )}
        {rows && rows.length === 0 && <p className="empty-line">Nothing yet. Steps appear here once you add a prescription.</p>}
        {rows && rows.length > 0 && (
          <div className="table-scroll">
            <table className="plain audit">
              <thead>
                <tr>
                  <th scope="col">Time</th>
                  <th scope="col">What happened</th>
                  <th scope="col">AI used</th>
                  <th scope="col">Fingerprint</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r, i) => (
                  <tr key={i}>
                    <td className="num">{clock(r.ts)}</td>
                    <td>{STEP_LABELS[String(r.step)] ?? String(r.step)}</td>
                    <td>{r.model ? String(r.model).split(":").pop() : <span className="dash">None</span>}</td>
                    <td className="id">{String(r.input_sha256).slice(0, 12)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <section className="panel danger" aria-labelledby="delete-heading">
        <div>
          <h2 id="delete-heading">Forget this visit</h2>
          <p>Clears your prescriptions from memory and starts fresh. They're also forgotten when the server restarts.</p>
          {deleted && <p role="status"><strong>{deleted}</strong></p>}
        </div>
        {asking ? (
          <div className="confirm-row">
            <button className="danger-button" onClick={remove}>Yes, forget it</button>
            <button className="text-button" onClick={() => setAsking(false)}>Keep it</button>
          </div>
        ) : (
          <button className="danger-button" onClick={() => setAsking(true)}>Forget this visit</button>
        )}
      </section>
    </>
  );
}

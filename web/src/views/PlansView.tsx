import { useCallback, useEffect, useState } from "react";
import { api, parseTime, type Case, type PlanSummary, type Verification } from "../api";
import { useAuth } from "../auth";
import { Says } from "../Saarthi";

export function VerifyBadge({ v, usable = true }: { v: Verification | null; usable?: boolean }) {
  if (!usable) return <span className="pill warning">Waiting for a check</span>;
  if (v?.kind === "pharmacist") return <span className="pill positive">Verified by pharmacist {v.by}</span>;
  if (v?.kind === "self") return <span className="pill neutral">Checked by you, not by a pharmacist</span>;
  return <span className="pill neutral">Not yet checked by a pharmacist</span>;
}

const when = (iso: string) => parseTime(iso).toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" });

export function PlansView({ onOpen, goNew }: { onOpen: (c: Case) => void; goNew: () => void }) {
  const { profiles } = useAuth();
  const [plans, setPlans] = useState<PlanSummary[] | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState("");
  const [asking, setAsking] = useState<string | null>(null);

  const load = useCallback(() => {
    api.plans().then(setPlans).catch((e: Error) => setError(e.message));
  }, []);
  useEffect(load, [load]);

  const act = async (id: string, fn: () => Promise<unknown>) => {
    setBusy(id);
    setError("");
    try {
      await fn();
      load();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy("");
    }
  };

  const open = (id: string) => act(id, async () => onOpen(await api.openPlan(id)));

  return (
    <>
      <Says mood={plans?.some((p) => p.pending) ? "careful" : "hello"}>
        <h1>{plans && plans.length ? "Your saved plans" : "Nothing saved yet."}</h1>
        <p>{plans && plans.length ? "Open one to see today's doses, or ask a pharmacist to check anything unclear." : "When you save a plan it appears here, kept encrypted and only visible to you."}</p>
      </Says>

      {error && <div className="inline-error" role="alert">{error} <button className="text-button" onClick={load}>Try again</button></div>}

      <div className="plans">
        {plans === null && !error && <div className="panel skeleton" aria-hidden="true" />}
        {plans?.length === 0 && (
          <div className="panel empty"><button className="primary" onClick={goNew}>Add a prescription</button></div>
        )}
        {plans?.map((p) => {
          const open_ = p.items.every((i) => i.status !== "NEEDS_CONFIRMATION");
          const needsCheck = p.items.some((i) => i.status === "NEEDS_CONFIRMATION" || !i.verification || i.verification.kind !== "pharmacist");
          return (
            <article key={p.id} className="panel plan-card" aria-label={p.title}>
              <header className="item-head">
                <h2>{p.title}</h2>
                {profiles.length > 1 && <span className="pill neutral">{p.profile_name}</span>}
                <span className="meta push">{when(p.created_at)}</span>
              </header>
              <ul className="plan-items">
                {p.items.map((it) => (
                  <li key={it.index}>
                    <strong>{it.name}</strong>
                    <VerifyBadge v={it.verification} usable={it.status !== "NEEDS_CONFIRMATION"} />
                  </li>
                ))}
              </ul>
              {p.reviews.filter((r) => r.status === "declined").map((r) => (
                <p key={r.id} className="notice compact"><strong>{r.reviewer} sent this back:</strong> {r.note}</p>
              ))}
              {p.pending > 0 && <p className="meta" role="status">{p.pending} {p.pending === 1 ? "item is" : "items are"} waiting for a pharmacist.</p>}
              <footer className="item-foot">
                <button className="primary" disabled={busy === p.id} onClick={() => open(p.id)}>{open_ ? "Open my plan" : "Open and finish checking"}</button>
                {needsCheck && p.pending === 0 && (asking === p.id ? (
                  <span className="row">
                    <button className="secondary" onClick={() => act(p.id, () => api.askReview(p.id, "all"))}>Share with a pharmacist</button>
                    <button className="text-button" onClick={() => setAsking(null)}>Not now</button>
                  </span>
                ) : <button className="secondary" onClick={() => setAsking(p.id)}>Ask a pharmacist to check</button>)}
                <button className="text-button push" onClick={() => window.confirm(`Delete "${p.title}"? This can't be undone.`) && act(p.id, () => api.deletePlan(p.id))}>Delete</button>
              </footer>
              {asking === p.id && <p className="meta">A pharmacist will see the medicine details and the text I read from your prescription. Not your photo.</p>}
            </article>
          );
        })}
      </div>
    </>
  );
}

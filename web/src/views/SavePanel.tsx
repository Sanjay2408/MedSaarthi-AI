import { useState } from "react";
import { api, type Case, type PlanSummary } from "../api";
import { useAuth } from "../auth";

/** Saving is opt-in. A guest sees why an account helps; a signed-in person chooses who it is for
 *  and whether to share unclear items with a pharmacist. */
export function SavePanel({ current, goLogin, goPlans }: { current: Case; goLogin: () => void; goPlans: () => void }) {
  const { user, profiles, profile } = useAuth();
  const held = current.items.filter((i) => !i.usable).length;
  const [profileId, setProfileId] = useState<number | null>(current.profile_id ?? null);
  const [share, setShare] = useState(held > 0);
  const [busy, setBusy] = useState(false);
  const [saved, setSaved] = useState<PlanSummary | null>(null);
  const [error, setError] = useState("");

  if (user?.role === "pharmacist") return null;

  if (!user) {
    return (
      <section className="panel save-panel" aria-labelledby="save-heading">
        <h2 id="save-heading">Want to keep this?</h2>
        <p>Sign in to save this plan, and to ask a pharmacist to check anything unclear. Without an account nothing is saved, and it is forgotten when you close this page.</p>
        <button className="secondary" onClick={goLogin}>Sign in or create an account</button>
      </section>
    );
  }

  const save = async () => {
    setBusy(true);
    setError("");
    try {
      const target = profileId ?? profile?.id;
      if (!target) throw new Error("Choose who this is for.");
      setSaved(await api.savePlan({ case_id: current.id, profile_id: target, share_with_pharmacist: share }));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  if (saved) {
    return (
      <section className="panel save-panel" aria-live="polite">
        <h2>Saved.</h2>
        <p>{saved.pending > 0 ? `${saved.pending} ${saved.pending === 1 ? "item was" : "items were"} sent to a pharmacist. You'll see their answer in My plans.` : "You'll find it in My plans, kept encrypted."}</p>
        <button className="secondary" onClick={goPlans}>Go to My plans</button>
      </section>
    );
  }

  return (
    <section className="panel save-panel" aria-labelledby="save-heading">
      <h2 id="save-heading">Save this plan</h2>
      {profiles.length > 1 && (
        <div className="field inline">
          <label htmlFor="save-for">Who is this for?</label>
          <select id="save-for" value={profileId ?? profile?.id ?? ""} onChange={(e) => setProfileId(Number(e.target.value))}>
            {profiles.map((p) => <option key={p.id} value={p.id}>{p.display_name}</option>)}
          </select>
        </div>
      )}
      <label className="check">
        <input type="checkbox" checked={share} onChange={(e) => setShare(e.target.checked)} />
        <span>{held > 0 ? `Share the ${held} unclear ${held === 1 ? "item" : "items"} with a pharmacist, so they can check ${held === 1 ? "it" : "them"}.` : "Also ask a pharmacist to verify all of it."}</span>
      </label>
      <p className="meta">Saved plans are encrypted. Your photo is never stored. A pharmacist sees only what you share.</p>
      {error && <div className="inline-error" role="alert">{error}</div>}
      <button className="secondary" disabled={busy} onClick={save}>{busy ? "Saving…" : "Save to my account"}</button>
    </section>
  );
}

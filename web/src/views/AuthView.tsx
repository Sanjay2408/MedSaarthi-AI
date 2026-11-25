import { useState, type FormEvent } from "react";
import type { Role } from "../api";
import { useAuth } from "../auth";
import { Says } from "../Saarthi";

const ROLES: { id: Role; label: string; help: string }[] = [
  { id: "patient", label: "For me", help: "I take medicines myself." },
  { id: "caregiver", label: "For my family", help: "I look after someone else too: a parent, a child." },
  { id: "pharmacist", label: "I'm a pharmacist", help: "I check prescriptions people share. Needs an invite code." },
];

export function AuthView({ onDone, onGuest }: { onDone: (role: Role) => void; onGuest: () => void }) {
  const auth = useAuth();
  const [mode, setMode] = useState<"in" | "up">("in");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [show, setShow] = useState(false);
  const [name, setName] = useState("");
  const [role, setRole] = useState<Role>("patient");
  const [invite, setInvite] = useState("");
  const [agree, setAgree] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      const me = mode === "in"
        ? await auth.signIn(email, password)
        : await auth.signUp({ email, password, name, role, invite: role === "pharmacist" ? invite : undefined, agree });
      onDone(me.user!.role);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const signup = mode === "up";
  return (
    <>
      <Says mood="hello">
        <h1>{signup ? "Let's set you up." : "Welcome back."}</h1>
        <p>{signup ? "An account lets you save plans, look after family, and ask a pharmacist to check anything unclear." : "Sign in to see your saved plans."}</p>
      </Says>

      <div className="grid-auth">
        <form className="panel auth-form" onSubmit={submit} aria-labelledby="auth-heading">
          <h2 id="auth-heading" className="sr-only">{signup ? "Create an account" : "Sign in"}</h2>
          <div className="segmented" role="tablist" aria-label="Sign in or create an account">
            <button type="button" role="tab" aria-selected={!signup} className={!signup ? "on" : ""} onClick={() => setMode("in")}>Sign in</button>
            <button type="button" role="tab" aria-selected={signup} className={signup ? "on" : ""} onClick={() => setMode("up")}>Create account</button>
          </div>

          {signup && (
            <>
              <fieldset className="role-pick">
                <legend>Who is this for?</legend>
                {ROLES.map((r) => (
                  <label key={r.id} className={role === r.id ? "role on" : "role"}>
                    <input type="radio" name="role" value={r.id} checked={role === r.id} onChange={() => setRole(r.id)} />
                    <strong>{r.label}</strong>
                    <span>{r.help}</span>
                  </label>
                ))}
              </fieldset>
              <div className="field">
                <label htmlFor="name">What should I call you?</label>
                <input id="name" value={name} onChange={(e) => setName(e.target.value)} autoComplete="name" maxLength={60} required />
              </div>
            </>
          )}

          <div className="field">
            <label htmlFor="email">Email</label>
            <input id="email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="email" inputMode="email" required />
          </div>
          <div className="field">
            <label htmlFor="password">Password</label>
            <div className="password-row">
              <input id="password" type={show ? "text" : "password"} value={password} onChange={(e) => setPassword(e.target.value)}
                     autoComplete={signup ? "new-password" : "current-password"} aria-describedby={signup ? "pw-help" : undefined} required />
              <button type="button" className="secondary" aria-pressed={show} onClick={() => setShow(!show)}>{show ? "Hide" : "Show"}</button>
            </div>
            {signup && <p id="pw-help" className="meta">At least 10 characters. A few random words are easier to remember and hard to guess.</p>}
          </div>

          {signup && role === "pharmacist" && (
            <div className="field">
              <label htmlFor="invite">Invite code</label>
              <input id="invite" value={invite} onChange={(e) => setInvite(e.target.value)} autoComplete="off" required />
              <p className="meta">Pharmacist accounts are not open to everyone. The person running this server gives you the code.</p>
            </div>
          )}

          {signup && (
            <label className="check">
              <input type="checkbox" checked={agree} onChange={(e) => setAgree(e.target.checked)} required />
              <span>I understand this is a student project on made-up prescriptions, and I won't enter real patient data.</span>
            </label>
          )}

          {error && <div className="inline-error" role="alert">{error}</div>}
          <button className="primary wide" type="submit" disabled={busy}>{busy ? "One moment…" : signup ? "Create my account" : "Sign in"}</button>
          <button type="button" className="text-button center" onClick={onGuest}>Continue without an account</button>
        </form>

        <aside className="panel side" aria-labelledby="why-heading">
          <h2 id="why-heading">What an account is for</h2>
          <ul className="promise-list">
            <li><strong>Saved plans.</strong> Kept encrypted. I never store your photo.</li>
            <li><strong>Family.</strong> Look after a parent or child, each with their own language and text size.</li>
            <li><strong>A pharmacist's check.</strong> Share an unclear item and get a named pharmacist's answer.</li>
            <li><strong>Delete anytime.</strong> One button removes your account and everything in it.</li>
          </ul>
          <p className="meta">You can use MedSaarthi without an account. Nothing is saved then.</p>
        </aside>
      </div>
    </>
  );
}

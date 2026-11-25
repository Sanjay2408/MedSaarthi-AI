import { useState } from "react";
import { api, type AgeBand, type Config, type Profile } from "../api";
import { useAuth } from "../auth";
import { readDevicePref, writeDevicePref, type DevicePref } from "../scene/prefs";

const AGES: { id: AgeBand; label: string; help: string }[] = [
  { id: "child", label: "Child", help: "Simple words and a lively Saarthi. A grown-up looks after this profile." },
  { id: "adult", label: "Adult", help: "The usual." },
  { id: "senior", label: "Senior", help: "Bigger text, slower motion, fewer choices, and I offer to read aloud first." },
];
const RELATIONS = [["parent", "Parent"], ["child", "Child"], ["spouse", "Partner"], ["other", "Someone else"]];

function Switch({ label, help, on, onChange }: { label: string; help?: string; on: boolean; onChange: (v: boolean) => void }) {
  return (
    <div className="setting-row">
      <div>
        <strong>{label}</strong>
        {help && <p className="meta">{help}</p>}
      </div>
      <button className="switch" role="switch" aria-checked={on} aria-label={label} onClick={() => onChange(!on)}>
        <span className="switch-track" aria-hidden="true" />
        <span className="sr-only">{on ? "On" : "Off"}</span>
      </button>
    </div>
  );
}

export function SettingsView({ config, onSignedOut, goLogin }: { config: Config; onSignedOut: () => void; goLogin: () => void }) {
  const auth = useAuth();
  const { user, profile, profiles } = auth;
  const [device, setDevice] = useState<DevicePref>(readDevicePref);
  const [saved, setSaved] = useState("");
  const [error, setError] = useState("");
  const [adding, setAdding] = useState(false);
  const [draft, setDraft] = useState({ display_name: "", relation: "parent", age_band: "senior" as AgeBand, language: "en" });
  const [confirming, setConfirming] = useState(false);
  const [password, setPassword] = useState("");

  const save = async (patch: Partial<Profile>) => {
    if (!profile) return;
    setError("");
    try {
      await auth.updateProfile(profile.id, patch);
      setSaved("Saved");
      window.setTimeout(() => setSaved(""), 1800);
    } catch (e) {
      setError((e as Error).message);
    }
  };

  const deviceChoice = (v: DevicePref) => {
    setDevice(v);
    writeDevicePref(v);
  };

  const devicePanel = (
    <section className="panel" aria-labelledby="device-heading">
      <h2 id="device-heading">This device</h2>
      <div className="setting-row">
        <div>
          <strong>3D scenes</strong>
          <p className="meta">Saarthi and the pill organizer in 3D. Auto turns them off on slow phones and when you ask your device for less motion.</p>
        </div>
        <div className="segmented small" role="group" aria-label="3D scenes">
          {(["auto", "on", "off"] as DevicePref[]).map((v) => (
            <button key={v} className={device === v ? "on" : ""} aria-pressed={device === v} onClick={() => deviceChoice(v)}>{v === "auto" ? "Auto" : v === "on" ? "On" : "Off"}</button>
          ))}
        </div>
      </div>
    </section>
  );

  if (!user || !profile) {
    return (
      <>
        <div className="title-row"><div><h1>Settings</h1><p className="subline">Without an account, these apply to this device only.</p></div></div>
        <div className="stack">
          {devicePanel}
          <section className="panel">
            <h2>Make it yours</h2>
            <p>An account remembers your language, text size and age setting on every device, and keeps your saved plans.</p>
            <button className="primary" onClick={goLogin}>Sign in or create an account</button>
          </section>
        </div>
      </>
    );
  }

  const remove = async (id: number) => {
    try {
      await api.removeProfile(id);
      await auth.refresh();
    } catch (e) {
      setError((e as Error).message);
    }
  };

  const add = async () => {
    setError("");
    try {
      await api.addProfile({ ...draft, large_text: draft.age_band === "senior", voice_first: draft.age_band === "senior" });
      await auth.refresh();
      setAdding(false);
      setDraft({ display_name: "", relation: "parent", age_band: "senior", language: "en" });
    } catch (e) {
      setError((e as Error).message);
    }
  };

  const deleteAccount = async () => {
    setError("");
    try {
      await api.deleteAccount(password);
      await auth.signOut();
      onSignedOut();
    } catch (e) {
      setError((e as Error).message);
    }
  };

  return (
    <>
      <div className="title-row">
        <div>
          <h1>Settings{profiles.length > 1 ? `: ${profile.display_name}` : ""}</h1>
          <p className="subline" role="status">{saved || "Changes save as you make them."}</p>
        </div>
      </div>
      {error && <div className="inline-error" role="alert">{error}</div>}

      <div className="stack">
        <section className="panel" aria-labelledby="who-heading">
          <h2 id="who-heading">How I talk to you</h2>
          <div className="field">
            <label htmlFor="pname">Name</label>
            <input id="pname" defaultValue={profile.display_name} key={profile.id} maxLength={60}
                   onBlur={(e) => e.target.value.trim() && e.target.value !== profile.display_name && save({ display_name: e.target.value.trim() })} />
          </div>
          <fieldset className="age-pick">
            <legend>Age group</legend>
            {AGES.map((a) => (
              <label key={a.id} className={profile.age_band === a.id ? "role on" : "role"}>
                <input type="radio" name="age" checked={profile.age_band === a.id} onChange={() => save(a.id === "senior" ? { age_band: a.id, large_text: true, voice_first: true } : { age_band: a.id })} />
                <strong>{a.label}</strong>
                <span>{a.help}</span>
              </label>
            ))}
          </fieldset>
        </section>

        <section className="panel" aria-labelledby="lang-heading">
          <h2 id="lang-heading">Language and time</h2>
          <div className="field">
            <label htmlFor="lang">Language for my plan</label>
            <select id="lang" value={profile.language} onChange={(e) => save({ language: e.target.value })}>
              {config.languages.map((l) => (
                <option key={l.code} value={l.code}>{l.native === l.name ? l.name : `${l.native} (${l.name})`}{l.reviewed ? "" : " · draft wording"}</option>
              ))}
            </select>
            <p className="meta">"Draft wording" means the words were written by an AI and a native speaker has not checked them yet.</p>
          </div>
          <div className="setting-row">
            <strong>Clock</strong>
            <div className="segmented small" role="group" aria-label="Clock">
              {(["12h", "24h"] as const).map((f) => (
                <button key={f} className={profile.time_format === f ? "on" : ""} aria-pressed={profile.time_format === f} onClick={() => save({ time_format: f })}>{f === "12h" ? "12 hour" : "24 hour"}</button>
              ))}
            </div>
          </div>
        </section>

        <section className="panel" aria-labelledby="comfort-heading">
          <h2 id="comfort-heading">Comfort</h2>
          <Switch label="Bigger text" on={profile.large_text} onChange={(v) => save({ large_text: v })} />
          <Switch label="High contrast" help="Black and yellow, easier in bright light." on={profile.high_contrast} onChange={(v) => save({ high_contrast: v })} />
          <Switch label="Calm motion" help="Less movement everywhere. 3D scenes become flat." on={profile.reduce_motion} onChange={(v) => save({ reduce_motion: v })} />
          <Switch label="Read aloud first" help="Offer to read each medicine out loud. Works when your device has a voice for the language." on={profile.voice_first} onChange={(v) => save({ voice_first: v })} />
        </section>

        {devicePanel}

        {user.role === "caregiver" && (
          <section className="panel" aria-labelledby="people-heading">
            <h2 id="people-heading">People I look after</h2>
            <ul className="people">
              {profiles.map((p) => (
                <li key={p.id}>
                  <span><strong>{p.display_name}</strong> <span className="meta">{p.is_default ? "You" : p.relation} · {p.age_band}</span></span>
                  {!p.is_default && <button className="text-button" onClick={() => remove(p.id)} aria-label={`Remove ${p.display_name}`}>Remove</button>}
                </li>
              ))}
            </ul>
            {adding ? (
              <div className="add-person">
                <div className="field"><label htmlFor="n">Name</label><input id="n" value={draft.display_name} onChange={(e) => setDraft({ ...draft, display_name: e.target.value })} maxLength={60} /></div>
                <div className="field"><label htmlFor="r">Who are they to you?</label>
                  <select id="r" value={draft.relation} onChange={(e) => setDraft({ ...draft, relation: e.target.value })}>{RELATIONS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select></div>
                <div className="field"><label htmlFor="a">Age group</label>
                  <select id="a" value={draft.age_band} onChange={(e) => setDraft({ ...draft, age_band: e.target.value as AgeBand })}>{AGES.map((a) => <option key={a.id} value={a.id}>{a.label}</option>)}</select></div>
                <div className="field"><label htmlFor="l">Their language</label>
                  <select id="l" value={draft.language} onChange={(e) => setDraft({ ...draft, language: e.target.value })}>{config.languages.map((l) => <option key={l.code} value={l.code}>{l.native}</option>)}</select></div>
                <div className="row"><button className="primary" disabled={!draft.display_name.trim()} onClick={add}>Add this person</button><button className="text-button" onClick={() => setAdding(false)}>Cancel</button></div>
              </div>
            ) : (
              <button className="secondary" onClick={() => setAdding(true)}>Add a person</button>
            )}
          </section>
        )}

        <section className="panel" aria-labelledby="acct-heading">
          <h2 id="acct-heading">Account</h2>
          <p><strong>{user.name}</strong> <span className="meta">{user.email} · {user.role}</span></p>
          <div className="row">
            <button className="secondary" onClick={async () => { await auth.signOut(); onSignedOut(); }}>Sign out</button>
          </div>
        </section>

        <section className="panel danger" aria-labelledby="del-heading">
          <div>
            <h2 id="del-heading">Delete my account</h2>
            <p className="meta">Removes your account, every person you look after, all saved plans and pharmacist notes. This can't be undone.</p>
          </div>
          {confirming ? (
            <div className="confirm-col">
              <div className="field"><label htmlFor="dp">Your password</label><input id="dp" type="password" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="current-password" /></div>
              <div className="row"><button className="danger-button" disabled={!password} onClick={deleteAccount}>Yes, delete everything</button><button className="text-button" onClick={() => { setConfirming(false); setPassword(""); }}>Keep my account</button></div>
            </div>
          ) : (
            <button className="danger-button" onClick={() => setConfirming(true)}>Delete my account</button>
          )}
        </section>
      </div>
    </>
  );
}

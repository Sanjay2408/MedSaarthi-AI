import { useEffect, useMemo, useState } from "react";
import { api, type Case, type Config, type Guide, type GuidePrefs, type Role } from "./api";
import { AuthProvider, useAuth } from "./auth";
import { Saarthi } from "./Saarthi";
import { ScenePrefsProvider } from "./scene/prefs";
import { AuditView } from "./views/AuditView";
import { AuthView } from "./views/AuthView";
import { ConfirmView } from "./views/ConfirmView";
import { GuideView } from "./views/GuideView";
import { PlansView } from "./views/PlansView";
import { QueueView } from "./views/QueueView";
import { ReadView } from "./views/ReadView";
import { SettingsView } from "./views/SettingsView";

export type View = "read" | "confirm" | "guide" | "audit" | "login" | "plans" | "settings" | "queue";

function stored(key: string): boolean {
  try {
    return localStorage.getItem(key) === "1";
  } catch {
    return false;
  }
}

function store(key: string, on: boolean) {
  try {
    localStorage.setItem(key, on ? "1" : "0");
  } catch {
    /* private window: the setting still applies for this visit */
  }
}

export const DEFAULT_PREFS: GuidePrefs = { lang: "en", time_format: "12h", shift_minutes: 0, variant: "v2" };

type Tab = { id: View; label: string; icon: string };
const ICONS: Record<string, string> = {
  read: "M12 5v14M5 12h14",
  plans: "M6 4h12v16H6zM9 9h6M9 13h6",
  settings: "M12 8.5a3.5 3.5 0 1 0 0 7 3.5 3.5 0 0 0 0-7zM4 12h2M18 12h2M12 4v2M12 18v2",
  queue: "M5 7h14M5 12h14M5 17h9",
  login: "M10 6H6v12h4M14 8l4 4-4 4M18 12H9",
  audit: "M12 4l7 3v5c0 4-3 7-7 8-4-1-7-4-7-8V7z",
};

function Shell() {
  const auth = useAuth();
  const { user, profile, profiles } = auth;
  const [view, setView] = useState<View>("read");
  const [config, setConfig] = useState<Config | null>(null);
  const [configError, setConfigError] = useState("");
  const [current, setCurrent] = useState<Case | null>(null);
  const [guide, setGuide] = useState<Guide | null>(null);
  const [prefs, setPrefs] = useState<GuidePrefs>(DEFAULT_PREFS);
  const [consent, setConsent] = useState(false);
  const [guestLarge, setGuestLarge] = useState(() => stored("ms-large"));
  const [guestContrast, setGuestContrast] = useState(() => stored("ms-contrast"));

  // A signed-in person's own settings win over the device toggles.
  const large = profile ? profile.large_text || profile.age_band === "senior" : guestLarge;
  const contrast = profile ? profile.high_contrast : guestContrast;
  const calm = profile?.reduce_motion ?? false;
  const age = profile?.age_band ?? "adult";

  useEffect(() => {
    api.config().then(setConfig).catch((e: Error) => setConfigError(e.message));
  }, []);

  useEffect(() => {
    const root = document.documentElement;
    root.toggleAttribute("data-large", large);
    root.toggleAttribute("data-contrast", contrast);
    root.toggleAttribute("data-calm", calm);
    root.setAttribute("data-age", age);
    if (!profile) {
      store("ms-large", guestLarge);
      store("ms-contrast", guestContrast);
    }
  }, [large, contrast, calm, age, profile, guestLarge, guestContrast]);

  // The profile's language and clock are the starting point for each new plan.
  useEffect(() => {
    if (profile) setPrefs((p) => ({ ...p, lang: profile.language, time_format: profile.time_format }));
  }, [profile?.id, profile?.language, profile?.time_format]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    window.scrollTo(0, 0);
  }, [view]);

  const role: Role | null = user?.role ?? null;

  // Pharmacists have no use for the add-a-prescription flow; send them to their queue once.
  useEffect(() => {
    if (!auth.loading && role === "pharmacist" && (view === "read" || view === "login")) setView("queue");
  }, [auth.loading, role]); // eslint-disable-line react-hooks/exhaustive-deps

  const startOver = () => {
    setCurrent(null);
    setGuide(null);
    setView(role === "pharmacist" ? "queue" : "read");
  };

  const openCase = (c: Case, to: View = "confirm") => {
    setCurrent(c);
    setGuide(null);
    setView(to);
  };

  const tabs: Tab[] = useMemo(() => {
    if (role === "pharmacist") {
      return [
        { id: "queue", label: "To check", icon: ICONS.queue },
        { id: "settings", label: "Account", icon: ICONS.settings },
        { id: "audit", label: "Privacy", icon: ICONS.audit },
      ];
    }
    if (role) {
      return [
        { id: "read", label: "New", icon: ICONS.read },
        { id: "plans", label: "My plans", icon: ICONS.plans },
        { id: "settings", label: "Settings", icon: ICONS.settings },
      ];
    }
    return [
      { id: "read", label: "New", icon: ICONS.read },
      { id: "login", label: "Sign in", icon: ICONS.login },
      { id: "settings", label: "Settings", icon: ICONS.settings },
    ];
  }, [role]);

  const flow = view === "read" || view === "confirm" || view === "guide";
  const steps: { id: View; label: string; ready: boolean }[] = [
    { id: "read", label: "Add prescription", ready: true },
    { id: "confirm", label: "Check together", ready: current !== null },
    { id: "guide", label: "Your plan", ready: current?.items.some((i) => i.usable) ?? false },
  ];
  const at = steps.findIndex((s) => s.id === view);
  const tabOn = (id: View) => view === id || (id === "read" && (view === "confirm" || view === "guide"));

  const afterAuth = (r: Role) => setView(r === "pharmacist" ? "queue" : current ? "confirm" : "plans");

  return (
    <ScenePrefsProvider age={age} reduceMotion={calm}>
      <a className="skip" href="#main">Skip to content</a>
      <header className="topbar">
        <div className="column topbar-inner">
          <button className="brand" onClick={startOver} aria-label="MedSaarthi, start again">
            <Saarthi mood="hello" size={34} />
            <span>MedSaarthi</span>
          </button>

          <nav className="topnav" aria-label="Main">
            {tabs.map((t) => (
              <button key={t.id} className={tabOn(t.id) ? "toplink on" : "toplink"} aria-current={tabOn(t.id) ? "page" : undefined} onClick={() => setView(t.id)}>
                {t.label}
              </button>
            ))}
            {role !== "pharmacist" && (
              <button className={view === "audit" ? "toplink on" : "toplink"} onClick={() => setView(view === "audit" ? "read" : "audit")}>Your privacy</button>
            )}
          </nav>

          <div className="toggles">
            {user && profiles.length > 1 && (
              <div className="field inline who">
                <label htmlFor="who">For</label>
                <select id="who" value={profile?.id} onChange={(e) => { auth.setProfileId(Number(e.target.value)); }}>
                  {profiles.map((p) => <option key={p.id} value={p.id}>{p.is_default ? `${p.display_name} (me)` : p.display_name}</option>)}
                </select>
              </div>
            )}
            {!user && (
              <>
                <button className="switch" role="switch" aria-checked={guestLarge} onClick={() => setGuestLarge(!guestLarge)}>
                  <span className="switch-track" aria-hidden="true" />
                  Bigger text
                </button>
                <button className="switch" role="switch" aria-checked={guestContrast} onClick={() => setGuestContrast(!guestContrast)}>
                  <span className="switch-track" aria-hidden="true" />
                  High contrast
                </button>
              </>
            )}
            {user && (
              <button className="account-chip" onClick={() => setView("settings")} aria-label={`Account: ${user.name}`}>
                <span className="avatar" aria-hidden="true">{user.name.slice(0, 1).toUpperCase()}</span>
                <span className="chip-name">{user.name.split(" ")[0]}</span>
              </button>
            )}
          </div>
        </div>
      </header>

      <main id="main" className="column canvas" tabIndex={-1}>
        {flow && role !== "pharmacist" && (
          <nav className="path" aria-label="Your progress">
            {steps.map((s, i) => (
              <button
                key={s.id}
                className={`path-step ${view === s.id ? "on" : ""} ${i < at ? "past" : ""}`}
                disabled={!s.ready}
                aria-current={view === s.id ? "step" : undefined}
                onClick={() => setView(s.id)}
              >
                <span className="path-dot" aria-hidden="true" />
                {s.label}
              </button>
            ))}
          </nav>
        )}

        {configError && (
          <div className="inline-error" role="alert">
            {configError} <button className="text-button" onClick={() => location.reload()}>Try again</button>
          </div>
        )}

        {view === "login" && (
          <AuthView onDone={afterAuth} onGuest={() => setView("read")} />
        )}
        {view === "plans" && user && (
          <PlansView onOpen={(c) => openCase(c, c.items.some((i) => i.usable) && c.items.every((i) => i.usable) ? "guide" : "confirm")} goNew={() => setView("read")} />
        )}
        {view === "queue" && role === "pharmacist" && <QueueView />}
        {config && view === "settings" && (
          <SettingsView config={config} goLogin={() => setView("login")} onSignedOut={() => { startOver(); setView("read"); setConsent(false); }} />
        )}

        {config && view === "read" && (
          <ReadView
            config={config}
            consent={consent || Boolean(user)}
            onConsent={setConsent}
            onRead={(c) => openCase(c)}
          />
        )}
        {config && view === "confirm" && current && (
          <ConfirmView
            current={current}
            onChange={(c) => {
              setCurrent(c);
              setGuide(null);
            }}
            onContinue={() => setView("guide")}
            onStartOver={startOver}
            goLogin={() => setView("login")}
            goPlans={() => setView("plans")}
          />
        )}
        {config && view === "guide" && current && (
          <GuideView
            config={config}
            current={current}
            guide={guide}
            prefs={prefs}
            large={large}
            contrast={contrast}
            onGuide={setGuide}
            onPrefs={setPrefs}
            goLogin={() => setView("login")}
            goPlans={() => setView("plans")}
          />
        )}
        {view === "audit" && <AuditView onDeleted={() => { startOver(); setConsent(false); }} />}
      </main>

      <footer className="column footer">
        A student project tested on made-up prescriptions, not a medical device. {config?.disclaimer ?? "Not medical advice. Confirm with your pharmacist or doctor."}
      </footer>

      <nav className="tabbar" aria-label="Main">
        {tabs.map((t) => (
          <button key={t.id} className={tabOn(t.id) ? "tab on" : "tab"} aria-current={tabOn(t.id) ? "page" : undefined} onClick={() => setView(t.id)}>
            <svg viewBox="0 0 24 24" aria-hidden="true"><path d={t.icon} /></svg>
            <span>{t.label}</span>
          </button>
        ))}
      </nav>
    </ScenePrefsProvider>
  );
}

export function App() {
  return (
    <AuthProvider>
      <Shell />
    </AuthProvider>
  );
}

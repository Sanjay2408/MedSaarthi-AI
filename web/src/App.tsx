import { useEffect, useState } from "react";
import { api, type Case, type Config, type Guide, type GuidePrefs } from "./api";
import { Saarthi } from "./Saarthi";
import { AuditView } from "./views/AuditView";
import { ConfirmView } from "./views/ConfirmView";
import { GuideView } from "./views/GuideView";
import { ReadView } from "./views/ReadView";

export type View = "read" | "confirm" | "guide" | "audit";

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

export function App() {
  const [view, setView] = useState<View>("read");
  const [config, setConfig] = useState<Config | null>(null);
  const [configError, setConfigError] = useState("");
  const [current, setCurrent] = useState<Case | null>(null);
  const [guide, setGuide] = useState<Guide | null>(null);
  const [prefs, setPrefs] = useState<GuidePrefs>(DEFAULT_PREFS);
  const [consent, setConsent] = useState(false);
  const [large, setLarge] = useState(() => stored("ms-large"));
  const [contrast, setContrast] = useState(() => stored("ms-contrast"));

  useEffect(() => {
    api.config().then(setConfig).catch((e: Error) => setConfigError(e.message));
  }, []);

  useEffect(() => {
    const root = document.documentElement;
    root.toggleAttribute("data-large", large);
    root.toggleAttribute("data-contrast", contrast);
    store("ms-large", large);
    store("ms-contrast", contrast);
  }, [large, contrast]);

  useEffect(() => {
    window.scrollTo(0, 0);
  }, [view]);

  const startOver = () => {
    setCurrent(null);
    setGuide(null);
    setView("read");
  };

  const steps: { id: View; label: string; ready: boolean }[] = [
    { id: "read", label: "Add prescription", ready: true },
    { id: "confirm", label: "Check together", ready: current !== null },
    { id: "guide", label: "Your plan", ready: current?.items.some((i) => i.usable) ?? false },
  ];
  const at = steps.findIndex((s) => s.id === view);

  return (
    <>
      <header className="topbar">
        <div className="column topbar-inner">
          <button className="brand" onClick={startOver} aria-label="MedSaarthi, start again">
            <Saarthi mood="hello" size={34} />
            <span>MedSaarthi</span>
          </button>
          <div className="toggles">
            <button className="switch" role="switch" aria-checked={large} onClick={() => setLarge(!large)}>
              <span className="switch-track" aria-hidden="true" />
              Bigger text
            </button>
            <button className="switch" role="switch" aria-checked={contrast} onClick={() => setContrast(!contrast)}>
              <span className="switch-track" aria-hidden="true" />
              High contrast
            </button>
            <button className={view === "audit" ? "toplink on" : "toplink"} onClick={() => setView(view === "audit" ? (current ? "confirm" : "read") : "audit")}>
              {view === "audit" ? "Back to my plan" : "Your privacy"}
            </button>
          </div>
        </div>
      </header>

      <main className="column canvas">
        {view !== "audit" && (
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

        {config && view === "read" && (
          <ReadView
            config={config}
            consent={consent}
            onConsent={setConsent}
            onRead={(c) => {
              setCurrent(c);
              setGuide(null);
              setView("confirm");
            }}
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
          />
        )}
        {config && view === "guide" && current && (
          <GuideView config={config} current={current} guide={guide} prefs={prefs} large={large} contrast={contrast} onGuide={setGuide} onPrefs={setPrefs} />
        )}
        {view === "audit" && <AuditView onDeleted={() => { startOver(); setConsent(false); }} />}
      </main>

      <footer className="column footer">
        A student project tested on made-up prescriptions, not a medical device. {config?.disclaimer ?? "Not medical advice. Confirm with your pharmacist or doctor."}
      </footer>
    </>
  );
}

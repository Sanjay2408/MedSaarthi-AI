import { lazy, Suspense, useEffect, useState } from "react";
import type { Guide } from "../api";
import type { Words } from "../i18n";
import { SceneBoundary } from "../Saarthi";
import { useScenePrefs } from "../scene/prefs";

const Organizer3D = lazy(() => import("../scene/Organizer3D"));

// The signature element: the day as four tiles, from sunrise to night, each dose a thing to
// tick off. Morning and night are different places with different pictures, so they cannot be
// mistaken for each other, even by someone who reads with difficulty. Ticks are for today only
// and stay in this browser. There are no streaks or points: a missed dose must never feel like
// a lost game, and nothing here rewards taking more.
const PERIODS = ["Morning", "Afternoon", "Evening", "Night"] as const;

function PeriodArt({ period }: { period: string }) {
  if (period === "Morning") {
    return (
      <svg viewBox="0 0 96 48" aria-hidden="true" className="art">
        <path d="M24 44a24 24 0 0 1 48 0z" className="art-fill" />
        <path d="M48 8v8M18 20l6 5M78 20l-6 5M6 38h8M82 38h8" className="art-line" />
        <path d="M0 44h96" className="art-line" />
      </svg>
    );
  }
  if (period === "Afternoon") {
    return (
      <svg viewBox="0 0 96 48" aria-hidden="true" className="art">
        <circle cx="48" cy="24" r="13" className="art-fill" />
        <path d="M48 2v6M48 40v6M26 24h-6M76 24h-6M32 8l4 4M64 8l-4 4M32 40l4-4M64 40l-4-4" className="art-line" />
      </svg>
    );
  }
  if (period === "Evening") {
    return (
      <svg viewBox="0 0 96 48" aria-hidden="true" className="art">
        <path d="M30 34a18 18 0 0 1 36 0z" className="art-fill" />
        <path d="M0 34h96M14 42h68M30 48h36" className="art-line" />
      </svg>
    );
  }
  return (
    <svg viewBox="0 0 96 48" aria-hidden="true" className="art">
      <path d="M56 6a19 19 0 1 0 12 30A15 15 0 0 1 56 6z" className="art-fill" />
      <path d="M78 12l1.5 3.5 3.5 1.5-3.5 1.5L78 22l-1.5-3.5L73 17l3.5-1.5zM24 10l1 2.5 2.5 1-2.5 1-1 2.5-1-2.5-2.5-1 2.5-1zM16 32l1 2.5 2.5 1-2.5 1-1 2.5-1-2.5-2.5-1 2.5-1z" className="art-star" />
    </svg>
  );
}

function ticksKey(caseId: string) {
  return `ms-ticks-${caseId}-${new Date().toISOString().slice(0, 10)}`;
}

function loadTicks(caseId: string): string[] {
  try {
    return JSON.parse(localStorage.getItem(ticksKey(caseId)) ?? "[]");
  } catch {
    return [];
  }
}

export function DayPlan({ caseId, schedule, words, onProgress }: {
  caseId: string;
  schedule: Guide["schedule"];
  words: Words;
  onProgress: (done: number, total: number) => void;
}) {
  const [ticks, setTicks] = useState<string[]>(() => loadTicks(caseId));

  const doses = schedule.filter((s) => !s.as_needed).flatMap((s) =>
    s.times.map((t) => ({ key: `${s.medicine}|${s.dose}|${t.at}`, medicine: s.medicine, dose: s.dose, ...t })));
  const prn = schedule.filter((s) => s.as_needed);
  const live = doses.filter((d) => ticks.includes(d.key)).length;

  useEffect(() => {
    onProgress(live, doses.length);
    try {
      localStorage.setItem(ticksKey(caseId), JSON.stringify(ticks));
    } catch {
      /* private window: ticks last for this visit */
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ticks, doses.length, caseId, live]);

  const toggle = (key: string) => setTicks((t) => (t.includes(key) ? t.filter((k) => k !== key) : [...t, key]));

  const scene = useScenePrefs();
  const [selected, setSelected] = useState<string | null>(null);
  const names = [...new Set(doses.map((d) => d.medicine))];
  const slots = PERIODS.map((p) => ({
    period: p,
    doses: doses.filter((d) => d.period === p).map((d) => ({ key: d.key, hue: names.indexOf(d.medicine), done: ticks.includes(d.key) })),
  }));
  const hour = new Date().getHours();
  const now: (typeof PERIODS)[number] = hour < 11 ? "Morning" : hour < 16 ? "Afternoon" : hour < 20 ? "Evening" : "Night";
  const pick = (period: string) => {
    setSelected((s) => (s === period ? null : period));
    document.getElementById(`tile-${period}`)?.scrollIntoView({ block: "nearest", behavior: scene.still ? "auto" : "smooth" });
  };

  return (
    <section className="plan" aria-labelledby="today-heading">
      <h2 id="today-heading" className="sr-only">{words.today}</h2>
      {scene.mode === "3d" && doses.length > 0 && (
        <div className="organizer">
          <SceneBoundary fallback={null}>
            <Suspense fallback={<div className="organizer-wait" aria-hidden="true" />}>
              <Organizer3D slots={slots} selected={selected} now={now} onSelect={pick} speed={scene.speed} bounce={scene.bounce} still={scene.still} height={200} />
            </Suspense>
          </SceneBoundary>
          <p className="meta organizer-hint">Tap a lid to open it. The tiles below say the same in words.</p>
        </div>
      )}
      <div className="day">
        {PERIODS.map((p) => {
          const here = doses.filter((d) => d.period === p).sort((a, b) => a.at.localeCompare(b.at));
          return (
            <div key={p} id={`tile-${p}`} className={`tile tile-${p.toLowerCase()} ${here.length ? "" : "quiet"} ${selected === p ? "picked" : ""}`}>
              <PeriodArt period={p} />
              <h3>{words.periods[p]}</h3>
              {here.length === 0 && <p className="tile-empty">{words.nothing}</p>}
              <ul>
                {here.map((d) => {
                  const on = ticks.includes(d.key);
                  return (
                    <li key={d.key}>
                      <button className={on ? "dose-tick on" : "dose-tick"} role="checkbox" aria-checked={on} aria-label={`${d.label}, ${d.medicine} ${d.dose}. ${on ? words.done : words.markDone}`} onClick={() => toggle(d.key)}>
                        <span className="tick-box" aria-hidden="true">
                          <svg viewBox="0 0 20 20"><path d="M4 10.5l4 4 8-9" /></svg>
                        </span>
                        <span className="tick-text">
                          <span className="dose-time">{d.label}</span>
                          <span className="dose-med">{d.medicine} {d.dose}</span>
                        </span>
                      </button>
                    </li>
                  );
                })}
              </ul>
            </div>
          );
        })}
      </div>
      {prn.length > 0 && (
        <div className="prn">
          <h3>{words.needed}</h3>
          <ul>
            {prn.map((s) => <li key={s.medicine}><strong>{s.medicine} {s.dose}</strong> <span className="meta">{words.noFixed}</span></li>)}
          </ul>
        </div>
      )}
    </section>
  );
}

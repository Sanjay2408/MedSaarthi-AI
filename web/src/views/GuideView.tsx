import { useCallback, useEffect, useRef, useState } from "react";
import { api, type Case, type Config, type Guide, type GuidePrefs } from "../api";
import { SPEECH_LANG, WORDS, type Words } from "../i18n";
import { Says, type Mood } from "../Saarthi";
import { DayPlan } from "./DayStrip";
import { VerifyBadge } from "./PlansView";
import { SavePanel } from "./SavePanel";

const SHIFTS = [-120, -90, -60, -30, 0, 30, 60, 90, 120];
const shiftLabel = (m: number) => {
  if (m === 0) return "Usual times";
  const abs = Math.abs(m);
  const text = abs < 60 ? `${abs} min` : abs % 60 ? `${Math.floor(abs / 60)} h ${abs % 60} min` : `${abs / 60} h`;
  return m < 0 ? `${text} earlier` : `${text} later`;
};

function useVoice(lang: string) {
  const [has, setHas] = useState(false);
  useEffect(() => {
    if (!("speechSynthesis" in window)) return;
    const check = () => setHas(speechSynthesis.getVoices().some((v) => v.lang.toLowerCase().startsWith(lang.slice(0, 2))));
    check();
    speechSynthesis.addEventListener("voiceschanged", check);
    return () => speechSynthesis.removeEventListener("voiceschanged", check);
  }, [lang]);
  return has;
}

function ListenButton({ text, lang, words }: { text: string; lang: string; words: Words }) {
  const code = SPEECH_LANG[lang] ?? "en-IN";
  const has = useVoice(code);
  const [speaking, setSpeaking] = useState(false);
  useEffect(() => () => { if ("speechSynthesis" in window) speechSynthesis.cancel(); }, []);
  if (!has) return null;
  const toggle = () => {
    speechSynthesis.cancel();
    if (speaking) {
      setSpeaking(false);
      return;
    }
    const talk = new SpeechSynthesisUtterance(text);
    talk.lang = code;
    talk.rate = 0.9;
    talk.onend = () => setSpeaking(false);
    talk.onerror = () => setSpeaking(false);
    setSpeaking(true);
    speechSynthesis.speak(talk);
  };
  return (
    <button className="listen" onClick={toggle} aria-pressed={speaking}>
      <svg viewBox="0 0 20 20" aria-hidden="true"><path d="M3 8v4h3l4 3V5L6 8zM13 7.5a3.5 3.5 0 0 1 0 5M15 5a7 7 0 0 1 0 10" /></svg>
      {speaking ? words.stop : words.listen}
    </button>
  );
}

type Row = { key: string; label: string; text: string };

function CardRows({ rows, greeting, footer, lang }: { rows: Row[]; greeting?: string; footer?: string[]; lang: string }) {
  return (
    <div className="card" lang={lang}>
      {greeting && <p className="greeting">{greeting}</p>}
      <dl className="card-rows">
        {rows.map((r) => (
          <div key={r.key} className={`card-row row-${r.key}`}>
            <dt>{r.label}</dt>
            <dd>{r.text}</dd>
          </div>
        ))}
      </dl>
      {footer && footer.length > 0 && <ul className="card-footer">{footer.map((f, i) => <li key={i}>{f}</li>)}</ul>}
    </div>
  );
}

function Medicine({ med, words, languageName }: { med: Guide["medicines"][number]; words: Words; languageName: string }) {
  const tr = med.translation;
  const template = tr && tr.tier === "template" && !tr.blocked && tr.rows && tr.rows.length > 0 ? tr : null;
  const shown = tr && !tr.blocked ? tr.text : null;
  const englishRows = med.card && med.card.rows.length > 0 ? med.card : null;
  const spoken = template ? [template.greeting, ...template.rows!.map((r) => `${r.label}. ${r.text}`)].filter(Boolean).join(" ") : shown ?? med.english;
  const spokenLang = template || shown ? tr!.lang : "en";
  const draft = tr && !tr.reviewed && tr.lang !== "en";

  return (
    <article className="panel medicine" aria-label={med.name}>
      <header className="item-head">
        <h2>{med.name}</h2>
        <VerifyBadge v={med.verification} />
        <ListenButton text={spoken} lang={spokenLang} words={words} />
      </header>
      {med.blocked && <p className="notice compact">I've kept this one exactly as your prescription says it, so nothing gets changed in the wording.</p>}
      {tr?.blocked && <p className="notice compact">I couldn't be sure the {languageName} kept every number right, so I'm showing English here. Please ask your pharmacist to explain it.</p>}
      {template
        ? <CardRows rows={template.rows!} greeting={template.greeting} footer={template.footer} lang={tr!.lang} />
        : shown
          ? (
            <div className="guide-text" lang={tr!.lang}>
              {shown.split("\n").map((line, i) => (
                <p key={i} className={line === tr!.when ? "when" : ""}>{line}</p>
              ))}
            </div>
          )
          : englishRows
            ? <CardRows rows={englishRows.rows} greeting={englishRows.greeting} footer={englishRows.footer} lang="en" />
            : <div className="guide-text">{med.english.split("\n").map((line, i) => <p key={i}>{line}</p>)}</div>}
      {tr && tr.lang !== "en" && shown !== null && (
        <>
          <p className="meta">
            {tr.tier === "template"
              ? `Times, doses and days were written by code from your confirmed values, so they can't be mistranslated. ${draft ? "The surrounding words are a draft and have not been checked by a native speaker yet." : "A native speaker has reviewed this wording."}`
              : `${tr.note} Translated by ${tr.provider}, then checked: every number matches.`}
          </p>
          <details className="advanced">
            <summary>English</summary>
            <div className="guide-text small">{med.english.split("\n").map((line, i) => <p key={i}>{line}</p>)}</div>
          </details>
        </>
      )}
    </article>
  );
}

function scheduleText(guide: Guide): string {
  const lines = guide.schedule
    .filter((s) => !s.as_needed)
    .flatMap((s) => s.times.map((t) => `${t.label}: ${s.medicine} ${s.dose}`));
  return [`Medicine plan${guide.patient ? ` for ${guide.patient}` : ""}`, ...lines, "", guide.disclaimer].join("\n");
}

function ShareBar({ caseId, guide, canShare }: { caseId: string; guide: Guide; canShare: boolean }) {
  const text = scheduleText(guide);
  const share = async () => {
    try {
      await navigator.share({ title: "Medicine plan", text });
    } catch {
      /* the person closed the share sheet */
    }
  };
  return (
    <section className="panel share-bar" aria-labelledby="share-heading">
      <h2 id="share-heading">Take it with you</h2>
      <div className="share-actions">
        <a className="secondary" href={`/api/cases/${caseId}/reminders.ics`} download>Add reminders to my calendar</a>
        {canShare
          ? <button className="secondary" onClick={share}>Share my plan</button>
          : <a className="secondary" href={`https://wa.me/?text=${encodeURIComponent(text)}`} target="_blank" rel="noreferrer">Send on WhatsApp</a>}
        <a className="text-button" href={`/api/cases/${caseId}/plan.fhir.json`} download>For my doctor's software (FHIR)</a>
      </div>
      <p className="meta">The calendar file works with Google, Apple and Outlook calendars. Sharing sends only the times and medicine names, when you tap the button.</p>
    </section>
  );
}

export function GuideView({ config, current, guide, prefs, large, contrast, onGuide, onPrefs, goLogin, goPlans }: {
  config: Config;
  current: Case;
  guide: Guide | null;
  prefs: GuidePrefs;
  large: boolean;
  contrast: boolean;
  onGuide: (g: Guide) => void;
  onPrefs: (p: GuidePrefs) => void;
  goLogin: () => void;
  goPlans: () => void;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [progress, setProgress] = useState({ done: 0, total: 0 });
  const request = useRef(0);

  const load = useCallback(async () => {
    const mine = ++request.current;
    setBusy(true);
    setError("");
    try {
      const next = await api.guide(current.id, prefs);
      if (mine === request.current) onGuide(next);
    } catch (e) {
      if (mine === request.current) setError((e as Error).message);
    } finally {
      if (mine === request.current) setBusy(false);
    }
  }, [current.id, prefs, onGuide]);

  useEffect(() => { load(); }, [load]);

  const onProgress = useCallback((done: number, total: number) => setProgress({ done, total }), []);

  const language = config.languages.find((l) => l.code === prefs.lang)!;
  const words = WORDS[guide && !busy ? guide.prefs.lang : "en"] ?? WORDS.en;
  const flags = `large=${large}&contrast=${contrast}`;
  const name = current.patient;
  const allDone = progress.total > 0 && progress.done === progress.total;
  const lang = guide && !busy ? guide.prefs.lang : "en";
  const mood: Mood = busy ? "thinking" : allDone ? "happy" : "hello";
  const heading = busy
    ? "Writing your plan…"
    : allDone ? words.allDone : words.plan + (name && lang === "en" ? ` for ${name}` : "");
  const sub = busy
    ? prefs.lang === "en" ? "Putting it into plain words." : `Putting it into ${language.name}. This takes about 20 seconds for each medicine.`
    : `${words.today}: ${progress.done} ${words.of} ${progress.total}`;

  return (
    <>
      <Says mood={mood} live>
        <h1 lang={lang}>{heading}</h1>
        <p lang={lang}>{sub}</p>
      </Says>

      <div className="controls" role="group" aria-label="Plan settings">
        <div className="field inline">
          <label htmlFor="language">Language</label>
          <select id="language" value={prefs.lang} onChange={(e) => onPrefs({ ...prefs, lang: e.target.value })}>
            {config.languages.map((l) => <option key={l.code} value={l.code}>{l.native === l.name ? l.name : `${l.native} (${l.name})`}</option>)}
          </select>
        </div>
        <div className="field inline">
          <label htmlFor="shift">Fit it to my day</label>
          <select id="shift" value={prefs.shift_minutes} onChange={(e) => onPrefs({ ...prefs, shift_minutes: Number(e.target.value) })}>
            {SHIFTS.map((m) => <option key={m} value={m}>{shiftLabel(m)}</option>)}
          </select>
        </div>
        <div className="field inline">
          <span className="label" id="time-label">Clock</span>
          <div className="segmented small" role="group" aria-labelledby="time-label">
            {(["12h", "24h"] as const).map((f) => (
              <button key={f} className={prefs.time_format === f ? "on" : ""} aria-pressed={prefs.time_format === f} onClick={() => onPrefs({ ...prefs, time_format: f })}>{f === "12h" ? "12 hour" : "24 hour"}</button>
            ))}
          </div>
        </div>
        <div className="downloads">
          {guide && !busy ? (
            <>
              <a className="secondary" href={`/api/cases/${current.id}/guide.html?${flags}`} download>Full guide</a>
              <a className="primary" href={`/api/cases/${current.id}/schedule.pdf?${flags}`} download>Print my plan</a>
            </>
          ) : (
            <button className="primary" disabled>Print my plan</button>
          )}
        </div>
      </div>
      {prefs.shift_minutes !== 0 && <p className="meta shift-note">Please check new times with your pharmacist before you change them.</p>}

      {error && (
        <div className="inline-error" role="alert">
          {error} <button className="text-button" onClick={load}>Try again</button>
        </div>
      )}

      {guide ? (
        <div className={busy ? "guide stale" : "guide"}>
          <DayPlan caseId={current.id} schedule={guide.schedule} words={words} onProgress={onProgress} />
          <h2 className="section-title" lang={lang}>{words.howToTake}</h2>
          <div className="medicines">
            {guide.medicines.map((m) => <Medicine key={m.name} med={m} words={words} languageName={language.name} />)}
          </div>
          {guide.left_out.length > 0 && (
            <section className="panel left-out" aria-labelledby="left-out-heading">
              <h2 id="left-out-heading">Still waiting for your pharmacist</h2>
              <p>These aren't in your plan yet. Please don't take them based on this page until they've been checked.</p>
              <ul>
                {guide.left_out.map((m) => <li key={m.name}><strong>{m.name}.</strong> {m.reason}</li>)}
              </ul>
            </section>
          )}
          <ShareBar caseId={current.id} guide={guide} canShare={typeof navigator !== "undefined" && "share" in navigator} />
          <SavePanel current={current} goLogin={goLogin} goPlans={goPlans} />
          <p className="disclaimer">{guide.disclaimer}</p>
        </div>
      ) : !error && (
        <div className="guide" aria-hidden="true">
          <div className="panel skeleton tall" />
          <div className="panel skeleton" />
        </div>
      )}
    </>
  );
}

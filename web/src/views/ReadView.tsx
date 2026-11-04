import { useEffect, useId, useMemo, useState } from "react";
import { api, type Case, type Config, type Sample } from "../api";
import { Says } from "../Saarthi";

type Tab = "example" | "photo" | "typed";

const SCENES = [
  { id: "S02", title: "A clear prescription", note: "Two medicines, printed neatly." },
  { id: "S16", title: "A blurry photo", note: "Hard to read, like a rushed snapshot." },
  { id: "S19", title: "Something is missing", note: "The paper doesn't say how much." },
  { id: "S24", title: "A sneaky note", note: "A hidden line tries to change the dose." },
];

const NAMES: Record<Tab, string> = { example: "Try an example", photo: "Use a photo", typed: "Type it in" };

export function ReadView({ config, consent, onConsent, onRead }: {
  config: Config;
  consent: boolean;
  onConsent: (on: boolean) => void;
  onRead: (c: Case) => void;
}) {
  const [tab, setTab] = useState<Tab>("example");
  const [file, setFile] = useState<File | null>(null);
  const [typed, setTyped] = useState("");
  const [samples, setSamples] = useState<Sample[]>([]);
  const [sampleId, setSampleId] = useState("S24");
  const [sampleText, setSampleText] = useState("");
  const [useImage, setUseImage] = useState(true);
  const [patient, setPatient] = useState("");
  const [model, setModel] = useState(config.models[0]);
  const [variant, setVariant] = useState("v2");
  const [ocrMode, setOcrMode] = useState("auto");
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const fileHelp = useId();

  useEffect(() => {
    api.samples().then(setSamples).catch((e: Error) => setError(e.message));
  }, []);

  useEffect(() => {
    if (tab !== "example") return;
    let live = true;
    api.sample(sampleId).then((s) => {
      if (!live) return;
      setSampleText(s.text);
      setPatient(s.patient);
    }).catch((e: Error) => live && setError(e.message));
    return () => { live = false; };
  }, [sampleId, tab]);

  const preview = useMemo(() => (file ? URL.createObjectURL(file) : ""), [file]);
  useEffect(() => () => { if (preview) URL.revokeObjectURL(preview); }, [preview]);

  const hasInput = tab === "photo" ? file !== null : tab === "typed" ? typed.trim().length > 0 : true;
  const reason = !hasInput
    ? tab === "photo" ? "Choose a photo to carry on." : "Type the prescription to carry on."
    : !consent ? "Tick the box above to carry on." : "";

  const read = async () => {
    const form = new FormData();
    form.set("consent", "true");
    form.set("patient", patient);
    form.set("variant", variant);
    form.set("model", model);
    form.set("ocr_mode", ocrMode);
    if (tab === "photo" && file) form.set("file", file);
    if (tab === "typed") form.set("text", typed);
    if (tab === "example") {
      form.set("sample_id", sampleId);
      form.set("use_image", String(useImage));
    }
    const isImage = tab === "photo" || (tab === "example" && useImage);
    setBusy(isImage ? "Reading it carefully, line by line. This takes about 15 seconds." : "Reading it carefully. This takes a few seconds.");
    setError("");
    try {
      onRead(await api.read(form));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy("");
    }
  };

  return (
    <>
      <Says mood={busy ? "thinking" : "hello"} live={Boolean(busy)}>
        {busy ? (
          <>
            <h1>One moment…</h1>
            <p>{busy}</p>
          </>
        ) : (
          <>
            <h1>Hello, I'm Saarthi.</h1>
            <p>Let's make sense of your prescription, in plain words and in your language. If anything is unclear I won't guess. We'll check it with your pharmacist.</p>
          </>
        )}
      </Says>

      <div className="grid-read">
        <section className="panel" aria-labelledby="input-heading">
          <h2 id="input-heading">What would you like to show me?</h2>
          <div className="segmented" role="tablist" aria-label="How to add the prescription">
            {(Object.keys(NAMES) as Tab[]).map((id) => (
              <button key={id} role="tab" aria-selected={tab === id} className={tab === id ? "on" : ""} onClick={() => setTab(id)}>
                {NAMES[id]}
              </button>
            ))}
          </div>

          {tab === "photo" && (
            <div className="photo-pane">
              <label className="dropzone">
                <input
                  type="file"
                  accept="image/png,image/jpeg"
                  aria-describedby={fileHelp}
                  onChange={(e) => setFile(e.target.files?.[0] ?? null)}
                />
                {preview ? <img src={preview} alt="The prescription you chose" /> : <span className="drop-text">Tap to choose a photo</span>}
              </label>
              <p id={fileHelp} className="meta">PNG or JPEG, up to 10 MB. Please use a made-up prescription, not a real one.</p>
            </div>
          )}

          {tab === "typed" && (
            <div className="field">
              <label htmlFor="typed">Write what the prescription says</label>
              <textarea
                id="typed"
                rows={10}
                maxLength={5000}
                value={typed}
                onChange={(e) => setTyped(e.target.value)}
                placeholder={"Tab. Paracetamol 500 mg TDS x 5 days after food"}
              />
            </div>
          )}

          {tab === "example" && (
            <div className="example-pane">
              <div className="scenes" role="radiogroup" aria-label="Example prescriptions">
                {SCENES.map((s) => (
                  <button key={s.id} role="radio" aria-checked={s.id === sampleId} className={s.id === sampleId ? "scene on" : "scene"} onClick={() => setSampleId(s.id)}>
                    <strong>{s.title}</strong>
                    <span>{s.note}</span>
                  </button>
                ))}
              </div>
              <div className="sample-preview">
                {useImage
                  ? <img className="rx-image" src={`/api/samples/${sampleId}/image`} alt={`Example prescription ${sampleId}`} />
                  : <pre className="rx-text">{sampleText}</pre>}
                <div className="preview-row">
                  <div className="segmented small" role="group" aria-label="Show the example as">
                    <button className={useImage ? "on" : ""} aria-pressed={useImage} onClick={() => setUseImage(true)}>As a photo</button>
                    <button className={!useImage ? "on" : ""} aria-pressed={!useImage} onClick={() => setUseImage(false)}>As text</button>
                  </div>
                  <details className="advanced more">
                    <summary>All 25 examples</summary>
                    <div className="field">
                      <label htmlFor="all-samples">Example</label>
                      <select id="all-samples" value={sampleId} onChange={(e) => setSampleId(e.target.value)}>
                        {samples.map((s) => <option key={s.id} value={s.id}>{s.id}: {s.label}</option>)}
                      </select>
                    </div>
                  </details>
                </div>
              </div>
            </div>
          )}
        </section>

        <section className="panel side" aria-labelledby="before-heading">
          <h2 id="before-heading">Before we start</h2>
          <ul className="promise-list">
            <li><strong>I'm a helper, not a doctor.</strong> This is a student project, tested only on made-up prescriptions.</li>
            <li><strong>Please don't use a real prescription.</strong> The words I read are sent to an AI service (Groq) to be understood.</li>
            <li><strong>I don't keep your prescription.</strong> You can see what's logged under "Your privacy".</li>
            <li><strong>My translations are made by a computer</strong> and haven't been checked by a professional.</li>
          </ul>
          <label className="check">
            <input type="checkbox" checked={consent} onChange={(e) => onConsent(e.target.checked)} />
            <span>I understand and agree</span>
          </label>

          <div className="field">
            <label htmlFor="patient">What should I call you?</label>
            <input id="patient" value={patient} maxLength={60} onChange={(e) => setPatient(e.target.value)} autoComplete="off" placeholder="A nickname is fine" />
          </div>

          <div className="action-block">
            <button className="primary wide" disabled={Boolean(reason) || Boolean(busy)} onClick={read}>
              {busy ? "Reading…" : "Read my prescription"}
            </button>
            {reason && !busy && <p className="meta">{reason}</p>}
            {error && <div className="inline-error" role="alert">{error}</div>}
          </div>

          <details className="advanced">
            <summary>For evaluators: model and prompt</summary>
            <div className="field">
              <label htmlFor="model">Language model</label>
              <select id="model" value={model} onChange={(e) => setModel(e.target.value)}>
                {config.models.map((m) => <option key={m}>{m}</option>)}
              </select>
            </div>
            <div className="field">
              <label htmlFor="variant">Prompt</label>
              <select id="variant" value={variant} onChange={(e) => setVariant(e.target.value)}>
                {config.variants.map((v) => <option key={v.id} value={v.id}>{v.label}</option>)}
              </select>
            </div>
            <div className="field">
              <label htmlFor="ocr">Photo reading</label>
              <select id="ocr" value={ocrMode} onChange={(e) => setOcrMode(e.target.value)}>
                {config.ocr_modes.map((m) => <option key={m}>{m}</option>)}
              </select>
            </div>
          </details>
        </section>
      </div>
    </>
  );
}

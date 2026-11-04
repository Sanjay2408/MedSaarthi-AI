export type Field = { value: string | null; confidence: number };
export type FieldName = "name" | "dose" | "route" | "frequency" | "duration" | "instructions";
export type Item = {
  index: number;
  status: "CLEAR" | "NEEDS_CONFIRMATION" | "CONFIRMED";
  usable: boolean;
  reasons: { code: string; text: string }[];
  fields: Record<FieldName, Field>;
  frequency_plain: string | null;
};
export type Case = {
  id: string;
  patient: string;
  source: "text" | "image";
  has_image: boolean;
  ocr: { engine: string; mean_confidence: number; lines: { text: string; confidence: number }[] };
  injection_hits: string[];
  model: string;
  prompt: string;
  threshold: number;
  items: Item[];
};
export type Config = {
  models: string[];
  variants: { id: string; label: string }[];
  ocr_modes: string[];
  languages: { code: string; name: string; native: string }[];
  threshold: number;
  disclaimer: string;
};
export type Sample = { id: string; category: string; label: string; n_items: number };
export type Dose = { at: string; label: string; period: string };
export type Guide = {
  case_id: string;
  patient: string;
  prefs: GuidePrefs;
  schedule: { medicine: string; dose: string; as_needed: boolean; times: Dose[] }[];
  medicines: {
    name: string;
    english: string;
    blocked: boolean;
    model: string;
    prompt: string;
    translation: null | {
      lang: string;
      text: string | null;
      blocked: boolean;
      numbers_ok: boolean;
      similarity: number;
      note: string;
      when: string;
    };
  }[];
  left_out: { name: string; reason: string }[];
  disclaimer: string;
};
export type GuidePrefs = { lang: string; time_format: "12h" | "24h"; shift_minutes: number; variant: string; model?: string | null };
export type AuditRow = Record<string, string | number | boolean | null>;

export class ApiError extends Error {
  missing: string[];
  constructor(message: string, missing: string[] = []) {
    super(message);
    this.missing = missing;
  }
}

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(url, init);
  } catch {
    throw new ApiError("The MedSaarthi server is not responding. Check that it is running.");
  }
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new ApiError(typeof body.detail === "string" ? body.detail : "Something went wrong.", body.missing ?? []);
  }
  return res.json() as Promise<T>;
}

const json = (body: unknown): RequestInit => ({
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body),
});

export const api = {
  config: () => request<Config>("/api/config"),
  samples: () => request<Sample[]>("/api/samples"),
  sample: (id: string) => request<{ id: string; text: string; patient: string }>(`/api/samples/${id}`),
  read: (form: FormData) => request<Case>("/api/read", { method: "POST", body: form }),
  confirm: (caseId: string, index: number, fields: Record<string, string | null>) =>
    request<Case>(`/api/cases/${caseId}/items/${index}/confirm`, json({ fields })),
  guide: (caseId: string, prefs: GuidePrefs) => request<Guide>(`/api/cases/${caseId}/guide`, json(prefs)),
  audit: () => request<{ session: string; rows: AuditRow[] }>("/api/audit"),
  deleteSession: () => request<{ removed: number }>("/api/session", { method: "DELETE" }),
};

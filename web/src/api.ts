export type Field = { value: string | null; confidence: number };
export type FieldName = "name" | "dose" | "route" | "frequency" | "duration" | "instructions";
export type Verification = { kind: "self" | "pharmacist"; by: string | null; at: string | null };
export type Item = {
  index: number;
  status: "CLEAR" | "NEEDS_CONFIRMATION" | "CONFIRMED";
  usable: boolean;
  reasons: { code: string; text: string }[];
  fields: Record<FieldName, Field>;
  frequency_plain: string | null;
  verification: Verification | null;
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
  plan_id?: string;
  profile_id?: number;
};
export type Language = { code: string; name: string; native: string; reviewed: boolean };
export type Config = {
  models: string[];
  variants: { id: string; label: string }[];
  ocr_modes: string[];
  languages: Language[];
  threshold: number;
  disclaimer: string;
};
export type Sample = { id: string; category: string; label: string; n_items: number };
export type Card = {
  lang: string;
  reviewed: boolean;
  greeting: string;
  rows: { key: string; label: string; text: string }[];
  footer: string[];
  untranslated: string | null;
};
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
    verification: Verification | null;
    card: Card | null;
    translation: null | (Partial<Card> & {
      lang: string;
      tier: "template" | "mt";
      reviewed: boolean;
      text: string | null;
      blocked: boolean;
      numbers_ok: boolean;
      note: string;
      when: string;
      provider: string;
    });
  }[];
  left_out: { name: string; reason: string }[];
  disclaimer: string;
};
export type GuidePrefs = { lang: string; time_format: "12h" | "24h"; shift_minutes: number; variant: string; model?: string | null };
export type AuditRow = Record<string, string | number | boolean | null>;

export type Role = "patient" | "caregiver" | "pharmacist";
export type AgeBand = "child" | "adult" | "senior";
export type Profile = {
  id: number;
  display_name: string;
  relation: string;
  age_band: AgeBand;
  language: string;
  time_format: "12h" | "24h";
  large_text: boolean;
  high_contrast: boolean;
  reduce_motion: boolean;
  voice_first: boolean;
  is_default: boolean;
};
export type Me = { user: null | { id: number; name: string; email: string; role: Role; consent_version: string | null }; profiles: Profile[] };
export type PlanSummary = {
  id: string;
  profile_id: number;
  profile_name: string;
  title: string;
  created_at: string;
  n_items: number;
  items: { index: number; name: string; status: Item["status"]; verification: Verification | null }[];
  reviews: { id: number; item_index: number; status: "pending" | "verified" | "declined"; reviewer: string | null; note: string | null }[];
  pending: number;
};
export type QueueItem = {
  id: number;
  plan_id: string;
  item_index: number;
  status: "pending" | "verified" | "declined";
  requested_at: string;
  reviewed_at: string | null;
  patient: string;
  source: string;
  item: Item;
  ocr_lines: { text: string; confidence: number }[];
  injection_hits: string[];
  reviewed_by: string | null;
};

export class ApiError extends Error {
  missing: string[];
  status: number;
  constructor(message: string, status = 0, missing: string[] = []) {
    super(message);
    this.missing = missing;
    this.status = status;
  }
}

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(url, init);
  } catch {
    throw new ApiError("The MedSaarthi server is not responding. Check your connection and try again.");
  }
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new ApiError(typeof body.detail === "string" ? body.detail : "Something went wrong.", res.status, body.missing ?? []);
  }
  return res.json() as Promise<T>;
}

const send = (method: string, body?: unknown): RequestInit => ({
  method,
  headers: { "Content-Type": "application/json" },
  body: body === undefined ? undefined : JSON.stringify(body),
});

export const api = {
  config: () => request<Config>("/api/config"),
  samples: () => request<Sample[]>("/api/samples"),
  sample: (id: string) => request<{ id: string; text: string; patient: string }>(`/api/samples/${id}`),
  read: (form: FormData) => request<Case>("/api/read", { method: "POST", body: form }),
  confirm: (caseId: string, index: number, fields: Record<string, string | null>) =>
    request<Case>(`/api/cases/${caseId}/items/${index}/confirm`, send("POST", { fields })),
  guide: (caseId: string, prefs: GuidePrefs) => request<Guide>(`/api/cases/${caseId}/guide`, send("POST", prefs)),
  audit: () => request<{ session: string; rows: AuditRow[] }>("/api/audit"),
  deleteSession: () => request<{ removed: number }>("/api/session", { method: "DELETE" }),

  me: () => request<Me>("/api/auth/me"),
  signup: (body: { email: string; password: string; name: string; role: Role; invite?: string; agree: boolean; language?: string }) =>
    request<Me>("/api/auth/signup", send("POST", body)),
  login: (email: string, password: string) => request<Me>("/api/auth/login", send("POST", { email, password })),
  logout: () => request<{ ok: boolean }>("/api/auth/logout", send("POST")),
  deleteAccount: (password: string) => request<{ ok: boolean }>("/api/auth/account", send("DELETE", { password })),

  addProfile: (body: Partial<Profile> & { display_name: string }) => request<Profile>("/api/profiles", send("POST", body)),
  patchProfile: (id: number, body: Partial<Profile>) => request<Profile>(`/api/profiles/${id}`, send("PATCH", body)),
  removeProfile: (id: number) => request<{ ok: boolean }>(`/api/profiles/${id}`, send("DELETE")),

  savePlan: (body: { case_id: string; profile_id: number; title?: string; share_with_pharmacist: boolean }) =>
    request<PlanSummary>("/api/plans", send("POST", body)),
  plans: () => request<PlanSummary[]>("/api/plans"),
  openPlan: (id: string) => request<Case>(`/api/plans/${id}/open`, send("POST")),
  askReview: (id: string, scope: "held" | "all") => request<PlanSummary>(`/api/plans/${id}/review`, send("POST", { scope })),
  deletePlan: (id: string) => request<{ ok: boolean }>(`/api/plans/${id}`, send("DELETE")),

  queue: (status: "pending" | "done") => request<QueueItem[]>(`/api/review/queue?status=${status}`),
  verify: (id: number, fields: Record<string, string | null>) => request<QueueItem>(`/api/review/${id}/verify`, send("POST", { fields })),
  decline: (id: number, note: string) => request<QueueItem>(`/api/review/${id}/decline`, send("POST", { note })),
};

/** The server stores UTC without a zone suffix. Without it, browsers read the time as local. */
export const parseTime = (iso: string) => new Date(/Z|[+-]\d\d:?\d\d$/.test(iso) ? iso : `${iso}Z`);

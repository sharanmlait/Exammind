export const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export async function api<T = any>(path: string, opts: { method?: string; body?: any; form?: FormData } = {}): Promise<T> {
  const init: RequestInit = { method: opts.method || (opts.body || opts.form ? "POST" : "GET") };
  if (opts.form) init.body = opts.form;
  else if (opts.body !== undefined) {
    init.body = JSON.stringify(opts.body);
    init.headers = { "Content-Type": "application/json" };
  }
  let res: Response;
  try {
    res = await fetch(`${API}/api${path}`, init);
  } catch {
    throw new Error(`Cannot reach the backend at ${API}. Is it running? (uvicorn app.main:app --reload)`);
  }
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail ? (typeof data.detail === "string" ? data.detail : JSON.stringify(data.detail)) : res.statusText);
  return data as T;
}

export function sendFeedback(subject_id: number, kind: string, prompt: string, response: string, rating: 1 | -1) {
  return api("/feedback", { body: { subject_id, kind, prompt, response, rating } }).catch(() => {});
}

export type Source = { id: string; document: string; page: number | null; text: string; score: number };

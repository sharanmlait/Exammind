"use client";
import { useState } from "react";
import { Source, sendFeedback } from "@/lib/api";

export function Spinner({ label = "Thinking" }: { label?: string }) {
  return <span className="muted small"><span className="spinner" /> {label}…</span>;
}

export function Sources({ sources, highlight }: { sources: Source[]; highlight?: string | null }) {
  const [open, setOpen] = useState(false);
  if (!sources?.length) return null;
  return (
    <div className="sources">
      <button className="link small" onClick={() => setOpen(!open)}>
        {open ? "Hide" : "Show"} {sources.length} sources
      </button>
      {(open || highlight) &&
        sources.filter((s) => open || s.id === highlight).map((s) => (
          <div key={s.id} className={`source ${s.id === highlight ? "hl" : ""}`}>
            <strong>{s.id}</strong> · {s.document}{s.page ? `, page ${s.page}` : ""} · <span className="muted">relevance {s.score}</span>
            <div>{s.text.length > 420 ? s.text.slice(0, 420) + "…" : s.text}</div>
          </div>
        ))}
    </div>
  );
}

export function Feedback({ subjectId, kind, prompt, response }: { subjectId: number; kind: string; prompt: string; response: string }) {
  const [sent, setSent] = useState<number | null>(null);
  const send = (r: 1 | -1) => { setSent(r); sendFeedback(subjectId, kind, prompt, response, r); };
  if (sent) return <span className="muted small">Thanks — feedback saved{sent < 0 ? " for review" : ""}.</span>;
  return (
    <span className="row small muted">
      Helpful?
      <button className="secondary small" onClick={() => send(1)}>👍</button>
      <button className="secondary small" onClick={() => send(-1)}>👎</button>
    </span>
  );
}

export function useAsync<T>() {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const run = async (fn: () => Promise<T>) => {
    setLoading(true); setError(null);
    try { const d = await fn(); setData(d); return d; }
    catch (e: any) { setError(e.message); return null; }
    finally { setLoading(false); }
  };
  return { data, setData, loading, error, run };
}

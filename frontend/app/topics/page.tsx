"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Markdown } from "@/lib/md";
import { useSubject } from "@/components/SubjectContext";
import { NeedSubject } from "@/components/Shell";
import { Spinner } from "@/components/ui";

type Pred = { topic: string; unit: string; probability: number; times_asked: number; last_asked: number | null; reasons: string[] };
type Q = { id: number; year: number; marks: number; text: string; topic: string; confidence: number };

export default function Topics() {
  const { current } = useSubject();
  const [tab, setTab] = useState<"hot" | "pyq" | "terms">("hot");
  const [hot, setHot] = useState<any>(null);
  const [qs, setQs] = useState<Q[]>([]);
  const [topics, setTopics] = useState<{ name: string; unit: string; times_asked: number }[]>([]);
  const [terms, setTerms] = useState<any>(null);
  const [summary, setSummary] = useState<{ topic: string; text: string } | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [filter, setFilter] = useState("");

  useEffect(() => {
    if (!current) return;
    setHot(null); setSummary(null);
    api(`/subjects/${current.id}/hot-topics?limit=30`).then(setHot).catch(() => {});
    api(`/subjects/${current.id}/questions`).then(setQs).catch(() => {});
    api(`/subjects/${current.id}/topics`).then(setTopics).catch(() => {});
    api(`/subjects/${current.id}/keyterms`).then(setTerms).catch(() => {});
  }, [current?.id]);

  const summarize = async (topic: string) => {
    if (!current) return;
    setBusy(topic);
    try { const r = await api(`/subjects/${current.id}/summarize`, { body: { topic } }); setSummary({ topic, text: r.summary }); }
    finally { setBusy(null); }
  };

  const relabel = async (q: Q, topic: string) => {
    if (!current) return;
    await api(`/subjects/${current.id}/questions/${q.id}`, { method: "PUT", body: { topic } });
    setQs((all) => all.map((x) => (x.id === q.id ? { ...x, topic, confidence: 1 } : x)));
  };

  const shown = qs.filter((q) => !filter || q.topic === filter);

  return (
    <NeedSubject>
      <h1>Hot topics & past papers</h1>
      <p className="sub">A gradient-boosted model learns from past papers which topics come back, using features like
        "asked last year", "skipped for two years" and the unit's share of marks. It is back-tested on the most recent paper.</p>
      <div className="tabs">
        <button className={tab === "hot" ? "on" : ""} onClick={() => setTab("hot")}>Predictions</button>
        <button className={tab === "pyq" ? "on" : ""} onClick={() => setTab("pyq")}>Tagged questions ({qs.length})</button>
        <button className={tab === "terms" ? "on" : ""} onClick={() => setTab("terms")}>Key terms & formulas</button>
      </div>

      {summary && (
        <div className="card">
          <div className="row" style={{ justifyContent: "space-between" }}><h2>{summary.topic} — quick revision</h2>
            <button className="link" onClick={() => setSummary(null)}>close</button></div>
          <Markdown text={summary.text} />
        </div>
      )}

      {tab === "hot" && (
        <div className="card">
          {!hot ? <Spinner label="Running model" /> : !hot.predictions.length ? (
            <p className="muted">Upload a syllabus and a few years of past papers to get predictions.</p>
          ) : (
            <>
              <div className="row small muted" style={{ marginBottom: 12 }}>
                <span>Predicting <strong>{hot.target_year}</strong> from {hot.years_seen.join(", ")}</span>·
                <span>model {hot.model}</span>
                {hot.backtest && <span>· back-test on {hot.backtest.test_year}: precision@{hot.backtest.k} = {hot.backtest.precision_at_k}{hot.backtest.auc ? `, AUC ${hot.backtest.auc}` : ""}</span>}
              </div>
              <table>
                <thead><tr><th style={{ width: "34%" }}>Topic</th><th style={{ width: "22%" }}>Chance</th><th>Why</th><th></th></tr></thead>
                <tbody>{hot.predictions.map((p: Pred) => (
                  <tr key={p.topic}>
                    <td><strong>{p.topic}</strong><div className="muted small">{p.unit} · asked {p.times_asked}× · last {p.last_asked ?? "never"}</div></td>
                    <td><div className="bar"><div style={{ width: `${Math.round(p.probability * 100)}%` }} /></div>
                      <span className="small">{Math.round(p.probability * 100)}%</span></td>
                    <td className="small">{p.reasons.join(" · ") || "—"}</td>
                    <td><button className="link small" onClick={() => summarize(p.topic)} disabled={!!busy}>
                      {busy === p.topic ? <Spinner label="" /> : "revise"}</button></td>
                  </tr>))}
                </tbody>
              </table>
            </>
          )}
        </div>
      )}

      {tab === "pyq" && (
        <div className="card">
          <div className="row" style={{ marginBottom: 10 }}>
            <select value={filter} onChange={(e) => setFilter(e.target.value)}>
              <option value="">All topics</option>
              {topics.map((t) => <option key={t.name} value={t.name}>{t.name} ({t.times_asked})</option>)}
            </select>
            <span className="muted small">Wrong tag? Fix it — corrections become training labels for the classifier.</span>
          </div>
          <table>
            <thead><tr><th>Year</th><th>Marks</th><th>Question</th><th>Topic (auto-tagged)</th></tr></thead>
            <tbody>{shown.map((q) => (
              <tr key={q.id}>
                <td>{q.year}</td><td>{q.marks ?? "—"}</td><td>{q.text}</td>
                <td>
                  <select value={q.topic} onChange={(e) => relabel(q, e.target.value)} style={{ maxWidth: 210 }}>
                    {topics.map((t) => <option key={t.name}>{t.name}</option>)}
                  </select>
                  <div className="small muted">{q.confidence >= 1 ? "✓ confirmed" : `${Math.round(q.confidence * 100)}% confident`}</div>
                </td>
              </tr>))}
            </tbody>
          </table>
        </div>
      )}

      {tab === "terms" && terms && (
        <div className="grid" style={{ gridTemplateColumns: "1fr 1fr" }}>
          <div className="card" style={{ margin: 0 }}>
            <h2>Definitions</h2>
            {terms.definitions.map((d: any) => (
              <p key={d.term} className="small"><strong>{d.term}</strong> — {d.definition} <span className="muted">(p.{d.page})</span></p>))}
          </div>
          <div>
            <div className="card">
              <h2>Formulas</h2>
              {terms.formulas.map((f: any) => <p key={f.formula}><code>{f.formula}</code></p>)}
            </div>
            <div className="card">
              <h2>Key terms</h2>
              <div className="row">{terms.terms.map((t: any) => <span key={t.term} className="badge">{t.term}</span>)}</div>
            </div>
          </div>
        </div>
      )}
    </NeedSubject>
  );
}

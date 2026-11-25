"use client";
import { Suspense, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { api } from "@/lib/api";
import { Markdown } from "@/lib/md";
import { useSubject } from "@/components/SubjectContext";
import { NeedSubject } from "@/components/Shell";
import { Feedback, Spinner, useAsync } from "@/components/ui";

function Grader() {
  const { current } = useSubject();
  const params = useSearchParams();
  const [q, setQ] = useState("");
  const [ans, setAns] = useState("");
  const [max, setMax] = useState(10);
  const [showRef, setShowRef] = useState(false);
  const { data, loading, error, run } = useAsync<any>();

  useEffect(() => {
    const pq = params.get("q"); const pm = params.get("m");
    if (pq) setQ(pq);
    if (pm) setMax(Number(pm));
  }, [params]);

  const go = () => run(() => api(`/subjects/${current!.id}/grade`, { body: { question: q, answer: ans, max_marks: max } }));
  const pct = data ? data.score / data.max_score : 0;

  return (
    <NeedSubject>
      <h1>Grade my answer</h1>
      <p className="sub">Your score blends an LLM examiner (60%), semantic similarity to a model answer from your notes (25%) and
        key-point coverage (15%), so keyword-stuffing alone won't get marks. Results feed your weak-topic list.</p>
      <div className="card stack">
        <input placeholder="Question" value={q} onChange={(e) => setQ(e.target.value)} style={{ width: "100%" }} />
        <textarea placeholder="Write your answer like you would in the exam…" value={ans} onChange={(e) => setAns(e.target.value)} style={{ minHeight: 180 }} />
        <div className="row">
          <span className="muted">Out of</span>
          <select value={max} onChange={(e) => setMax(Number(e.target.value))}>{[2, 5, 10].map((m) => <option key={m}>{m}</option>)}</select>
          <span className="muted small">{ans.trim() ? ans.trim().split(/\s+/).length : 0} words</span>
          <button className="accent" style={{ marginLeft: "auto" }} onClick={go} disabled={loading || !q.trim() || !ans.trim()}>
            {loading ? <Spinner label="Examiner is reading" /> : "Grade"}</button>
        </div>
      </div>
      {error && <div className="alert error">{error}</div>}
      {data && (
        <div className="card stack">
          <div className="row" style={{ justifyContent: "space-between" }}>
            <div><span className="stat" style={{ color: pct >= 0.6 ? "var(--good)" : pct >= 0.4 ? "var(--accent)" : "var(--bad)" }}>
              {data.score}</span><span className="muted"> / {data.max_score}</span></div>
            {data.topic && <span className="badge">{data.topic}</span>}
          </div>
          {data.breakdown && (
            <div className="row small muted">
              {Object.entries(data.breakdown).map(([k, v]) => <span key={k} className="badge">{k.replace(/_/g, " ")}: {v === null ? "n/a" : Math.round((v as number) * 100) + "%"}</span>)}
            </div>
          )}
          <p>{data.feedback}</p>
          {data.strengths?.length > 0 && <div><h3>What you got right</h3><ul>{data.strengths.map((s: string) => <li key={s}>{s}</li>)}</ul></div>}
          {data.missing_points?.length > 0 && <div><h3>Missing points</h3><ul>{data.missing_points.map((s: string) => <li key={s}>{s}</li>)}</ul></div>}
          <button className="link" onClick={() => setShowRef(!showRef)}>{showRef ? "Hide" : "Show"} model answer</button>
          {showRef && <div className="source"><Markdown text={data.reference_answer} /></div>}
          <Feedback subjectId={current!.id} kind="grade" prompt={q} response={JSON.stringify({ score: data.score })} />
        </div>
      )}
    </NeedSubject>
  );
}

export default function GradePage() {
  return <Suspense fallback={<Spinner label="Loading" />}><Grader /></Suspense>;
}

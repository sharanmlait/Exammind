"use client";
import { useState } from "react";
import { api } from "@/lib/api";
import { Markdown } from "@/lib/md";
import { useSubject } from "@/components/SubjectContext";
import { NeedSubject } from "@/components/Shell";
import { Feedback, Sources, Spinner, useAsync } from "@/components/ui";

export default function Answer() {
  const { current } = useSubject();
  const [q, setQ] = useState("");
  const [marks, setMarks] = useState(5);
  const [hl, setHl] = useState<string | null>(null);
  const { data, loading, error, run } = useAsync<any>();

  const go = () => current && q.trim() && run(() => api(`/subjects/${current.id}/answer`, { body: { question: q, marks } }));

  return (
    <NeedSubject>
      <h1>Exam-style answers</h1>
      <p className="sub">Introduction → numbered points → diagram hint → conclusion, with the length matched to the marks.
        After you fine-tune your own model this page uses it (see <code>training/README.md</code>).</p>
      <div className="card stack">
        <textarea placeholder="Paste an exam question, e.g. Explain the Banker's algorithm with an example." value={q}
                  onChange={(e) => setQ(e.target.value)} style={{ minHeight: 80 }} />
        <div className="row">
          <span className="muted">Marks</span>
          {[2, 5, 10].map((m) => (
            <button key={m} className={marks === m ? "" : "secondary"} onClick={() => setMarks(m)}>{m}</button>
          ))}
          <button className="accent" onClick={go} disabled={loading || !q.trim()} style={{ marginLeft: "auto" }}>
            {loading ? <Spinner label="Writing" /> : "Write answer"}
          </button>
        </div>
      </div>
      {error && <div className="alert error">{error}</div>}
      {data && (
        <div className="card">
          <div className="row" style={{ justifyContent: "space-between", marginBottom: 8 }}>
            <span className="badge accent">{data.marks} marks</span>
            <span className="muted small">model {data.model} · {data.latency_ms} ms · ~{data.answer.split(/\s+/).length} words</span>
          </div>
          {data.warnings?.map((w: string) => <div key={w} className="alert warn small">{w}</div>)}
          <Markdown text={data.answer} onCite={(id) => setHl(hl === id ? null : id)} />
          <Sources sources={data.sources} highlight={hl} />
          <div style={{ marginTop: 10 }}><Feedback subjectId={current!.id} kind="answer" prompt={data.question} response={data.answer} /></div>
        </div>
      )}
    </NeedSubject>
  );
}

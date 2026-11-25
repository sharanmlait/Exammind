"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import { useSubject } from "@/components/SubjectContext";
import { NeedSubject } from "@/components/Shell";
import { Spinner, useAsync } from "@/components/ui";

export default function Practice() {
  const { current } = useSubject();
  const [topics, setTopics] = useState<string[]>([]);
  const [topic, setTopic] = useState("");
  const [kind, setKind] = useState<"mcq" | "short">("mcq");
  const [n, setN] = useState(5);
  const [picked, setPicked] = useState<Record<number, number>>({});
  const { data, loading, error, run, setData } = useAsync<any>();

  useEffect(() => {
    if (!current) return;
    setData(null);
    api(`/subjects/${current.id}/topics`).then((t) => { setTopics(t.map((x: any) => x.name)); setTopic(t[0]?.name || ""); }).catch(() => {});
  }, [current?.id]);

  const go = () => { setPicked({}); run(() => api(`/subjects/${current!.id}/practice`, { body: { topic, n, kind } })); };
  const qs = data?.questions || [];
  const answered = Object.keys(picked).length;
  const score = qs.reduce((s: number, q: any, i: number) => s + (picked[i] === q.answer_index ? 1 : 0), 0);

  return (
    <NeedSubject>
      <h1>Practice</h1>
      <p className="sub">Questions are generated from your notes on the chosen topic. MCQs are checked for exactly 4 distinct options and one correct answer.</p>
      <div className="card row">
        <select value={topic} onChange={(e) => setTopic(e.target.value)} style={{ minWidth: 240 }}>
          {topics.map((t) => <option key={t}>{t}</option>)}
        </select>
        <select value={kind} onChange={(e) => setKind(e.target.value as any)}>
          <option value="mcq">MCQs</option><option value="short">Short answer</option>
        </select>
        <select value={n} onChange={(e) => setN(Number(e.target.value))}>
          {[3, 5, 10].map((x) => <option key={x} value={x}>{x} questions</option>)}
        </select>
        <button className="accent" onClick={go} disabled={loading || !topic}>{loading ? <Spinner label="Generating" /> : "Generate"}</button>
      </div>
      {error && <div className="alert error">{error}</div>}
      {data?.error && <div className="alert error">{data.error}</div>}
      {data && data.kind === "mcq" && qs.length > 0 && (
        <>
          {answered === qs.length && <div className="alert ok">Score: {score} / {qs.length}</div>}
          {qs.map((q: any, i: number) => (
            <div className="card" key={i}>
              <h3>{i + 1}. {q.question}</h3>
              {q.options.map((o: string, j: number) => {
                const done = picked[i] !== undefined;
                const cls = !done ? "" : j === q.answer_index ? "right" : picked[i] === j ? "wrong" : "";
                return <button key={j} className={`option ${cls}`} disabled={done} onClick={() => setPicked({ ...picked, [i]: j })}>
                  {String.fromCharCode(65 + j)}. {o}</button>;
              })}
              {picked[i] !== undefined && <p className="small muted" style={{ marginTop: 10 }}>{q.explanation}</p>}
            </div>
          ))}
        </>
      )}
      {data && data.kind === "short" && qs.map((q: any, i: number) => (
        <details className="card" key={i}>
          <summary><strong>{i + 1}. {q.question}</strong> <span className="badge">{q.marks} marks</span></summary>
          <p className="small" style={{ marginTop: 10 }}>{q.model_answer}</p>
          <Link href={`/grade?q=${encodeURIComponent(q.question)}&m=${q.marks}`} className="small">Write your answer and get graded →</Link>
        </details>
      ))}
    </NeedSubject>
  );
}

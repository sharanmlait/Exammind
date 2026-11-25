"use client";
import Link from "next/link";
import { useState } from "react";
import { api } from "@/lib/api";
import { useSubject } from "@/components/SubjectContext";
import { Spinner } from "@/components/ui";

const FEATURES = [
  ["/chat", "Ask your notes", "RAG chat with page-level citations. English, Hindi or Hinglish."],
  ["/answer", "Exam answers", "Answers sized for 2, 5 or 10 marks, from your fine-tuned model."],
  ["/topics", "Hot topics", "ML predicts what's likely this year from past papers."],
  ["/practice", "Practice", "Auto-generated MCQs and short questions from any chapter."],
  ["/grade", "Grade my answer", "Semantic similarity + rubric-based LLM examiner."],
  ["/plan", "Study plan", "An AI agent builds a day-by-day plan around weak and hot topics."],
];

export default function Home() {
  const { subjects, current, select, refresh } = useSubject();
  const [name, setName] = useState("");
  const [busy, setBusy] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const create = async () => {
    if (name.trim().length < 2) return;
    setBusy("create"); setErr(null);
    try { const s = await api("/subjects", { body: { name } }); setName(""); await refresh(); select(s.id); }
    catch (e: any) { setErr(e.message); } finally { setBusy(null); }
  };
  const demo = async () => {
    setBusy("demo"); setErr(null);
    try { const r = await api("/demo/seed", { method: "POST" }); await refresh(); select(r.subject_id); }
    catch (e: any) { setErr(e.message); } finally { setBusy(null); }
  };

  return (
    <div>
      <h1>Study smarter for your semester exams</h1>
      <p className="sub">Upload your syllabus, notes and previous year papers. ExamMind answers from <em>your</em> material,
        predicts important topics, quizzes you and grades your answers.</p>
      {err && <div className="alert error">{err}</div>}

      <div className="card">
        <h2>Subjects</h2>
        <div className="row">
          <input placeholder="e.g. Operating Systems" value={name} onChange={(e) => setName(e.target.value)}
                 onKeyDown={(e) => e.key === "Enter" && create()} style={{ flex: 1, minWidth: 220 }} />
          <button onClick={create} disabled={!!busy}>Create subject</button>
          <button className="accent" onClick={demo} disabled={!!busy}>
            {busy === "demo" ? <Spinner label="Loading demo" /> : "Load OS demo"}
          </button>
        </div>
        {subjects.length > 0 && (
          <table style={{ marginTop: 16 }}>
            <thead><tr><th>Subject</th><th>Documents</th><th>Topics</th><th>Past questions</th><th></th></tr></thead>
            <tbody>
              {subjects.map((s) => (
                <tr key={s.id}>
                  <td><strong>{s.name}</strong></td><td>{s.documents}</td><td>{s.topics}</td><td>{s.questions}</td>
                  <td>{current?.id === s.id ? <span className="badge accent">selected</span>
                    : <button className="link" onClick={() => select(s.id)}>select</button>}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        {current && current.documents === 0 && (
          <div className="alert warn" style={{ marginTop: 14 }}>
            Next: <Link href="/library">upload your syllabus, notes and PYQs</Link> for {current.name}.
          </div>
        )}
      </div>

      <div className="grid">
        {FEATURES.map(([href, title, desc]) => (
          <Link key={href} href={href} className="card" style={{ textDecoration: "none", color: "inherit", margin: 0 }}>
            <h3>{title}</h3><p className="muted small" style={{ margin: 0 }}>{desc}</p>
          </Link>
        ))}
      </div>
    </div>
  );
}

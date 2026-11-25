"use client";
import { useState } from "react";
import { api } from "@/lib/api";
import { useSubject } from "@/components/SubjectContext";
import { NeedSubject } from "@/components/Shell";
import { Spinner, useAsync } from "@/components/ui";

export default function Plan() {
  const { current } = useSubject();
  const [days, setDays] = useState(7);
  const [hours, setHours] = useState(3);
  const [goal, setGoal] = useState("");
  const [trace, setTrace] = useState(false);
  const { data, loading, error, run } = useAsync<any>();

  const go = () => run(() => api(`/subjects/${current!.id}/plan`, { body: { days, hours_per_day: hours, goal } }));

  return (
    <NeedSubject>
      <h1>Study plan</h1>
      <p className="sub">An AI agent decides which tools to call (syllabus, hot-topic model, your weak topics) and then builds a
        day-by-day plan. High-chance and weak topics get double sessions, and the last day is for revision and a mock test.</p>
      <div className="card row">
        <label className="row">Exam in <input type="number" min={1} max={60} value={days} onChange={(e) => setDays(Number(e.target.value))} style={{ width: 70 }} /> days</label>
        <label className="row"><input type="number" min={0.5} max={14} step={0.5} value={hours} onChange={(e) => setHours(Number(e.target.value))} style={{ width: 70 }} /> hours/day</label>
        <input placeholder="Anything else? e.g. I'm weak in deadlocks" value={goal} onChange={(e) => setGoal(e.target.value)} style={{ flex: 1, minWidth: 220 }} />
        <button className="accent" onClick={go} disabled={loading}>{loading ? <Spinner label="Agent planning" /> : "Make my plan"}</button>
      </div>
      {error && <div className="alert error">{error}</div>}
      {data && (
        <>
          <div className="card">
            <p style={{ marginTop: 0 }}>{data.message}</p>
            <p className="small muted">Covers {data.schedule.topics_covered} of {data.schedule.topics_total} topics.
              {data.schedule.skipped?.length > 0 && ` Low-priority topics left out for lack of time: ${data.schedule.skipped.slice(0, 6).join(", ")}${data.schedule.skipped.length > 6 ? "…" : ""}.`}</p>
            <button className="link small" onClick={() => setTrace(!trace)}>{trace ? "Hide" : "Show"} agent reasoning ({data.trace.length} steps)</button>
            {trace && <ol className="small">{data.trace.map((t: any, i: number) => (
              <li key={i}><code>{t.tool}({JSON.stringify(t.args || {})})</code> {t.thought && <span className="muted">— {t.thought}</span>}{t.error && <span className="badge bad">{t.error}</span>}</li>))}</ol>}
          </div>
          <div className="card">
            {data.schedule.days.map((d: any) => (
              <div className="day" key={d.day}>
                <h3>Day {d.day}</h3>
                {d.sessions.map((s: any, i: number) => (
                  <div key={i} className="row small" style={{ justifyContent: "space-between" }}>
                    <span>{s.topic} {s.unit && <span className="muted">· {s.unit}</span>}</span>
                    <span className="muted">{s.hours} h {s.priority !== undefined && <span className="badge">priority {s.priority}</span>}</span>
                  </div>))}
              </div>
            ))}
          </div>
        </>
      )}
    </NeedSubject>
  );
}

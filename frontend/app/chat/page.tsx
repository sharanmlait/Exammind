"use client";
import { useEffect, useRef, useState } from "react";
import { api, Source } from "@/lib/api";
import { Markdown } from "@/lib/md";
import { useSubject } from "@/components/SubjectContext";
import { NeedSubject } from "@/components/Shell";
import { Feedback, Sources, Spinner } from "@/components/ui";

type Msg = { role: "user" | "assistant"; content: string; sources?: Source[]; grounded?: boolean;
             language?: string; warnings?: string[]; timings_ms?: Record<string, number>; question?: string };

const EXAMPLES = ["What is thrashing and how is it prevented?", "Banker's algorithm kya hai?", "Compare paging and segmentation"];

export default function Chat() {
  const { current } = useSubject();
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [q, setQ] = useState("");
  const [busy, setBusy] = useState(false);
  const [hl, setHl] = useState<Record<number, string | null>>({});
  const end = useRef<HTMLDivElement>(null);
  useEffect(() => { setMsgs([]); }, [current?.id]);
  useEffect(() => { end.current?.scrollIntoView({ behavior: "smooth" }); }, [msgs, busy]);

  const ask = async (text = q) => {
    if (!current || !text.trim() || busy) return;
    const history = msgs.map(({ role, content }) => ({ role, content }));
    setMsgs((m) => [...m, { role: "user", content: text }]); setQ(""); setBusy(true);
    try {
      const r = await api(`/subjects/${current.id}/chat`, { body: { question: text, history } });
      setMsgs((m) => [...m, { role: "assistant", content: r.answer, question: text, ...r }]);
    } catch (e: any) {
      setMsgs((m) => [...m, { role: "assistant", content: `⚠️ ${e.message}`, warnings: [] }]);
    } finally { setBusy(false); }
  };

  return (
    <NeedSubject>
      <h1>Ask your notes</h1>
      <p className="sub">Answers come only from what you uploaded, with citations. If it isn't in your notes, ExamMind says so instead of guessing.</p>
      <div className="chat">
        {!msgs.length && (
          <div className="row">{EXAMPLES.map((e) => <button key={e} className="secondary" onClick={() => ask(e)}>{e}</button>)}</div>
        )}
        {msgs.map((m, i) => m.role === "user" ? (
          <div key={i} className="bubble user">{m.content}</div>
        ) : (
          <div key={i} className="bubble bot">
            <Markdown text={m.content} onCite={(id) => setHl((h) => ({ ...h, [i]: h[i] === id ? null : id }))} />
            {m.warnings?.map((w) => <div key={w} className="alert warn small" style={{ margin: "8px 0 0" }}>{w}</div>)}
            {m.sources && <Sources sources={m.sources} highlight={hl[i]} />}
            {m.sources && (
              <div className="row small muted" style={{ marginTop: 8, justifyContent: "space-between" }}>
                <span>
                  {m.grounded ? <span className="badge good">grounded</span> : <span className="badge bad">not found in notes</span>}{" "}
                  {m.language !== "english" && <span className="badge">{m.language}</span>}{" "}
                  {m.timings_ms && `retrieval ${m.timings_ms.retrieval} ms · generation ${m.timings_ms.generation} ms`}
                </span>
                <Feedback subjectId={current!.id} kind="chat" prompt={m.question || ""} response={m.content} />
              </div>
            )}
          </div>
        ))}
        {busy && <div className="bubble bot"><Spinner label="Searching your notes" /></div>}
        <div ref={end} />
      </div>
      <div className="composer row">
        <input style={{ flex: 1 }} value={q} placeholder="Ask anything from your notes… (English / Hindi / Hinglish)"
               onChange={(e) => setQ(e.target.value)} onKeyDown={(e) => e.key === "Enter" && ask()} />
        <button onClick={() => ask()} disabled={busy || !q.trim()}>Ask</button>
        {msgs.length > 0 && <button className="secondary" onClick={() => setMsgs([])}>New chat</button>}
      </div>
    </NeedSubject>
  );
}

"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useSubject } from "@/components/SubjectContext";
import { NeedSubject } from "@/components/Shell";
import { Spinner } from "@/components/ui";

type Doc = { id: number; filename: string; kind: string; year: number | null; pages: number; ocr_used: number; created_at: string };

export default function Library() {
  const { current, refresh } = useSubject();
  const [docs, setDocs] = useState<Doc[]>([]);
  const [stats, setStats] = useState<Record<string, number>>({});
  const [kind, setKind] = useState("notes");
  const [year, setYear] = useState("");
  const [files, setFiles] = useState<FileList | null>(null);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<{ type: string; text: string } | null>(null);

  const load = async () => {
    if (!current) return;
    const s = await api(`/subjects/${current.id}`);
    setDocs(s.documents); setStats(s.stats);
  };
  useEffect(() => { load().catch(() => {}); }, [current?.id]);

  const upload = async () => {
    if (!current || !files?.length) return;
    setBusy(true); setMsg(null);
    const done: string[] = [];
    try {
      for (const f of Array.from(files)) {
        const form = new FormData();
        form.append("file", f); form.append("kind", kind);
        if (year) form.append("year", year);
        const r = await api(`/subjects/${current.id}/documents`, { form });
        done.push(`${f.name}: ${r.chunks ? r.chunks + " chunks" : ""}${r.topics ? r.topics + " topics" : ""}${r.questions !== undefined ? r.questions + " questions" + (r.year ? ` (${r.year})` : "") : ""}${r.ocr_used ? " · OCR" : ""}`);
      }
      setMsg({ type: "ok", text: "Processed — " + done.join(" · ") });
      await load(); await refresh();
    } catch (e: any) { setMsg({ type: "error", text: e.message }); }
    finally { setBusy(false); }
  };

  const remove = async (id: number) => {
    if (!current) return;
    await api(`/subjects/${current.id}/documents/${id}`, { method: "DELETE" });
    await load(); await refresh();
  };

  return (
    <NeedSubject>
      <h1>Library</h1>
      <p className="sub">Notes are chunked, embedded and indexed for search. Syllabi become the topic list. Past papers are split into
        questions and auto-tagged by topic. Scanned PDFs and photos go through OCR.</p>
      <div className="grid" style={{ marginBottom: 18 }}>
        {[["chunks", "Indexed chunks"], ["topics", "Syllabus topics"], ["questions", "Past questions"], ["attempts", "Graded attempts"]].map(([k, l]) => (
          <div className="card" key={k} style={{ margin: 0 }}><div className="stat">{stats[k] ?? 0}</div><div className="muted small">{l}</div></div>
        ))}
      </div>
      <div className="card stack">
        <h2>Upload</h2>
        <div className="row">
          <select value={kind} onChange={(e) => setKind(e.target.value)}>
            <option value="notes">Notes / textbook chapter</option>
            <option value="syllabus">Syllabus</option>
            <option value="pyq">Previous year paper</option>
          </select>
          {kind === "pyq" && <input placeholder="Year (auto-detected)" value={year} onChange={(e) => setYear(e.target.value)} style={{ width: 170 }} />}
          <input type="file" multiple accept=".pdf,.txt,.md,.png,.jpg,.jpeg" onChange={(e) => setFiles(e.target.files)} />
          <button onClick={upload} disabled={busy || !files?.length}>{busy ? <Spinner label="Processing" /> : "Upload"}</button>
        </div>
        <p className="muted small">Tip: upload the syllabus first, so past questions can be tagged with its topics.</p>
        {msg && <div className={`alert ${msg.type}`}>{msg.text}</div>}
      </div>
      <div className="card">
        <h2>Documents</h2>
        {!docs.length ? <p className="muted">Nothing uploaded yet.</p> : (
          <table>
            <thead><tr><th>File</th><th>Type</th><th>Year</th><th>Pages</th><th></th></tr></thead>
            <tbody>{docs.map((d) => (
              <tr key={d.id}>
                <td>{d.filename} {d.ocr_used ? <span className="badge">OCR</span> : null}</td>
                <td><span className="badge">{d.kind}</span></td><td>{d.year ?? "—"}</td><td>{d.pages}</td>
                <td><button className="link" onClick={() => remove(d.id)}>delete</button></td>
              </tr>))}
            </tbody>
          </table>
        )}
      </div>
    </NeedSubject>
  );
}

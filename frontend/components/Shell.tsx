"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useSubject } from "./SubjectContext";

const NAV = [
  { href: "/", label: "Home", icon: "◎" },
  { href: "/library", label: "Library", icon: "▤" },
  { href: "/chat", label: "Ask your notes", icon: "✦" },
  { href: "/answer", label: "Exam answers", icon: "✎" },
  { href: "/topics", label: "Hot topics", icon: "▲" },
  { href: "/practice", label: "Practice", icon: "◇" },
  { href: "/grade", label: "Grade my answer", icon: "✓" },
  { href: "/plan", label: "Study plan", icon: "▦" },
];

export function Shell({ children }: { children: React.ReactNode }) {
  const path = usePathname();
  const { subjects, current, select, error } = useSubject();
  return (
    <div className="shell">
      <aside className="sidebar">
        <div className="brand">Exam<span>Mind</span></div>
        <label className="label">Subject</label>
        <select value={current?.id ?? ""} onChange={(e) => select(Number(e.target.value))} disabled={!subjects.length}>
          {!subjects.length && <option value="">No subjects yet</option>}
          {subjects.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
        </select>
        <nav>
          {NAV.map((n) => (
            <Link key={n.href} href={n.href} className={path === n.href ? "active" : ""}>
              <span className="icon">{n.icon}</span>{n.label}
            </Link>
          ))}
        </nav>
        <p className="foot">RAG · fine-tuned LLM · NLP · ML</p>
      </aside>
      <main className="main">
        {error && <div className="alert error">{error}</div>}
        {children}
      </main>
    </div>
  );
}

export function NeedSubject({ children }: { children: React.ReactNode }) {
  const { current } = useSubject();
  if (!current) return <div className="empty">Create or select a subject on the <Link href="/">Home</Link> page first.</div>;
  return <>{children}</>;
}

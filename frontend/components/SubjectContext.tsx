"use client";
import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { api } from "@/lib/api";

export type Subject = { id: number; name: string; documents: number; questions: number; topics: number };

type Ctx = {
  subjects: Subject[];
  current: Subject | null;
  select: (id: number) => void;
  refresh: () => Promise<void>;
  error: string | null;
};

const SubjectCtx = createContext<Ctx>({ subjects: [], current: null, select: () => {}, refresh: async () => {}, error: null });

const KEY = "exammind.subject";
const load = () => { try { return Number(localStorage.getItem(KEY)) || null; } catch { return null; } };
const save = (id: number) => { try { localStorage.setItem(KEY, String(id)); } catch { /* storage unavailable */ } };

export function SubjectProvider({ children }: { children: React.ReactNode }) {
  const [subjects, setSubjects] = useState<Subject[]>([]);
  const [currentId, setCurrentId] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const s = await api<Subject[]>("/subjects");
      setSubjects(s);
      setError(null);
      setCurrentId((cur) => {
        const saved = cur ?? load();
        return s.find((x) => x.id === saved) ? saved : s[0]?.id ?? null;
      });
    } catch (e: any) {
      setError(e.message);
    }
  }, []);

  useEffect(() => { refresh(); }, [refresh]);

  const select = (id: number) => { setCurrentId(id); save(id); };
  const current = subjects.find((s) => s.id === currentId) ?? null;
  return <SubjectCtx.Provider value={{ subjects, current, select, refresh, error }}>{children}</SubjectCtx.Provider>;
}

export const useSubject = () => useContext(SubjectCtx);

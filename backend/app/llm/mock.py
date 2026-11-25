"""Deterministic offline provider. Lets the whole app, tests and eval run with no API key.
It builds answers from the retrieved context, so RAG behaviour (citations, grounding) is real;
only the "intelligence" of the wording is faked."""
import json
import re

from .base import LLMProvider

SRC_RE = re.compile(r"\[S(\d+)\][^\n]*\n(.*?)(?=\n\[S\d+\]|\n---|\Z)", re.S)


def _sentences(text: str) -> list[str]:
    text = re.sub(r"^#+ .*$", "", text, flags=re.M)  # drop markdown headings
    parts = re.split(r"(?<=[.!?])\s+", re.sub(r"\s+", " ", text).strip())
    return [p for p in parts if len(p.split()) >= 5]


def _sources(text: str) -> list[tuple[str, str]]:
    return [(m.group(1), m.group(2).strip()) for m in SRC_RE.finditer(text)]


class MockProvider(LLMProvider):
    name = "mock"
    model = "mock-1"

    def _complete(self, messages, json_mode, temperature, task):
        user = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")
        allt = "\n".join(m["content"] for m in messages)
        handler = getattr(self, f"_t_{task}", None)
        if handler:
            return handler(user, allt, messages)
        return json.dumps({"result": "ok"}) if json_mode else "OK."

    # --- tasks ---------------------------------------------------------------
    def _t_rag_answer(self, user, allt, messages):
        srcs = _sources(user)
        if not srcs:
            return "I couldn't find this in your notes."
        lines = []
        for sid, txt in srcs[:3]:
            sents = _sentences(txt)
            if sents:
                lines.append(f"{sents[0]} [S{sid}]")
        return " ".join(lines) or "I couldn't find this in your notes."

    def _t_exam_answer(self, user, allt, messages):
        srcs = _sources(user)
        marks = int((re.search(r"(\d+)\s*marks", user) or [0, 5])[1])
        sents = [(sid, s) for sid, t in srcs for s in _sentences(t)]
        n = {2: 2, 5: 6, 10: 11}.get(marks, max(3, marks))
        q = (re.search(r"Question:\s*(.+)", user) or [None, "the topic"])[1].strip()
        topic = q.rstrip("?.").lower()
        if not sents:
            return f"**Introduction**\nThis answer covers {topic}.\n\n**Conclusion**\nNo supporting notes were found."
        intro = f"{sents[0][1]} [S{sents[0][0]}]"
        if marks <= 2:
            return f"{intro} " + " ".join(f"{s} [S{i}]" for i, s in sents[1:n])
        pts = "\n".join(f"{k}. {s} [S{i}]" for k, (i, s) in enumerate(sents[1:n], 1))
        return (f"**Introduction**\n{intro}\n\n**Key points**\n{pts}\n\n"
                f"**Diagram hint**\nDraw a labelled block diagram of {topic}.\n\n"
                f"**Conclusion**\nThus, {topic} is an important concept in this unit.")

    def _t_summarize(self, user, allt, messages):
        sents = [s for _, t in _sources(user) for s in _sentences(t)] or _sentences(user)
        return "\n".join(f"- {s}" for s in sents[:6])

    def _t_mcq(self, user, allt, messages):
        n = int((re.search(r"Create (\d+)", user) or [0, 3])[1])
        topic = (re.search(r"Topic:\s*(.+)", user) or [None, "General"])[1].strip()
        sents = [s for _, t in _sources(user) for s in _sentences(t)]
        qs = []
        for i, s in enumerate(sents[:n]):
            words = [w.strip(",.;:()") for w in s.split() if len(w.strip(",.;:()")) > 5]
            key = words[0] if words else "concept"
            stem = s.replace(key, "_____", 1)
            distract = [w for w in {x for x in re.findall(r"[A-Za-z]{6,}", user)} if w.lower() != key.lower()][:3]
            while len(distract) < 3:
                distract.append(f"None of these {len(distract)}")
            opts = [key] + distract
            rot = i % 4
            opts = opts[rot:] + opts[:rot]
            qs.append({"question": f"Fill in the blank: {stem}", "options": opts,
                       "answer_index": opts.index(key), "explanation": s, "topic": topic})
        return json.dumps({"questions": qs})

    def _t_short_questions(self, user, allt, messages):
        n = int((re.search(r"Create (\d+)", user) or [0, 3])[1])
        topic = (re.search(r"Topic:\s*(.+)", user) or [None, "General"])[1].strip()
        sents = [s for _, t in _sources(user) for s in _sentences(t)]
        return json.dumps({"questions": [
            {"question": f"Explain: {' '.join(s.split()[:8])}...", "marks": 5,
             "model_answer": s, "topic": topic} for s in sents[:n]]})

    def _t_grade(self, user, allt, messages):
        ref = (re.search(r"REFERENCE:\s*(.*?)\nSTUDENT ANSWER:", user, re.S) or [None, ""])[1]
        ans = (re.search(r"STUDENT ANSWER:\s*(.*?)\nMAX MARKS:", user, re.S) or [None, ""])[1]
        mx = float((re.search(r"MAX MARKS:\s*(\d+)", user) or [0, 10])[1])
        rw = {w.lower() for w in re.findall(r"[A-Za-z]{5,}", ref)}
        aw = {w.lower() for w in re.findall(r"[A-Za-z]{5,}", ans)}
        cov = len(rw & aw) / max(1, len(rw))
        missing = sorted(rw - aw)[:5]
        return json.dumps({"score": round(min(1.0, cov * 1.3) * mx, 1), "max_score": mx,
                           "strengths": sorted(rw & aw)[:5], "missing_points": missing,
                           "feedback": "Good attempt." if cov > 0.5 else "Add more key points from your notes."})

    def _t_judge(self, user, allt, messages):
        ctx = (re.search(r"CONTEXT:\s*(.*?)\nANSWER:", user, re.S) or [None, ""])[1]
        ans = (re.search(r"ANSWER:\s*(.*)", user, re.S) or [None, ""])[1]
        aw = {w.lower() for w in re.findall(r"[A-Za-z]{5,}", ans)}
        cw = {w.lower() for w in re.findall(r"[A-Za-z]{5,}", ctx)}
        score = len(aw & cw) / max(1, len(aw))
        return json.dumps({"faithfulness": round(score, 2), "unsupported_claims": []})

    def _t_agent(self, user, allt, messages):
        done = set(re.findall(r'TOOL_RESULT \((\w+)\)', allt))
        days = int((re.search(r"(\d+)\s*days", allt) or [0, 7])[1])
        hours = float((re.search(r"([\d.]+)\s*hours", allt) or [0, 3])[1])
        for tool, args in (("list_topics", {}), ("hot_topics", {"limit": 8}), ("weak_topics", {}),
                           ("build_schedule", {"days": days, "hours_per_day": hours})):
            if tool not in done:
                return json.dumps({"thought": f"I need {tool} next.", "tool": tool, "args": args})
        return json.dumps({"thought": "I have everything.", "final":
                           f"Here is your {days}-day plan. High-probability and weak topics come first, "
                           "with revision and a mock test at the end."})

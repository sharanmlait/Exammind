"""Exam-oriented generation: exam-style answers, chapter summaries, MCQs and short questions."""
import random

from ..llm import LLMError, get_answer_llm, get_llm
from ..rag.pipeline import best_score, format_sources, relevance_threshold, retrieve

# Indian university answer length norms, roughly
MARKS_GUIDE = {2: "40-60 words, 2-3 crisp points", 5: "150-250 words, 5-6 points",
               10: "400-600 words, intro + 8-10 points + diagram + conclusion"}

# This exact system prompt is also used to build the fine-tuning dataset (training/llm/build_sft_dataset.py),
# so the fine-tuned model sees the same instruction format at train and inference time.
EXAM_SYSTEM = """You write model answers for Indian university (B.Tech) theory exams.
Structure: **Introduction** (1-2 lines, a definition) -> **Key points** (numbered, each point bold title + 1-2 lines)
-> **Diagram hint** (what to draw, if any) -> **Conclusion** (1 line).
Match the length to the marks. Use only the provided notes; cite like [S1]. Simple language, exam keywords."""


def marks_guide(marks: int) -> str:
    key = min(MARKS_GUIDE, key=lambda m: abs(m - marks))
    return MARKS_GUIDE[key]


def exam_answer(subject_id: int, question: str, marks: int = 5) -> dict:
    hits = retrieve(subject_id, question, k=6)
    context, sources, warns = format_sources(hits)
    if best_score(hits) < relevance_threshold(hits):
        warns.append("Weak match with your notes — answer may be generic.")
    llm = get_answer_llm()
    prompt = (f"Notes:\n{context}\n---\nQuestion: {question}\nMarks: {marks} marks "
              f"(target: {marks_guide(marks)})")
    res = llm.complete([{"role": "system", "content": EXAM_SYSTEM}, {"role": "user", "content": prompt}],
                       temperature=0.4, task="exam_answer")
    return {"question": question, "marks": marks, "answer": res.text, "sources": sources,
            "model": f"{res.provider}:{res.model}", "latency_ms": res.latency_ms, "warnings": warns}


def summarize(subject_id: int, topic: str) -> dict:
    hits = retrieve(subject_id, topic, k=8)
    context, sources, _ = format_sources(hits)
    res = get_llm().complete([
        {"role": "system", "content": "Summarise university notes for last-minute revision. "
                                      "6-10 bullet points, each one fact with a citation [S#]. Bold the key terms."},
        {"role": "user", "content": f"Sources:\n{context}\n---\nTopic: {topic}"}], task="summarize")
    return {"topic": topic, "summary": res.text, "sources": sources}


def _validate_mcqs(raw) -> list[dict]:
    items = raw.get("questions", raw) if isinstance(raw, dict) else raw
    good = []
    for q in items if isinstance(items, list) else []:
        opts = q.get("options")
        ai = q.get("answer_index")
        if (isinstance(q.get("question"), str) and isinstance(opts, list) and len(opts) == 4
                and isinstance(ai, int) and 0 <= ai < 4 and len({str(o).lower() for o in opts}) == 4):
            good.append({"question": q["question"], "options": [str(o) for o in opts], "answer_index": ai,
                         "explanation": q.get("explanation", ""), "topic": q.get("topic")})
    return good


def practice(subject_id: int, topic: str, n: int = 5, kind: str = "mcq") -> dict:
    hits = retrieve(subject_id, topic, k=8)
    head, tail = hits[:3], hits[3:]
    random.Random(topic).shuffle(tail)  # keep the most relevant chunks first, vary the rest
    hits = head + tail
    context, sources, _ = format_sources(hits)
    llm = get_llm()
    if kind == "mcq":
        instr = ("Create {n} multiple-choice questions from the sources. JSON: "
                 '{{"questions":[{{"question":str,"options":[4 strings],"answer_index":0-3,'
                 '"explanation":str citing [S#],"topic":str}}]}}. One clearly correct option, '
                 "plausible distractors, no 'all of the above'.")
    else:
        instr = ("Create {n} short-answer exam questions from the sources. JSON: "
                 '{{"questions":[{{"question":str,"marks":2|5,"model_answer":str,"topic":str}}]}}')
    user = f"Sources:\n{context}\n---\nTopic: {topic}\nCreate {n} questions.\n" + instr.format(n=n)
    try:
        raw = llm.complete_json([{"role": "system", "content": "You are an exam paper setter. Output JSON only."},
                                 {"role": "user", "content": user}], task=kind if kind == "mcq" else "short_questions")
    except LLMError as e:
        return {"topic": topic, "kind": kind, "questions": [], "error": str(e), "sources": sources}
    qs = _validate_mcqs(raw) if kind == "mcq" else [
        q for q in (raw.get("questions", []) if isinstance(raw, dict) else []) if isinstance(q, dict) and q.get("question")]
    return {"topic": topic, "kind": kind, "questions": qs[:n], "sources": sources}

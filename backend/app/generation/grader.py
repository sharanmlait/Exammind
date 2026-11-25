"""Answer grading = three signals blended into one score:
1. Semantic similarity between the student's answer and a reference answer (embeddings).
2. Key-point coverage: how many important terms from the reference the student used.
3. LLM-as-judge with a rubric (strengths, missing points, feedback).
Blending makes the grade harder to game (e.g. keyword stuffing fools #2 but not #3)."""
import numpy as np

from .. import db
from ..llm import LLMError, get_llm
from ..rag.embeddings import get_embedder
from ..rag.pipeline import format_sources, retrieve
from ..rag.store import tokenize
from .exam import exam_answer

WEIGHTS = {"llm": 0.6, "semantic": 0.25, "coverage": 0.15}


def _coverage(reference: str, answer: str, top: int = 12) -> tuple[float, list[str]]:
    """Share of the reference's most frequent content words that the student also used."""
    from collections import Counter
    counts = Counter(t for t in tokenize(reference) if len(t) > 3 and not t.isdigit())
    ref_terms = [t for t, _ in counts.most_common(top)]
    ans = set(tokenize(answer))
    hit = [t for t in ref_terms if t in ans]
    return (len(hit) / len(ref_terms) if ref_terms else 0.0), [t for t in ref_terms if t not in ans][:8]


def grade(subject_id: int, question: str, answer: str, max_marks: int = 10,
          reference: str | None = None, topic: str | None = None) -> dict:
    if not answer.strip():
        return {"score": 0, "max_score": max_marks, "feedback": "No answer written."}
    if reference is None:
        reference = exam_answer(subject_id, question, marks=max_marks)["answer"]

    emb = get_embedder()
    sem = float(np.clip(emb.embed_query(answer) @ emb.embed_query(reference), 0, 1))
    cov, missing_terms = _coverage(reference, answer)

    context, _, _ = format_sources(retrieve(subject_id, question, k=4))
    prompt = (f"QUESTION: {question}\nNOTES:\n{context}\nREFERENCE:\n{reference}\nSTUDENT ANSWER:\n{answer}\n"
              f"MAX MARKS: {max_marks}\n\nGrade like a fair university examiner. Give partial credit for "
              "correct points even if worded differently. Penalise wrong facts. JSON: "
              '{"score":number,"max_score":number,"strengths":[str],"missing_points":[str],"feedback":str}')
    llm_score, judge = None, {}
    try:
        judge = get_llm().complete_json([{"role": "system", "content": "You are a strict but fair examiner. JSON only."},
                                         {"role": "user", "content": prompt}], task="grade")
        llm_score = float(judge.get("score", 0)) / max_marks
    except (LLMError, TypeError, ValueError):
        pass

    if llm_score is None:
        frac = (sem * 0.6 + cov * 0.4)
    else:
        frac = WEIGHTS["llm"] * llm_score + WEIGHTS["semantic"] * sem + WEIGHTS["coverage"] * cov
    score = round(min(1.0, max(0.0, frac)) * max_marks * 2) / 2  # round to nearest 0.5 like examiners do

    result = {"score": score, "max_score": max_marks,
              "breakdown": {"llm_judge": None if llm_score is None else round(llm_score, 3),
                            "semantic_similarity": round(sem, 3), "keyword_coverage": round(cov, 3)},
              "strengths": judge.get("strengths", []), "missing_points": judge.get("missing_points") or missing_terms,
              "feedback": judge.get("feedback", "Compare your answer with the reference below."),
              "reference_answer": reference}
    db.execute("INSERT INTO attempts(subject_id, question, topic, score, max_score, feedback, created_at) "
               "VALUES (?,?,?,?,?,?,?)", (subject_id, question, topic, score, max_marks, result["feedback"], db.now()))
    return result

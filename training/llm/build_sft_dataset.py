"""Build the supervised fine-tuning (SFT) dataset for the exam-answer model.

Idea (knowledge distillation): a big "teacher" LLM (Groq Llama-70B / Gemini) writes high-quality,
exam-formatted answers grounded in the notes. We fine-tune a small "student" model (3B) on them,
so it learns the FORMAT and STYLE cheaply and runs locally for free.

Each row uses the exact same system prompt + user prompt format as the app (app/generation/exam.py),
so train-time and inference-time inputs match.

Run from backend/ (uses your .env for the teacher LLM):
    python ../training/llm/build_sft_dataset.py --per-topic 6
Offline smoke test:
    LLM_PROVIDER=mock EMBEDDING_PROVIDER=hash python ../training/llm/build_sft_dataset.py --per-topic 2"""
import argparse
import csv
import json
import random
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
BACKEND = HERE.parents[1] / "backend"
sys.path.insert(0, str(BACKEND))

from app import db  # noqa: E402
from app.generation.exam import EXAM_SYSTEM, marks_guide  # noqa: E402
from app.llm import LLMError, get_llm  # noqa: E402
from app.rag.pipeline import format_sources, retrieve  # noqa: E402
from scripts.seed_demo import seed  # noqa: E402

SAMPLE = HERE.parents[1] / "data" / "sample"
QUESTION_STYLES = [
    "Explain {t} with a suitable example.", "What is {t}? Discuss its advantages and disadvantages.",
    "Write a short note on {t}.", "Describe {t} in detail with a neat diagram.",
    "Define {t}.", "Compare {t} with a related concept you have studied.",
]
WORDS = {2: (25, 110), 5: (90, 350), 10: (250, 800)}


def build_user_prompt(context: str, question: str, marks: int) -> str:
    # MUST match app/generation/exam.py::exam_answer
    return f"Notes:\n{context}\n---\nQuestion: {question}\nMarks: {marks} marks (target: {marks_guide(marks)})"


def quality_ok(answer: str, marks: int) -> tuple[bool, str]:
    n = len(answer.split())
    lo, hi = WORDS[min(WORDS, key=lambda m: abs(m - marks))]
    if not (lo <= n <= hi):
        return False, f"length {n} outside {lo}-{hi}"
    if marks >= 5 and not all(s in answer for s in ("Introduction", "Key points", "Conclusion")):
        return False, "missing section"
    if not re.search(r"\[S\d+\]", answer):
        return False, "no citations"
    return True, "ok"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--subject-id", type=int, help="existing subject; default = load the demo OS subject")
    ap.add_argument("--questions", type=Path, default=SAMPLE / "pyq_labels.csv", help="real PYQs (text,label,marks)")
    ap.add_argument("--per-topic", type=int, default=6, help="synthetic questions per topic")
    ap.add_argument("--val-ratio", type=float, default=0.1)
    ap.add_argument("--out", type=Path, default=HERE / "data")
    args = ap.parse_args()

    db.init_db()
    sid = args.subject_id or seed()["subject_id"]
    rng = random.Random(42)
    jobs = []
    if args.questions.exists():
        with open(args.questions, encoding="utf-8") as f:
            for r in csv.DictReader(f):
                jobs.append((r["text"], int(r.get("marks") or 5), r.get("label")))
    for t in db.rows("SELECT name FROM topics WHERE subject_id=?", (sid,)):
        for style in rng.sample(QUESTION_STYLES, min(args.per_topic, len(QUESTION_STYLES))):
            jobs.append((style.format(t=t["name"]), rng.choice([2, 5, 5, 10]), t["name"]))
    jobs = list({(q.lower(), m): (q, m, t) for q, m, t in jobs}.values())  # dedupe
    print(f"{len(jobs)} prompts; teacher = {get_llm().name}:{get_llm().model}")

    teacher = get_llm()
    rows, rejected = [], {}
    for i, (q, marks, topic) in enumerate(jobs, 1):
        context, _, _ = format_sources(retrieve(sid, q, k=5))
        user = build_user_prompt(context, q, marks)
        msgs = [{"role": "system", "content": EXAM_SYSTEM}, {"role": "user", "content": user}]
        try:
            ans = teacher.complete(msgs, temperature=0.5, task="exam_answer").text.strip()
        except LLMError as e:
            print(f"  [{i}] teacher error: {e}")
            continue
        ok, why = quality_ok(ans, marks)
        if not ok:
            rejected[why.split()[0]] = rejected.get(why.split()[0], 0) + 1
            continue
        rows.append({"messages": msgs + [{"role": "assistant", "content": ans}],
                     "meta": {"question": q, "marks": marks, "topic": topic}})
        if i % 25 == 0:
            print(f"  {i}/{len(jobs)} done, kept {len(rows)}")

    rng.shuffle(rows)
    n_val = max(1, int(len(rows) * args.val_ratio)) if rows else 0
    args.out.mkdir(parents=True, exist_ok=True)
    for name, part in (("val", rows[:n_val]), ("train", rows[n_val:])):
        with open(args.out / f"{name}.jsonl", "w", encoding="utf-8") as f:
            for r in part:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"kept {len(rows)} / {len(jobs)} (rejected: {rejected}) -> {args.out}/train.jsonl, val.jsonl")


if __name__ == "__main__":
    main()

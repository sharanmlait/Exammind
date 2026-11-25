"""Benchmark: base model vs your fine-tuned model (vs the teacher) on the held-out val set.

Metrics per answer, averaged:
  structure      has Introduction / Key points / Conclusion (for 5+ marks)
  length_fit     word count inside the target range for the marks
  citations      cites at least one [S#]
  rouge_l        overlap with the teacher's reference answer (LCS-based ROUGE-L F1)
  judge          teacher LLM scores the answer 1-10 against the notes (needs a real LLM)
  latency_ms     generation time

Run from backend/, e.g. after `ollama pull qwen2.5:3b` and `ollama create exammind -f Modelfile`:
    python ../training/llm/evaluate_finetune.py --models ollama:qwen2.5:3b ollama:exammind groq
Offline smoke test:
    LLM_PROVIDER=mock python ../training/llm/evaluate_finetune.py --models mock --no-judge"""
import argparse
import json
import re
import statistics
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "backend"))

from app.config import get_settings  # noqa: E402
from app.llm import LLMError, build_provider, get_llm  # noqa: E402
from app.llm.providers import OllamaProvider  # noqa: E402

from build_sft_dataset import WORDS  # noqa: E402


def rouge_l(a: str, b: str) -> float:
    x, y = a.lower().split(), b.lower().split()
    if not x or not y:
        return 0.0
    prev = [0] * (len(y) + 1)
    for xi in x:
        cur = [0]
        for j, yj in enumerate(y, 1):
            cur.append(prev[j - 1] + 1 if xi == yj else max(prev[j], cur[-1]))
        prev = cur
    lcs = prev[-1]
    p, r = lcs / len(x), lcs / len(y)
    return 0.0 if lcs == 0 else 2 * p * r / (p + r)


def make(spec: str):
    """'groq' | 'gemini' | 'mock' | 'ollama:<model-name>'"""
    if spec.startswith("ollama:"):
        return OllamaProvider(get_settings().ollama_url, spec.split(":", 1)[1])
    return build_provider(spec)


def judge(notes_prompt: str, answer: str) -> float | None:
    try:
        r = get_llm().complete_json([
            {"role": "system", "content": "You are a university examiner. JSON only."},
            {"role": "user", "content": f"{notes_prompt}\n\nCANDIDATE ANSWER:\n{answer}\n\nScore 1-10 for correctness "
                                        "(vs the notes), exam structure, and appropriate length for the marks. "
                                        '{"score": int, "reason": str}'}], task="judge")
        return float(r["score"])
    except (LLMError, KeyError, TypeError, ValueError):
        return None


def evaluate(spec, rows, use_judge):
    llm = make(spec)
    m = {k: [] for k in ("structure", "length_fit", "citations", "rouge_l", "judge", "latency_ms")}
    for r in rows:
        msgs, ref = r["messages"][:2], r["messages"][2]["content"]
        marks = r["meta"]["marks"]
        t0 = time.perf_counter()
        try:
            ans = llm.complete(msgs, temperature=0.4, task="exam_answer").text
        except LLMError as e:
            print(f"  {spec}: {e}")
            continue
        m["latency_ms"].append((time.perf_counter() - t0) * 1000)
        lo, hi = WORDS[min(WORDS, key=lambda k: abs(k - marks))]
        m["length_fit"].append(1.0 if lo <= len(ans.split()) <= hi else 0.0)
        m["structure"].append(1.0 if marks < 5 or all(s in ans for s in ("Introduction", "Key points", "Conclusion"))
                              else 0.0)
        m["citations"].append(1.0 if re.search(r"\[S\d+\]", ans) else 0.0)
        m["rouge_l"].append(rouge_l(ans, ref))
        if use_judge:
            j = judge(msgs[1]["content"], ans)
            if j is not None:
                m["judge"].append(j)
    return {"model": spec, "n": len(m["latency_ms"]),
            **{k: (round(statistics.mean(v), 3) if v else None) for k, v in m.items()}}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--val", type=Path, default=HERE / "data" / "val.jsonl")
    ap.add_argument("--models", nargs="+", required=True)
    ap.add_argument("--limit", type=int, default=40)
    ap.add_argument("--no-judge", action="store_true")
    args = ap.parse_args()
    rows = [json.loads(l) for l in open(args.val, encoding="utf-8") if l.strip()][: args.limit]
    results = [evaluate(s, rows, not args.no_judge) for s in args.models]
    cols = ["model", "n", "structure", "length_fit", "citations", "rouge_l", "judge", "latency_ms"]
    md = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    md += ["| " + " | ".join("—" if r[c] is None else str(r[c]) for c in cols) + " |" for r in results]
    print("\n".join(md))
    (HERE / "finetune_eval.md").write_text("\n".join(md) + "\n")


if __name__ == "__main__":
    main()

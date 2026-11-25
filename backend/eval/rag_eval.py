"""RAG evaluation / benchmarking.

Compares retrieval configurations on a labelled question set and reports:
  Retrieval:  Hit@1, Recall@5, MRR           (is the right note section retrieved, and how high?)
  Generation: keyword coverage, faithfulness (does the answer contain the key points, and stick to sources?)
  Safety:     off-topic refusal rate          (does it say "not in notes" instead of hallucinating?)
  Cost:       mean retrieval / generation latency

Usage (from backend/):
    python -m eval.rag_eval                         # uses your .env (LLM + embeddings)
    LLM_PROVIDER=mock EMBEDDING_PROVIDER=hash python -m eval.rag_eval   # fully offline
Results are written to eval/results/<timestamp>.md and .json."""
import argparse
import json
import statistics
import time
from datetime import datetime
from pathlib import Path

from app import db
from app.config import get_settings
from app.llm import LLMError, get_llm
from app.rag.embeddings import get_embedder
from app.rag.pipeline import answer_question, retrieve
from app.rag.rerank import get_reranker
from scripts.seed_demo import seed

HERE = Path(__file__).parent
CONFIGS = [
    {"name": "BM25 only", "mode": "bm25", "rerank": False},
    {"name": "Dense only", "mode": "dense", "rerank": False},
    {"name": "Hybrid", "mode": "hybrid", "rerank": False},
    {"name": "Hybrid + rerank", "mode": "hybrid", "rerank": True},
]


def is_gold(text: str, gold: str) -> bool:
    return f"### {gold}".lower() in text.lower()


def faithfulness(answer: str, context: str) -> float | None:
    """LLM-as-judge: what fraction of the answer's claims are supported by the context?"""
    try:
        r = get_llm().complete_json([
            {"role": "system", "content": "You check whether an answer is supported by its context. JSON only."},
            {"role": "user", "content": f"CONTEXT:\n{context}\nANSWER:\n{answer}\n\nReturn "
                                        '{"faithfulness": 0..1 (share of claims supported), "unsupported_claims": [str]}'}],
            task="judge")
        return float(r.get("faithfulness"))
    except (LLMError, TypeError, ValueError):
        return None


def run(eval_file: Path, generate: bool = True) -> dict:
    data = json.loads(eval_file.read_text())
    sid = seed()["subject_id"]
    results = []
    for cfg in CONFIGS:
        hit1, rec5, rr, cov, faith, lat_r, lat_g = [], [], [], [], [], [], []
        for item in data["questions"]:
            t0 = time.perf_counter()
            hits = retrieve(sid, item["question"], k=5, mode=cfg["mode"], use_reranker=cfg["rerank"])
            lat_r.append((time.perf_counter() - t0) * 1000)
            ranks = [i for i, h in enumerate(hits, 1) if is_gold(h.text, item["gold_section"])]
            hit1.append(1.0 if ranks and ranks[0] == 1 else 0.0)
            rec5.append(1.0 if ranks else 0.0)
            rr.append(1.0 / ranks[0] if ranks else 0.0)
            if generate:
                res = answer_question(sid, item["question"], mode=cfg["mode"], use_reranker=cfg["rerank"])
                lat_g.append(res.timings_ms.get("generation", 0))
                low = res.answer.lower()
                kws = item["expected_keywords"]
                cov.append(sum(k.lower() in low for k in kws) / len(kws))
                if res.grounded:
                    f = faithfulness(res.answer, "\n".join(s["text"] for s in res.sources))
                    if f is not None:
                        faith.append(f)
        refusals = []
        if generate:
            for q in data["off_topic"]:
                res = answer_question(sid, q, mode=cfg["mode"], use_reranker=cfg["rerank"])
                refusals.append(0.0 if res.grounded else 1.0)
        mean = lambda xs: round(statistics.mean(xs), 3) if xs else None  # noqa: E731
        results.append({"config": cfg["name"], "hit@1": mean(hit1), "recall@5": mean(rec5), "mrr": mean(rr),
                        "keyword_coverage": mean(cov), "faithfulness": mean(faith),
                        "off_topic_refusal": mean(refusals),
                        "retrieval_ms": round(statistics.mean(lat_r), 1),
                        "generation_ms": round(statistics.mean(lat_g), 1) if lat_g else None})
    s = get_settings()
    meta = {"date": datetime.now().isoformat(timespec="seconds"), "llm": f"{get_llm().name}:{get_llm().model}",
            "embeddings": get_embedder().name, "reranker": get_reranker().name,
            "n_questions": len(data["questions"]), "n_off_topic": len(data["off_topic"]),
            "chunk_size": s.chunk_size, "hybrid_alpha": s.hybrid_alpha}
    return {"meta": meta, "results": results}


def to_markdown(report: dict) -> str:
    m = report["meta"]
    cols = ["config", "hit@1", "recall@5", "mrr", "keyword_coverage", "faithfulness",
            "off_topic_refusal", "retrieval_ms", "generation_ms"]
    lines = [f"# RAG evaluation — {m['date']}", "",
             f"LLM `{m['llm']}` · embeddings `{m['embeddings']}` · reranker `{m['reranker']}` · "
             f"{m['n_questions']} questions + {m['n_off_topic']} off-topic · chunk {m['chunk_size']} · alpha {m['hybrid_alpha']}",
             "", "| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    for r in report["results"]:
        lines.append("| " + " | ".join("—" if r[c] is None else str(r[c]) for c in cols) + " |")
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--eval-file", default=HERE / "eval_set_os.json", type=Path)
    ap.add_argument("--retrieval-only", action="store_true", help="skip LLM calls (fast, free)")
    args = ap.parse_args()
    db.init_db()
    report = run(args.eval_file, generate=not args.retrieval_only)
    out = HERE / "results"
    out.mkdir(exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    (out / f"{stamp}.json").write_text(json.dumps(report, indent=2))
    md = to_markdown(report)
    (out / f"{stamp}.md").write_text(md)
    print(md)

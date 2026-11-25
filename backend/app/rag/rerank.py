"""Second-stage re-ranking. A cross-encoder reads (query, chunk) together, which is far more
accurate than comparing two separate embeddings, but slower — so we only re-rank the top ~20."""
from functools import lru_cache

from ..config import get_settings
from .store import Hit, tokenize


class LexicalReranker:
    """Fallback: rewards chunks that cover more of the query's terms, and covers them close together."""
    name = "lexical"
    threshold = 0.3   # its scores run higher than a cross-encoder's, so it needs its own cut-off

    def score(self, query: str, hits: list[Hit]) -> list[float]:
        q = set(tokenize(query))
        out = []
        for h in hits:
            toks = tokenize(h.text)
            cover = len(q & set(toks)) / max(1, len(q))
            out.append(0.5 * cover + 0.5 * h.score)
        return out


class CrossEncoderReranker:
    def __init__(self, model: str):
        from sentence_transformers import CrossEncoder
        self.model = CrossEncoder(model)
        self.name = model

    def score(self, query, hits):
        import numpy as np
        raw = self.model.predict([(query, h.text) for h in hits])
        return (1 / (1 + np.exp(-np.asarray(raw)))).tolist()  # sigmoid -> [0, 1]


@lru_cache
def get_reranker():
    s = get_settings()
    if s.embedding_provider == "sentence-transformers":
        try:
            return CrossEncoderReranker(s.reranker_model)
        except Exception as e:
            print(f"[rerank] falling back to lexical reranker: {e}")
    return LexicalReranker()


def rerank(query: str, hits: list[Hit], k: int) -> list[Hit]:
    if not hits:
        return hits
    scores = get_reranker().score(query, hits)
    for h, s in zip(hits, scores):
        h.rerank = float(s)
    return sorted(hits, key=lambda h: -(h.rerank or 0))[:k]

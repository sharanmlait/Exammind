"""Embedding models.
- SentenceTransformerEmbedder: multilingual-e5 / bge-m3 — handles English, Hindi and Hinglish.
- HashEmbedder: dependency-free hashing-trick vectors; used offline and in tests."""
import hashlib
import re
from functools import lru_cache

import numpy as np

from ..config import get_settings

TOKEN_RE = re.compile(r"\w+", re.U)


class HashEmbedder:
    name = "hash-512"
    dim = 512

    def _vec(self, text: str) -> np.ndarray:
        v = np.zeros(self.dim, dtype=np.float32)
        toks = [t.lower() for t in TOKEN_RE.findall(text)]
        feats = toks + [f"{a}_{b}" for a, b in zip(toks, toks[1:])]
        for t in toks:  # char trigrams give some robustness to spelling variants (Hinglish!)
            feats += [t[i:i + 3] for i in range(max(1, len(t) - 2))]
        for f in feats:
            h = int(hashlib.md5(f.encode()).hexdigest()[:8], 16)
            v[h % self.dim] += 1.0 if (h >> 31) & 1 else -1.0
        n = np.linalg.norm(v)
        return v / n if n else v

    def embed_documents(self, texts: list[str]) -> np.ndarray:
        return np.vstack([self._vec(t) for t in texts]) if texts else np.zeros((0, self.dim), np.float32)

    def embed_query(self, text: str) -> np.ndarray:
        return self._vec(text)


class SentenceTransformerEmbedder:
    def __init__(self, model_name: str):
        from sentence_transformers import SentenceTransformer
        self.model = SentenceTransformer(model_name)
        self.name = model_name
        self.dim = self.model.get_sentence_embedding_dimension()
        self.e5 = "e5" in model_name.lower()   # e5 models expect "query:" / "passage:" prefixes

    def embed_documents(self, texts):
        if self.e5:
            texts = [f"passage: {t}" for t in texts]
        return np.asarray(self.model.encode(texts, normalize_embeddings=True, batch_size=32), dtype=np.float32)

    def embed_query(self, text):
        if self.e5:
            text = f"query: {text}"
        return np.asarray(self.model.encode([text], normalize_embeddings=True)[0], dtype=np.float32)


@lru_cache
def get_embedder():
    s = get_settings()
    if s.embedding_provider == "sentence-transformers":
        try:
            return SentenceTransformerEmbedder(s.embedding_model)
        except Exception as e:  # missing package or no internet for first download
            print(f"[embeddings] falling back to HashEmbedder: {e}")
    return HashEmbedder()

"""Per-subject hybrid index: dense vectors (NumPy, persisted as .npz) + BM25 keyword index.
For a student-scale corpus (thousands of chunks) brute-force cosine search is fast and simple;
swap in Qdrant/pgvector behind the same `search()` API if you scale up."""
import re
import threading
from dataclasses import dataclass

import numpy as np
from rank_bm25 import BM25Okapi

from .. import db
from ..config import get_settings
from .embeddings import get_embedder

STOP = set("""a an the of to in on for and or is are was were be been by with as at from that this
these those it its into than then so such which what how why when where who whom do does did can
could should would will shall may might explain define describe discuss write short note notes
kya hai hota hain ka ki ke ko se""".split())


def _stem(t: str) -> str:
    """Very light stemming so 'algorithms'/'algorithm', 'bankers'/'banker' match."""
    if len(t) > 4 and t.endswith("ies"):
        return t[:-3] + "y"
    if len(t) > 3 and t.endswith("s") and not t.endswith(("ss", "us", "is")):
        return t[:-1]
    return t


def tokenize(text: str) -> list[str]:
    text = re.sub(r"'s\b", "", text.lower())
    return [_stem(t) for t in re.findall(r"\w+", text, re.U) if t not in STOP and len(t) > 1]


@dataclass
class Hit:
    chunk_id: int
    text: str
    page: int | None
    document: str
    dense: float = 0.0
    sparse: float = 0.0
    score: float = 0.0
    rerank: float | None = None


class SubjectIndex:
    def __init__(self, subject_id: int):
        self.subject_id = subject_id
        self.path = get_settings().data_dir / f"vectors_{subject_id}.npz"
        self.ids: np.ndarray = np.zeros(0, dtype=np.int64)
        self.vecs: np.ndarray | None = None
        self.meta: dict[int, dict] = {}
        self.bm25: BM25Okapi | None = None
        self._load()

    def _load(self):
        chunks = db.rows("""SELECT c.id, c.text, c.page, d.filename FROM chunks c
                            JOIN documents d ON d.id = c.document_id
                            WHERE c.subject_id=? ORDER BY c.id""", (self.subject_id,))
        self.meta = {c["id"]: c for c in chunks}
        if self.path.exists():
            z = np.load(self.path)
            keep = np.isin(z["ids"], list(self.meta))
            self.ids, self.vecs = z["ids"][keep], z["vecs"][keep]
        missing = [cid for cid in self.meta if cid not in set(self.ids.tolist())]
        if missing:
            self.add(missing)
        self._build_bm25()

    def _build_bm25(self):
        order = self.ids.tolist()
        corpus = [tokenize(self.meta[i]["text"]) or ["_"] for i in order]
        self.bm25 = BM25Okapi(corpus) if corpus else None

    def add(self, chunk_ids: list[int]):
        have = set(self.ids.tolist())
        chunk_ids = [c for c in dict.fromkeys(chunk_ids) if c not in have]
        if not chunk_ids:
            return
        if any(c not in self.meta for c in chunk_ids):
            self.meta.update({c["id"]: c for c in db.rows(
                f"""SELECT c.id, c.text, c.page, d.filename FROM chunks c JOIN documents d ON d.id=c.document_id
                    WHERE c.id IN ({','.join('?' * len(chunk_ids))})""", chunk_ids)})
        vecs = get_embedder().embed_documents([self.meta[c]["text"] for c in chunk_ids])
        self.ids = np.concatenate([self.ids, np.asarray(chunk_ids, dtype=np.int64)])
        self.vecs = vecs if self.vecs is None or len(self.vecs) == 0 else np.vstack([self.vecs, vecs])
        np.savez(self.path, ids=self.ids, vecs=self.vecs)
        self._build_bm25()

    def __len__(self):
        return len(self.ids)

    def _hit(self, idx: int) -> Hit:
        m = self.meta[int(self.ids[idx])]
        return Hit(chunk_id=m["id"], text=m["text"], page=m["page"], document=m["filename"])

    def search(self, query: str, k: int = 5, mode: str = "hybrid", alpha: float | None = None) -> list[Hit]:
        """mode: dense | bm25 | hybrid. Returns hits with normalised scores in [0, 1]."""
        if not len(self):
            return []
        alpha = get_settings().hybrid_alpha if alpha is None else alpha
        n = len(self)
        dense = np.zeros(n)
        sparse = np.zeros(n)
        if mode in ("dense", "hybrid"):
            q = get_embedder().embed_query(query)
            dense = np.clip(self.vecs @ q, 0, 1)
        if mode in ("bm25", "hybrid") and self.bm25:
            qt = tokenize(query)
            raw = np.asarray(self.bm25.get_scores(qt))
            # Normalise against an "ideal" document that matches every query term, NOT against the best
            # hit — otherwise the top hit always scores 1.0 even for off-topic questions.
            idf = self.bm25.idf
            max_idf = max(idf.values()) if idf else 1.0
            ideal = sum(idf.get(t, max_idf) for t in qt) * (self.bm25.k1 + 1) or 1.0
            sparse = np.clip(raw / ideal, 0, 1)
        if mode == "dense":
            score = dense
        elif mode == "bm25":
            score = sparse
        else:
            score = alpha * dense + (1 - alpha) * sparse
        order = np.argsort(-score)[:k]
        hits = []
        for i in order:
            h = self._hit(int(i))
            h.dense, h.sparse, h.score = float(dense[i]), float(sparse[i]), float(score[i])
            hits.append(h)
        return hits


_indexes: dict[int, SubjectIndex] = {}
_lock = threading.Lock()


def get_index(subject_id: int) -> SubjectIndex:
    with _lock:
        if subject_id not in _indexes:
            _indexes[subject_id] = SubjectIndex(subject_id)
        return _indexes[subject_id]


def reset_indexes():
    with _lock:
        _indexes.clear()

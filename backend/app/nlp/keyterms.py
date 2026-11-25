"""Key-term, definition and formula extraction from notes (classic NLP, no LLM needed).
- Key terms: TF-IDF over chunks, scored per subject, with capitalised multi-word phrases boosted.
- Definitions: pattern matching on "X is a/an/the ...", "X refers to ...", "X is defined as ...".
- Formulas: lines with '=' plus math-ish symbols."""
import re
from collections import Counter

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer

from .. import db
from ..rag.store import STOP, tokenize

DEF_RE = re.compile(
    r"(?:^|(?<=[.!?]\s))([A-Z][\w\-()/ ]{2,60}?)\s+(?:is|are)\s+(?:defined as|called|known as|an?|the)\s+([^.]{15,240}\.)")
DEF_RE2 = re.compile(r"(?:^|(?<=[.!?]\s))([A-Z][\w\-()/ ]{2,60}?)\s+refers? to\s+([^.]{15,240}\.)")
FORMULA_RE = re.compile(r"^[^\n]{0,80}[A-Za-z_]\w*\s*=\s*[^\n=]{2,120}$", re.M)
PHRASE_RE = re.compile(r"\b(?:[A-Z][a-z]+|[A-Z]{2,})(?:\s+(?:[A-Z][a-z]+|[A-Z]{2,}|of|and))*\s+(?:[A-Z][a-z]+|[A-Z]{2,})\b")


GENERIC = {"unit", "introduction", "example", "used", "also", "main", "called", "each", "one", "two", "three", "time", "first", "information",
           "solution", "process", "memory", "page", "queue", "resource", "system", "not", "no",
           "management", "request", "more", "only"}
BAD_START = {"its", "if", "this", "it", "they", "there", "these", "when", "his", "her", "their"}


def _clean_term(t: str) -> str:
    return re.sub(r"^(a|an|the)\s+", "", t.strip(), flags=re.I)


def extract_keyterms(subject_id: int, limit: int = 30) -> dict:
    chunks = db.rows("""SELECT c.text, c.page, d.filename FROM chunks c JOIN documents d ON d.id=c.document_id
                        WHERE c.subject_id=? AND d.kind='notes'""", (subject_id,))
    if not chunks:
        return {"terms": [], "definitions": [], "formulas": []}
    # drop headings like "## Unit II: CPU Scheduling" so structural words don't become "key terms"
    texts = [re.sub(r"^#+ .*$", "", c["text"], flags=re.M) for c in chunks]

    vec = TfidfVectorizer(tokenizer=tokenize, token_pattern=None, ngram_range=(1, 3), max_df=0.6, min_df=1)
    m = vec.fit_transform(texts)
    scores = np.asarray(m.max(axis=0).todense()).ravel() + 0.2 * np.asarray((m > 0).sum(axis=0)).ravel() / len(texts)
    vocab = vec.get_feature_names_out()
    phrase_counts = Counter(_clean_term(p) for t in texts for p in PHRASE_RE.findall(t))
    boosted = {p.lower(): c for p, c in phrase_counts.items() if c >= 2}
    cand = {}
    for i in np.argsort(-scores)[: limit * 4]:
        term = vocab[i]
        if term.isdigit() or any(w in GENERIC for w in term.split()) or all(w in STOP for w in term.split()):
            continue
        cand[term] = float(scores[i]) * (1.5 if term in boosted else 1.0)
    for p, c in boosted.items():
        cand.setdefault(p, 0.3 + 0.05 * c)
    # drop terms fully contained in a higher-scoring longer term
    terms = []
    for t, s in sorted(cand.items(), key=lambda x: -x[1]):
        if not any(t in o and t != o for o, _ in terms):
            terms.append((t, s))
        if len(terms) >= limit:
            break

    defs, seen = [], set()
    for c in chunks:
        for rx in (DEF_RE, DEF_RE2):
            for term, body in rx.findall(c["text"]):
                term = _clean_term(term)
                k = term.lower()
                if k not in seen and len(k.split()) <= 6 and k.split()[0] not in BAD_START:
                    seen.add(k)
                    defs.append({"term": term.strip(), "definition": body.strip(),
                                 "source": c["filename"], "page": c["page"]})
    formulas = []
    for c in chunks:
        for f in FORMULA_RE.findall(c["text"]):
            f = f.strip()
            if re.search(r"[+\-*/^×÷()]|\b\d", f) and f not in [x["formula"] for x in formulas]:
                formulas.append({"formula": f, "source": c["filename"], "page": c["page"]})

    return {"terms": [{"term": t, "score": round(s, 3)} for t, s in terms],
            "definitions": defs[:40], "formulas": formulas[:30]}

"""Upload pipeline: extract text -> route by document kind -> store -> index / parse / classify."""
from .. import db
from ..config import get_settings
from ..nlp.classifier import retag_questions
from ..rag.store import get_index
from .chunker import chunk_pages
from .extract import extract
from .parsers import parse_pyq, parse_syllabus

KINDS = {"notes", "pyq", "syllabus"}


def ingest_document(subject_id: int, filename: str, data: bytes, kind: str, year: int | None = None) -> dict:
    if kind not in KINDS:
        raise ValueError(f"kind must be one of {sorted(KINDS)}")
    pages = extract(filename, data)
    if not any(p.text for p in pages):
        raise ValueError("No text found. If this is a scanned PDF, install Tesseract OCR (see README).")
    ocr_used = any(p.ocr for p in pages)
    doc_id = db.execute("INSERT INTO documents(subject_id, filename, kind, year, pages, ocr_used, created_at) "
                        "VALUES (?,?,?,?,?,?,?)",
                        (subject_id, filename, kind, year, len(pages), int(ocr_used), db.now()))
    full_text = "\n".join(p.text for p in pages)
    out = {"document_id": doc_id, "filename": filename, "kind": kind, "pages": len(pages), "ocr_used": ocr_used}

    if kind == "notes":  # syllabus is parsed into topics, not indexed (it would pollute retrieval)
        s = get_settings()
        chunks = chunk_pages(pages, s.chunk_size, s.chunk_overlap)
        ids = []
        for c in chunks:
            ids.append(db.execute("INSERT INTO chunks(subject_id, document_id, page, position, text) VALUES (?,?,?,?,?)",
                                  (subject_id, doc_id, c.page, c.position, c.text)))
        get_index(subject_id).add(ids)
        out["chunks"] = len(ids)

    if kind == "syllabus":
        topics = parse_syllabus(full_text)
        db.executemany("INSERT INTO topics(subject_id, unit, name, description) VALUES (?,?,?,?)",
                       [(subject_id, t.unit, t.name, t.description) for t in topics])
        out["topics"] = len(topics)
        retag_questions(subject_id)   # new labels -> re-tag existing PYQs

    if kind == "pyq":
        qs = parse_pyq(full_text, year=year, filename=filename)
        if year is None and qs and qs[0].year:
            db.execute("UPDATE documents SET year=? WHERE id=?", (qs[0].year, doc_id))
        db.executemany("INSERT INTO questions(subject_id, document_id, year, marks, text) VALUES (?,?,?,?,?)",
                       [(subject_id, doc_id, q.year, q.marks, q.text) for q in qs])
        out["questions"] = len(qs)
        out["year"] = qs[0].year if qs else year
        retag_questions(subject_id)
    return out


def delete_document(subject_id: int, doc_id: int) -> None:
    from ..rag.store import reset_indexes
    for t in ("chunks", "questions"):
        db.execute(f"DELETE FROM {t} WHERE document_id=? AND subject_id=?", (doc_id, subject_id))
    doc = db.one("SELECT kind FROM documents WHERE id=?", (doc_id,))
    db.execute("DELETE FROM documents WHERE id=? AND subject_id=?", (doc_id, subject_id))
    if doc and doc["kind"] == "syllabus":
        db.execute("DELETE FROM topics WHERE subject_id=?", (subject_id,))
    reset_indexes()

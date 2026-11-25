"""Load the sample Operating Systems subject. Run: `python -m scripts.seed_demo` from backend/."""
from pathlib import Path

from app import db
from app.ingest.service import ingest_document

SAMPLE = Path(__file__).resolve().parents[2] / "data" / "sample"


def seed(name: str = "Operating Systems (demo)") -> dict:
    db.init_db()
    existing = db.one("SELECT id FROM subjects WHERE name=?", (name,))
    if existing:
        return {"subject_id": existing["id"], "created": False}
    sid = db.execute("INSERT INTO subjects(name, created_at) VALUES (?,?)", (name, db.now()))
    results = [ingest_document(sid, "os_syllabus.txt", (SAMPLE / "os_syllabus.txt").read_bytes(), "syllabus"),
               ingest_document(sid, "os_notes.md", (SAMPLE / "os_notes.md").read_bytes(), "notes")]
    for f in sorted(SAMPLE.glob("pyq_os_*.txt")):
        results.append(ingest_document(sid, f.name, f.read_bytes(), "pyq"))
    return {"subject_id": sid, "created": True, "documents": results}


if __name__ == "__main__":
    import json
    print(json.dumps(seed(), indent=2))

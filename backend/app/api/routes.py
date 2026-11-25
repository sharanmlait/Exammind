from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field

from .. import db
from ..agent.planner import run_planner
from ..generation.exam import exam_answer, practice, summarize
from ..generation.grader import grade
from ..ingest.service import delete_document, ingest_document
from ..llm import LLMError
from ..ml.topic_predictor import predict_hot_topics
from ..nlp.classifier import get_classifier
from ..nlp.keyterms import extract_keyterms
from ..rag.pipeline import answer_question

router = APIRouter(prefix="/api")
MAX_UPLOAD = 25 * 1024 * 1024


def _subject(sid: int) -> dict:
    s = db.one("SELECT * FROM subjects WHERE id=?", (sid,))
    if not s:
        raise HTTPException(404, "Subject not found")
    return s


def _llm_guard(fn, *a, **kw):
    try:
        return fn(*a, **kw)
    except LLMError as e:
        raise HTTPException(503, f"LLM unavailable: {e}")


# ---------- subjects & documents ----------
class SubjectIn(BaseModel):
    name: str = Field(min_length=2, max_length=80)


@router.get("/subjects")
def list_subjects():
    return db.rows("""SELECT s.*, (SELECT COUNT(*) FROM documents d WHERE d.subject_id=s.id) AS documents,
                      (SELECT COUNT(*) FROM questions q WHERE q.subject_id=s.id) AS questions,
                      (SELECT COUNT(*) FROM topics t WHERE t.subject_id=s.id) AS topics
                      FROM subjects s ORDER BY s.id DESC""")


@router.post("/subjects")
def create_subject(body: SubjectIn):
    sid = db.execute("INSERT INTO subjects(name, created_at) VALUES (?,?)", (body.name.strip(), db.now()))
    return _subject(sid)


@router.get("/subjects/{sid}")
def get_subject(sid: int):
    s = _subject(sid)
    s["documents"] = db.rows("SELECT * FROM documents WHERE subject_id=? ORDER BY id DESC", (sid,))
    s["stats"] = {k: db.one(f"SELECT COUNT(*) AS n FROM {k} WHERE subject_id=?", (sid,))["n"]
                  for k in ("chunks", "topics", "questions", "attempts")}
    return s


@router.post("/subjects/{sid}/documents")
async def upload(sid: int, file: UploadFile = File(...), kind: str = Form("notes"), year: int | None = Form(None)):
    _subject(sid)
    data = await file.read()
    if len(data) > MAX_UPLOAD:
        raise HTTPException(413, "File too large (max 25 MB)")
    try:
        return ingest_document(sid, file.filename or "upload", data, kind, year)
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.delete("/subjects/{sid}/documents/{doc_id}")
def remove_document(sid: int, doc_id: int):
    delete_document(sid, doc_id)
    return {"ok": True}


# ---------- topics, questions, ML ----------
@router.get("/subjects/{sid}/topics")
def topics(sid: int):
    _subject(sid)
    return db.rows("""SELECT t.id, t.unit, t.name, COUNT(q.id) AS times_asked FROM topics t
                      LEFT JOIN questions q ON q.subject_id=t.subject_id AND q.topic=t.name
                      WHERE t.subject_id=? GROUP BY t.id ORDER BY t.id""", (sid,))


@router.get("/subjects/{sid}/questions")
def questions(sid: int, topic: str | None = None):
    _subject(sid)
    if topic:
        return db.rows("SELECT * FROM questions WHERE subject_id=? AND topic=? ORDER BY year DESC", (sid, topic))
    return db.rows("SELECT * FROM questions WHERE subject_id=? ORDER BY year DESC, id", (sid,))


class RelabelIn(BaseModel):
    topic: str


@router.put("/subjects/{sid}/questions/{qid}")
def relabel(sid: int, qid: int, body: RelabelIn):
    """Human correction. confidence=1.0 marks it as a gold label the classifier will learn from."""
    db.execute("UPDATE questions SET topic=?, confidence=1.0 WHERE id=? AND subject_id=?", (body.topic, qid, sid))
    return {"ok": True}


class ClassifyIn(BaseModel):
    text: str


@router.post("/subjects/{sid}/classify")
def classify(sid: int, body: ClassifyIn):
    clf = get_classifier(sid)
    p = clf.predict([body.text])[0]
    return {"topic": p.topic, "confidence": round(p.confidence, 3), "alternatives": p.alternatives, "model": clf.name}


@router.get("/subjects/{sid}/hot-topics")
def hot_topics(sid: int, limit: int = 15):
    _subject(sid)
    return predict_hot_topics(sid, limit)


@router.get("/subjects/{sid}/keyterms")
def keyterms(sid: int):
    _subject(sid)
    return extract_keyterms(sid)


# ---------- LLM features ----------
class ChatIn(BaseModel):
    question: str = Field(min_length=2, max_length=2000)
    history: list[dict] = []


@router.post("/subjects/{sid}/chat")
def chat(sid: int, body: ChatIn):
    _subject(sid)
    return _llm_guard(answer_question, sid, body.question, body.history).dict()


class AnswerIn(BaseModel):
    question: str = Field(min_length=3)
    marks: int = Field(5, ge=1, le=20)


@router.post("/subjects/{sid}/answer")
def write_answer(sid: int, body: AnswerIn):
    _subject(sid)
    return _llm_guard(exam_answer, sid, body.question, body.marks)


class TopicIn(BaseModel):
    topic: str


@router.post("/subjects/{sid}/summarize")
def summary(sid: int, body: TopicIn):
    _subject(sid)
    return _llm_guard(summarize, sid, body.topic)


class PracticeIn(BaseModel):
    topic: str
    n: int = Field(5, ge=1, le=15)
    kind: str = Field("mcq", pattern="^(mcq|short)$")


@router.post("/subjects/{sid}/practice")
def make_practice(sid: int, body: PracticeIn):
    _subject(sid)
    return _llm_guard(practice, sid, body.topic, body.n, body.kind)


class GradeIn(BaseModel):
    question: str
    answer: str
    max_marks: int = Field(10, ge=1, le=20)
    reference: str | None = None


@router.post("/subjects/{sid}/grade")
def grade_answer(sid: int, body: GradeIn):
    _subject(sid)
    topic = get_classifier(sid).predict([body.question])[0].topic
    res = _llm_guard(grade, sid, body.question, body.answer, body.max_marks, body.reference, topic)
    res["topic"] = topic
    return res


class PlanIn(BaseModel):
    days: int = Field(7, ge=1, le=60)
    hours_per_day: float = Field(3, gt=0, le=14)
    goal: str = ""


@router.post("/subjects/{sid}/plan")
def plan(sid: int, body: PlanIn):
    _subject(sid)
    return run_planner(sid, body.days, body.hours_per_day, body.goal)


# ---------- feedback loop ----------
class FeedbackIn(BaseModel):
    subject_id: int | None = None
    kind: str
    prompt: str = ""
    response: str = ""
    rating: int = Field(ge=-1, le=1)
    comment: str = ""


@router.post("/feedback")
def feedback(body: FeedbackIn):
    db.execute("INSERT INTO feedback(subject_id, kind, prompt, response, rating, comment, created_at) "
               "VALUES (?,?,?,?,?,?,?)",
               (body.subject_id, body.kind, body.prompt, body.response, body.rating, body.comment, db.now()))
    return {"ok": True}

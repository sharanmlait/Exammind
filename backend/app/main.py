from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import db
from .api.routes import router
from .config import get_settings
from .rag.embeddings import get_embedder

@asynccontextmanager
async def lifespan(_app):
    db.init_db()
    yield


app = FastAPI(title="ExamMind API", version="1.0.0", lifespan=lifespan,
              description="RAG + fine-tuned LLM + NLP + ML exam-prep assistant")
app.add_middleware(CORSMiddleware, allow_origins=get_settings().cors_origins.split(","),
                   allow_methods=["*"], allow_headers=["*"])
app.include_router(router)


@app.get("/api/health")
def health():
    s = get_settings()
    return {"status": "ok", "llm": s.llm_provider, "answer_llm": s.answer_llm_provider or s.llm_provider,
            "embeddings": get_embedder().name}


@app.post("/api/demo/seed")
def seed_demo():
    """Loads the sample Operating Systems subject (syllabus, notes, 7 years of PYQs)."""
    from scripts.seed_demo import seed
    return seed()

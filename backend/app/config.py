"""Central configuration. Every setting can be overridden with an environment variable
(or a .env file in backend/). See .env.example for the full list."""
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BASE_DIR / ".env", extra="ignore")

    # ---- storage ----
    data_dir: Path = BASE_DIR / "storage"

    # ---- LLM used for chat / generation / grading / agent ----
    # one of: groq | gemini | ollama | mock
    llm_provider: str = "groq"
    groq_api_key: str = ""
    groq_model: str = "llama-3.3-70b-versatile"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"
    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "exammind"

    # ---- LLM used for exam-style answers (this is where YOUR fine-tuned model plugs in) ----
    # leave empty to reuse llm_provider; set to "ollama" + ollama_model=exammind after fine-tuning
    answer_llm_provider: str = ""

    llm_temperature: float = 0.3
    llm_timeout: float = 60.0

    # ---- embeddings ----
    # sentence-transformers (multilingual, recommended) | hash (offline fallback, used in tests)
    embedding_provider: str = "sentence-transformers"
    embedding_model: str = "intfloat/multilingual-e5-small"

    # ---- retrieval ----
    chunk_size: int = 700          # characters
    chunk_overlap: int = 120
    top_k: int = 5
    hybrid_alpha: float = 0.6      # weight of dense score vs BM25 in hybrid search
    use_reranker: bool = True
    reranker_model: str = "BAAI/bge-reranker-base"  # falls back to lexical reranker if unavailable
    min_relevance: float = 0.15    # below this, the guardrail says "not in your notes"

    # ---- topic classifier ----
    classifier_model_dir: Path = BASE_DIR.parent / "training" / "classifier" / "output"

    cors_origins: str = "http://localhost:3000"


@lru_cache
def get_settings() -> Settings:
    s = Settings()
    s.data_dir.mkdir(parents=True, exist_ok=True)
    return s

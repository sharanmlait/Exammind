from functools import lru_cache

from ..config import get_settings
from .base import LLMError, LLMProvider, LLMResult, parse_json
from .mock import MockProvider
from .providers import GeminiProvider, GroqProvider, OllamaProvider


def build_provider(name: str) -> LLMProvider:
    s = get_settings()
    name = (name or "mock").lower()
    if name == "groq":
        return GroqProvider(s.groq_api_key, s.groq_model, s.llm_timeout)
    if name == "gemini":
        return GeminiProvider(s.gemini_api_key, s.gemini_model, s.llm_timeout)
    if name == "ollama":
        return OllamaProvider(s.ollama_url, s.ollama_model, max(s.llm_timeout, 120))
    if name == "mock":
        return MockProvider()
    raise LLMError(f"Unknown LLM provider '{name}'")


@lru_cache
def get_llm() -> LLMProvider:
    """General-purpose LLM (chat, MCQs, grading, agent)."""
    return build_provider(get_settings().llm_provider)


@lru_cache
def get_answer_llm() -> LLMProvider:
    """Exam-answer writer. Point ANSWER_LLM_PROVIDER=ollama at your fine-tuned model."""
    s = get_settings()
    return build_provider(s.answer_llm_provider or s.llm_provider)


__all__ = ["get_llm", "get_answer_llm", "build_provider", "LLMError", "LLMProvider", "LLMResult", "parse_json"]

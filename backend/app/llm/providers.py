"""Concrete providers: Groq (OpenAI-compatible), Gemini, Ollama (your fine-tuned model)."""
import httpx

from .base import LLMError, LLMProvider


class GroqProvider(LLMProvider):
    name = "groq"
    URL = "https://api.groq.com/openai/v1/chat/completions"

    def __init__(self, api_key: str, model: str, timeout: float = 60):
        if not api_key:
            raise LLMError("GROQ_API_KEY is not set (get a free key at console.groq.com)")
        self.api_key, self.model, self.timeout = api_key, model, timeout

    def _complete(self, messages, json_mode, temperature, task):
        body = {"model": self.model, "messages": messages, "temperature": temperature}
        if json_mode:
            body["response_format"] = {"type": "json_object"}
        r = httpx.post(self.URL, json=body, timeout=self.timeout,
                       headers={"Authorization": f"Bearer {self.api_key}"})
        if r.status_code != 200:
            raise LLMError(f"Groq error {r.status_code}: {r.text[:300]}")
        return r.json()["choices"][0]["message"]["content"]


class GeminiProvider(LLMProvider):
    name = "gemini"

    def __init__(self, api_key: str, model: str, timeout: float = 60):
        if not api_key:
            raise LLMError("GEMINI_API_KEY is not set (get a free key at aistudio.google.com)")
        self.api_key, self.model, self.timeout = api_key, model, timeout

    def _complete(self, messages, json_mode, temperature, task):
        system = "\n\n".join(m["content"] for m in messages if m["role"] == "system")
        contents = [
            {"role": "model" if m["role"] == "assistant" else "user", "parts": [{"text": m["content"]}]}
            for m in messages if m["role"] != "system"
        ]
        body = {"contents": contents, "generationConfig": {"temperature": temperature}}
        if system:
            body["systemInstruction"] = {"parts": [{"text": system}]}
        if json_mode:
            body["generationConfig"]["responseMimeType"] = "application/json"
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent"
        r = httpx.post(url, json=body, timeout=self.timeout, headers={"x-goog-api-key": self.api_key})
        if r.status_code != 200:
            raise LLMError(f"Gemini error {r.status_code}: {r.text[:300]}")
        try:
            return "".join(p.get("text", "") for p in r.json()["candidates"][0]["content"]["parts"])
        except (KeyError, IndexError) as e:
            raise LLMError(f"Unexpected Gemini response: {r.text[:300]}") from e


class OllamaProvider(LLMProvider):
    """Local models via Ollama — use this for your QLoRA fine-tuned + GGUF-quantized model."""
    name = "ollama"

    def __init__(self, url: str, model: str, timeout: float = 120):
        self.url, self.model, self.timeout = url.rstrip("/"), model, timeout

    def _complete(self, messages, json_mode, temperature, task):
        body = {"model": self.model, "messages": messages, "stream": False,
                "options": {"temperature": temperature}}
        if json_mode:
            body["format"] = "json"
        try:
            r = httpx.post(f"{self.url}/api/chat", json=body, timeout=self.timeout)
        except httpx.HTTPError as e:
            raise LLMError(f"Cannot reach Ollama at {self.url}: {e}") from e
        if r.status_code != 200:
            raise LLMError(f"Ollama error {r.status_code}: {r.text[:300]}")
        return r.json()["message"]["content"]

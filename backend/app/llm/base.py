"""LLM provider interface + JSON helpers shared by every feature."""
import json
import re
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class LLMResult:
    text: str
    provider: str
    model: str
    latency_ms: int = 0
    meta: dict = field(default_factory=dict)


class LLMError(RuntimeError):
    pass


class LLMProvider(ABC):
    name = "base"
    model = ""

    @abstractmethod
    def _complete(self, messages: list[dict], json_mode: bool, temperature: float, task: str | None) -> str:
        ...

    def complete(self, messages: list[dict], *, json_mode: bool = False,
                 temperature: float = 0.3, task: str | None = None) -> LLMResult:
        """`task` is a short label (e.g. "rag_answer", "mcq") used for logging and by the mock provider."""
        t0 = time.perf_counter()
        text = self._complete(messages, json_mode, temperature, task)
        return LLMResult(text=text, provider=self.name, model=self.model,
                         latency_ms=int((time.perf_counter() - t0) * 1000))

    def complete_json(self, messages: list[dict], *, temperature: float = 0.2,
                      task: str | None = None, retries: int = 1):
        """Ask for JSON, parse it, and retry once with the parse error if the model slips."""
        msgs = list(messages)
        last_err = None
        for _ in range(retries + 1):
            res = self.complete(msgs, json_mode=True, temperature=temperature, task=task)
            try:
                return parse_json(res.text)
            except ValueError as e:
                last_err = e
                msgs = msgs + [
                    {"role": "assistant", "content": res.text},
                    {"role": "user", "content": f"That was not valid JSON ({e}). Reply with ONLY valid JSON."},
                ]
        raise LLMError(f"Model did not return valid JSON: {last_err}")


def parse_json(text: str):
    """Parse JSON even when wrapped in ```json fences or surrounded by chatter."""
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    if fence:
        text = fence.group(1).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    for open_c, close_c in (("{", "}"), ("[", "]")):
        s, e = text.find(open_c), text.rfind(close_c)
        if s != -1 and e > s:
            try:
                return json.loads(text[s:e + 1])
            except json.JSONDecodeError:
                continue
    raise ValueError("no JSON object found")

"""Safety + grounding checks around the LLM.
1. Prompt-injection scrubbing of retrieved text (uploaded PDFs are untrusted input).
2. Refuse to answer when retrieval confidence is too low (stops hallucinated answers).
3. Validate citations: every [S#] must point to a real source; flag answers with none."""
import re

INJECTION_PATTERNS = [
    r"ignore (all |any )?(previous|prior|above) (instructions|prompts?)",
    r"disregard (the )?(system|previous) (prompt|instructions)",
    r"you are now [a-z ]+",
    r"reveal (your|the) (system )?prompt",
    r"pretend to be",
    r"act as (an? )?(unfiltered|jailbroken|dan)",
]
_inj = re.compile("|".join(INJECTION_PATTERNS), re.I)


def scrub(text: str) -> tuple[str, bool]:
    found = bool(_inj.search(text))
    return _inj.sub("[removed instruction]", text), found


def low_confidence(best_score: float, threshold: float) -> bool:
    return best_score < threshold


def check_citations(answer: str, n_sources: int) -> dict:
    cited = {int(x) for x in re.findall(r"\[S(\d+)\]", answer)}
    valid = {c for c in cited if 1 <= c <= n_sources}
    return {
        "cited": sorted(valid),
        "invalid": sorted(cited - valid),
        "has_citations": bool(valid),
    }


def strip_invalid_citations(answer: str, n_sources: int) -> str:
    return re.sub(r"\[S(\d+)\]", lambda m: m.group(0) if 1 <= int(m.group(1)) <= n_sources else "", answer)

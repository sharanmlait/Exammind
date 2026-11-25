"""Lightweight language detection for English / Hindi (Devanagari) / Hinglish (romanised Hindi)."""
import re

HINGLISH = set("""kya hai hain kaise kyu kyun kyon hota hoti hote mujhe batao samjhao matlab aur ya nahi
nahin kaun kab kahan ke ki ka ko se mein me par bhi toh yeh ye woh wo karo kar karte karta liye
wala wali kuch sab accha acha""".split())


def detect_language(text: str) -> str:
    if re.search(r"[ऀ-ॿ]", text):
        return "hindi"
    words = re.findall(r"[a-z]+", text.lower())
    if words and sum(w in HINGLISH for w in words) / len(words) >= 0.2:
        return "hinglish"
    return "english"


def reply_instruction(lang: str) -> str:
    return {
        "hindi": "The student wrote in Hindi. Reply in simple Hindi (Devanagari); keep technical terms in English.",
        "hinglish": "The student wrote in Hinglish. Reply in friendly Hinglish (Roman script), keep technical terms in English.",
    }.get(lang, "Reply in clear, simple English.")

"""Recursive, sentence-aware chunking with overlap.
Splits on headings/paragraphs first, then sentences, so chunks don't cut ideas in half."""
import re
from dataclasses import dataclass


@dataclass
class Chunk:
    text: str
    page: int
    position: int


def _split_sentences(text: str) -> list[str]:
    return [s for s in re.split(r"(?<=[.!?।])\s+", text) if s.strip()]


def _overlap_tail(buf: str, overlap: int) -> str:
    """Carry over the last whole sentence(s) that fit in `overlap` chars, so the next chunk
    starts at a sentence boundary instead of mid-word."""
    tail = []
    for s in reversed(_split_sentences(buf.replace("\n", " "))):
        if sum(len(t) + 1 for t in tail) + len(s) > overlap:
            break
        tail.insert(0, s)
    return " ".join(tail)


def chunk_pages(pages, size: int = 700, overlap: int = 120) -> list[Chunk]:
    chunks: list[Chunk] = []
    pos = 0
    for page in pages:
        paras = [p.strip() for p in re.split(r"\n\s*\n|(?=\n#+ )", page.text) if p.strip()]
        buf = ""
        for para in paras:
            para = re.sub(r"[ \t]+", " ", para)
            if para.startswith("#") and buf.strip():   # a new heading starts a new chunk (no overlap)
                chunks.append(Chunk(buf.strip(), page.number, pos))
                pos += 1
                buf = ""
            pieces = [para] if len(para) <= size else _split_sentences(para)
            for piece in pieces:
                if len(piece) > size:  # a single monster sentence: hard-wrap it
                    for i in range(0, len(piece), size - overlap):
                        chunks.append(Chunk(piece[i:i + size], page.number, pos))
                        pos += 1
                    continue
                if len(buf) + len(piece) + 1 > size and buf:
                    chunks.append(Chunk(buf.strip(), page.number, pos))
                    pos += 1
                    buf = _overlap_tail(buf, overlap)
                buf += ("\n" if buf else "") + piece
        if buf.strip():
            chunks.append(Chunk(buf.strip(), page.number, pos))
            pos += 1
    return [c for c in chunks if len(c.text.split()) >= 4]

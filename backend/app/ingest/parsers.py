"""Parse a syllabus into units/topics and a PYQ paper into individual questions."""
import re
from dataclasses import dataclass

UNIT_RE = re.compile(r"^\s*(unit|module)\s*[-–:]?\s*([IVX\d]+)\s*[:.\-–]?\s*(.*)$", re.I)


@dataclass
class SyllabusTopic:
    unit: str
    name: str
    description: str


def parse_syllabus(text: str) -> list[SyllabusTopic]:
    """Expected shape (very common in Indian university syllabi):
        UNIT I: Introduction
        Topic A, Topic B; Topic C ...
    Each comma/semicolon separated item becomes a topic; the unit title gives context."""
    topics: list[SyllabusTopic] = []
    unit, unit_title, body = None, "", []

    def flush():
        if unit is None:
            return
        joined = " ".join(body)
        items = [i.strip(" .-–") for i in re.split(r"[;,]|\s-\s|\n", joined) if len(i.strip()) > 2]
        if not items and unit_title:
            items = [unit_title]
        for it in items:
            topics.append(SyllabusTopic(unit=f"Unit {unit}", name=it[:120], description=f"{unit_title}: {it}"))

    for line in text.splitlines():
        m = UNIT_RE.match(line)
        if m:
            flush()
            unit, unit_title, body = m.group(2).upper(), m.group(3).strip(), []
            # some syllabi put topics on the same line after the title, separated by ':' or '-'
            if re.search(r"[:\-–]", unit_title):
                head, _, rest = re.split(r"([:\-–])", unit_title, maxsplit=1)
                unit_title, body = head.strip(), [rest]
        elif unit is not None and line.strip():
            body.append(line.strip())
    flush()
    # dedupe while keeping order
    seen, out = set(), []
    for t in topics:
        k = t.name.lower()
        if k not in seen:
            seen.add(k)
            out.append(t)
    return out


@dataclass
class PYQ:
    text: str
    marks: int | None
    year: int | None


Q_START = re.compile(r"^\s*(?:Q\.?\s*\d+(?:[a-z](?![a-z]))?\s*[.):\-]?|\d+\s*[.)]|\(?[a-h]\)|[ivx]+\))\s*", re.I)
MARKS_RE = re.compile(r"[\(\[]\s*(\d{1,2})\s*(?:marks?|m)?\s*[\)\]]\s*$", re.I)
SECTION_RE = re.compile(r"^\s*(section|part|unit|note|instructions?)\b", re.I)
YEAR_RE = re.compile(r"\b(20[0-3]\d)\b")


def detect_year(*texts: str) -> int | None:
    for t in texts:
        if t and (m := YEAR_RE.search(t)):
            return int(m.group(1))
    return None


def parse_pyq(text: str, year: int | None = None, filename: str = "") -> list[PYQ]:
    year = year or detect_year(filename, text[:400])
    questions, cur = [], []

    def flush():
        if not cur:
            return
        q = " ".join(cur).strip()
        marks = None
        if m := MARKS_RE.search(q):
            marks, q = int(m.group(1)), q[:m.start()].strip()
        if len(q.split()) >= 4 and not re.match(r"^(note|time|max\.? marks|section)", q, re.I):
            questions.append(PYQ(q, marks, year))

    for line in text.splitlines():
        if not line.strip():
            continue
        if SECTION_RE.match(line):
            flush()
            cur = []
            continue
        if Q_START.match(line):
            flush()
            cur = [Q_START.sub("", line).strip()]
        elif cur:
            cur.append(line.strip())
    flush()
    return questions

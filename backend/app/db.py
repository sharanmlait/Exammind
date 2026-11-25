"""Tiny SQLite data layer. Plain sqlite3 keeps the project dependency-light and easy to read."""
import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone

from .config import get_settings

SCHEMA = """
CREATE TABLE IF NOT EXISTS subjects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    subject_id INTEGER NOT NULL,
    filename TEXT NOT NULL,
    kind TEXT NOT NULL,            -- notes | pyq | syllabus
    year INTEGER,
    pages INTEGER DEFAULT 0,
    ocr_used INTEGER DEFAULT 0,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS chunks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    subject_id INTEGER NOT NULL,
    document_id INTEGER NOT NULL,
    page INTEGER,
    position INTEGER,
    text TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS topics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    subject_id INTEGER NOT NULL,
    unit TEXT,
    name TEXT NOT NULL,
    description TEXT
);
CREATE TABLE IF NOT EXISTS questions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    subject_id INTEGER NOT NULL,
    document_id INTEGER,
    year INTEGER,
    marks INTEGER,
    text TEXT NOT NULL,
    topic TEXT,
    confidence REAL
);
CREATE TABLE IF NOT EXISTS attempts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    subject_id INTEGER NOT NULL,
    question TEXT NOT NULL,
    topic TEXT,
    score REAL,
    max_score REAL,
    feedback TEXT,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS feedback (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    subject_id INTEGER,
    kind TEXT,                     -- chat | answer | practice | grade
    prompt TEXT,
    response TEXT,
    rating INTEGER,                -- +1 / -1
    comment TEXT,
    created_at TEXT NOT NULL
);
"""


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _path():
    return get_settings().data_dir / "exammind.db"


def init_db() -> None:
    with connect() as con:
        con.executescript(SCHEMA)


@contextmanager
def connect():
    con = sqlite3.connect(_path())
    con.row_factory = sqlite3.Row
    try:
        yield con
        con.commit()
    finally:
        con.close()


def rows(sql: str, params=()) -> list[dict]:
    with connect() as con:
        return [dict(r) for r in con.execute(sql, params).fetchall()]


def one(sql: str, params=()) -> dict | None:
    r = rows(sql, params)
    return r[0] if r else None


def execute(sql: str, params=()) -> int:
    with connect() as con:
        cur = con.execute(sql, params)
        return cur.lastrowid


def executemany(sql: str, seq) -> None:
    with connect() as con:
        con.executemany(sql, seq)


def to_json(x) -> str:
    return json.dumps(x, ensure_ascii=False)

"""Trinity's local database: schema + connection management.

SQLite with FTS5 (full-text search) for the local knowledge base — no
external services, no network calls. Everything Trinity knows lives here.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

DEFAULT_DB_PATH = Path.home() / ".trinity" / "trinity.db"

SCHEMA = """
-- One row per HTB/THM box or CTF target you're actively working.
CREATE TABLE IF NOT EXISTS boxes (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    target TEXT,                      -- IP or hostname
    platform TEXT,                    -- 'htb', 'thm', 'ctf', 'other'
    status TEXT DEFAULT 'active',     -- 'active', 'rooted', 'abandoned'
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- Every parsed finding from every scan, tied to a box.
-- This is the raw structured output layer — one row per discovered fact.
CREATE TABLE IF NOT EXISTS findings (
    id INTEGER PRIMARY KEY,
    box_id INTEGER NOT NULL REFERENCES boxes(id),
    source_tool TEXT NOT NULL,        -- 'nmap', 'gobuster', 'ffuf', 'nikto', ...
    kind TEXT NOT NULL,               -- 'port', 'path', 'vuln', 'header', ...
    host TEXT,
    port INTEGER,
    service TEXT,
    product TEXT,
    version TEXT,
    path TEXT,
    status_code INTEGER,
    detail TEXT,                      -- free-text extra (banner, raw line, etc.)
    raw_ref TEXT,                     -- path to the raw scan file this came from
    matched INTEGER DEFAULT 0,        -- 1 once matched against the KB
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- The local knowledge base: technique/vuln/reference entries Trinity can
-- match findings against without ever calling out to an LLM.
CREATE TABLE IF NOT EXISTS kb_entries (
    id INTEGER PRIMARY KEY,
    source TEXT NOT NULL,             -- 'searchsploit', 'gtfobins', 'lolbas',
                                       -- 'payloadsallthethings', 'user_notes'
    title TEXT NOT NULL,
    summary TEXT NOT NULL,            -- short, ELI5-able explanation
    detail TEXT,                      -- longer reference / commands / links
    match_service TEXT,               -- e.g. 'vsftpd' — cheap pre-filter
    match_version TEXT,               -- e.g. '2.3.4' or a semver range string
    tags TEXT,                        -- comma-separated: 'ftp,backdoor,rce'
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- Full-text search index over the KB — this is what makes lookups instant
-- and free (no embeddings, no API calls, just SQLite's built-in FTS5).
CREATE VIRTUAL TABLE IF NOT EXISTS kb_fts USING fts5(
    title, summary, detail, tags,
    content='kb_entries', content_rowid='id'
);

-- Keep kb_fts in sync with kb_entries automatically.
CREATE TRIGGER IF NOT EXISTS kb_entries_ai AFTER INSERT ON kb_entries BEGIN
    INSERT INTO kb_fts(rowid, title, summary, detail, tags)
    VALUES (new.id, new.title, new.summary, new.detail, new.tags);
END;
CREATE TRIGGER IF NOT EXISTS kb_entries_ad AFTER DELETE ON kb_entries BEGIN
    INSERT INTO kb_fts(kb_fts, rowid, title, summary, detail, tags)
    VALUES ('delete', old.id, old.title, old.summary, old.detail, old.tags);
END;
CREATE TRIGGER IF NOT EXISTS kb_entries_au AFTER UPDATE ON kb_entries BEGIN
    INSERT INTO kb_fts(kb_fts, rowid, title, summary, detail, tags)
    VALUES ('delete', old.id, old.title, old.summary, old.detail, old.tags);
    INSERT INTO kb_fts(rowid, title, summary, detail, tags)
    VALUES (new.id, new.title, new.summary, new.detail, new.tags);
END;

-- Every command Trinity has ever suggested + its ELI5 explanation, cached
-- locally so the same flag combo never needs re-explaining (and never
-- costs a token twice).
CREATE TABLE IF NOT EXISTS command_explanations (
    id INTEGER PRIMARY KEY,
    command TEXT NOT NULL UNIQUE,     -- normalized command string
    explanation TEXT NOT NULL,        -- ELI5 explanation
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- A log of every suggestion Trinity made to the operator: what command,
-- why, and whether it was run. Lets Trinity avoid repeating itself and
-- gives you a session history per box.
CREATE TABLE IF NOT EXISTS suggestions (
    id INTEGER PRIMARY KEY,
    box_id INTEGER NOT NULL REFERENCES boxes(id),
    phase TEXT,                       -- 'recon', 'enum', 'foothold', 'privesc', 'post'
    command TEXT NOT NULL,
    rationale TEXT,                   -- why Trinity suggested this
    accepted INTEGER DEFAULT 0,       -- did the operator run it
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_findings_box ON findings(box_id);
CREATE INDEX IF NOT EXISTS idx_findings_matched ON findings(matched);
CREATE INDEX IF NOT EXISTS idx_kb_service ON kb_entries(match_service);
CREATE INDEX IF NOT EXISTS idx_suggestions_box ON suggestions(box_id);
"""


def connect(db_path: Path | None = None) -> sqlite3.Connection:
    """Open (creating if needed) the Trinity database with schema applied."""
    path = db_path or DEFAULT_DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA)
    conn.commit()
    return conn

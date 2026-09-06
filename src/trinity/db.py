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
    mode TEXT DEFAULT 'educational',  -- 'educational' or 'professional' —
                                       -- governs explanation verbosity while
                                       -- working and which report template
                                       -- runs at the end. Both modes log to
                                       -- the same timeline; mode is a lens
                                       -- over one dataset, not a fork of it.
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- Engagement front matter, used by professional-mode reports (and
-- optionally shown in educational mode too). One row per box; all
-- fields optional since educational/CTF use rarely needs them filled.
CREATE TABLE IF NOT EXISTS engagement_meta (
    box_id INTEGER PRIMARY KEY REFERENCES boxes(id),
    client_name TEXT,
    scope TEXT,                       -- what's in/out of scope, in the
                                       -- operator's own words
    authorization_ref TEXT,           -- e.g. HTB/THM platform + username,
                                       -- or a signed engagement letter ref
    tester_name TEXT,
    start_date TEXT,
    end_date TEXT,
    notes TEXT
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
    severity TEXT,                    -- 'critical', 'high', 'medium', 'low',
                                       -- 'info' — heuristic unless sourced
                                       -- from a real CVSS feed (see
                                       -- trinity.kb.severity)
    cvss_score REAL,                  -- populated once a local CVE/CVSS feed
                                       -- is wired in; NULL until then
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

-- Every command Trinity has ever explained + its ELI5 explanation, cached
-- locally so the same flag combo never needs re-explaining (and never
-- costs a token twice). 'source' distinguishes pre-seeded/bulk-authored
-- entries (trinity_preseed) from ones an operator personally verified via
-- the escalation flow (ai_escalation) or hand-wrote (user_curated) — a
-- pre-seeded explanation not yet been checked against a live command is
-- worth trusting less than one an operator confirmed themselves.
CREATE TABLE IF NOT EXISTS command_explanations (
    id INTEGER PRIMARY KEY,
    command TEXT NOT NULL UNIQUE,     -- normalized command string
    explanation TEXT NOT NULL,        -- ELI5 explanation
    source TEXT DEFAULT 'ai_escalation',  -- 'trinity_preseed', 'ai_escalation', 'user_curated'
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

-- The chronological spine both report modes read from. Every notable
-- thing that happens on a box — a scan run, a finding matched, a command
-- suggested, an ELI5 explanation given, a manual note — gets one row
-- here, in order. Educational-mode reports narrate this timeline;
-- professional-mode reports group and re-format it. One shared log,
-- two different lenses at report time — never two separate code paths
-- collecting different data depending on mode.
CREATE TABLE IF NOT EXISTS timeline (
    id INTEGER PRIMARY KEY,
    box_id INTEGER NOT NULL REFERENCES boxes(id),
    ts TEXT DEFAULT CURRENT_TIMESTAMP,
    phase TEXT,                       -- 'recon', 'enum', 'foothold', 'privesc', 'post'
    event_type TEXT NOT NULL,         -- 'scan', 'finding', 'match', 'suggestion',
                                       -- 'explanation', 'note', 'milestone'
    summary TEXT NOT NULL,            -- one-line, human-readable
    detail TEXT,                      -- longer text if useful in the report
    severity TEXT,                    -- carried over from the KBMatch that
                                       -- produced this event, if any
    ref_id INTEGER,                   -- optional FK into findings/kb_entries/
                                       -- suggestions, loosely typed on purpose
                                       -- so one table serves every event kind
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_findings_box ON findings(box_id);
CREATE INDEX IF NOT EXISTS idx_findings_matched ON findings(matched);
CREATE INDEX IF NOT EXISTS idx_kb_service ON kb_entries(match_service);
CREATE INDEX IF NOT EXISTS idx_suggestions_box ON suggestions(box_id);
CREATE INDEX IF NOT EXISTS idx_timeline_box ON timeline(box_id, ts);
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

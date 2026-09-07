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
    shell_level TEXT,                 -- PROTOTYPE (1.6): NULL / 'user' / 'root'
                                       -- operator-declared foothold. Never
                                       -- inferred from shell history.
    difficulty TEXT,                  -- PROTOTYPE: NULL / 'easy' / 'medium' / 'hard'
                                       -- operator-supplied, public platform rating.
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
    notes TEXT,
    classification TEXT,              -- PROTOTYPE pro-mode: e.g. TLP:CLEAR
    report_version TEXT,              -- PROTOTYPE pro-mode: 0.1-draft
    distribution TEXT                 -- PROTOTYPE pro-mode: who may receive this
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
    rationale TEXT,                   -- why Trinity suggested this (full detail --
                                       -- may name the tool/technique; shown in
                                       -- `trinity next` and hint level 3)
    nudge TEXT,                       -- vaguer, tool-name-free version of the
                                       -- rationale, used ONLY by the graduated
                                       -- hint ladder's level 2 (hints.py) so it
                                       -- never leaks the answer early
    required_tool TEXT,               -- binary name this command needs (e.g.
                                       -- 'gobuster') -- checked against tools.py
                                       -- before the coach recommends this command
    finding_id INTEGER REFERENCES findings(id),  -- the specific finding this
                                       -- suggestion is tied to, so coach.py can
                                       -- look up ITS severity directly instead
                                       -- of regexing "Port N" out of rationale
                                       -- prose (which breaks the moment a
                                       -- suggestion isn't port-shaped, e.g.
                                       -- path/share/user findings)
    accepted INTEGER DEFAULT 0,       -- 1 once the operator has done (or
                                       -- deliberately skipped) this suggestion
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

-- Tiny machine-local key/value store for the onboarding wizard: has
-- setup run before, and which box was last active (so 'trinity' with
-- no arguments can offer 'resume' instead of re-asking everything).
-- Deliberately not box-scoped data -- this is CLI/session state, not
-- anything a report would ever read from.
CREATE TABLE IF NOT EXISTS local_state (
    key TEXT PRIMARY KEY,
    value TEXT
);

-- Instructor Mode: tracks how far up the graduated hint ladder each
-- suggestion has climbed (1 = nudge, 2 = stronger nudge, 3 = full
-- answer). One row per (box, suggestion) -- a fresh suggestion always
-- starts back at level 1, never inherits escalation from an unrelated
-- earlier one. See docs/INSTRUCTOR_MODE.md.
CREATE TABLE IF NOT EXISTS hint_state (
    box_id INTEGER NOT NULL REFERENCES boxes(id),
    suggestion_id INTEGER NOT NULL REFERENCES suggestions(id),
    level INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (box_id, suggestion_id)
);

-- Instructor Mode: known error text -> cause + fix, the same
-- "pay the AI cost once, cache forever" shape as command_explanations,
-- but at "why didn't this work" granularity instead of "what does this
-- command mean". See docs/INSTRUCTOR_MODE.md.
CREATE TABLE IF NOT EXISTS error_patterns (
    id INTEGER PRIMARY KEY,
    error_text TEXT NOT NULL,         -- the error snippet/description matched on
    cause TEXT NOT NULL,               -- plain-English explanation of why it happens
    fix TEXT NOT NULL,                 -- the confirmed-working remedy
    source TEXT DEFAULT 'ai_escalation',  -- 'trinity_preseed', 'ai_escalation', 'user_curated'
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE VIRTUAL TABLE IF NOT EXISTS error_patterns_fts USING fts5(
    error_text, cause, fix,
    content='error_patterns', content_rowid='id'
);

CREATE TRIGGER IF NOT EXISTS error_patterns_ai AFTER INSERT ON error_patterns BEGIN
    INSERT INTO error_patterns_fts(rowid, error_text, cause, fix)
    VALUES (new.id, new.error_text, new.cause, new.fix);
END;
CREATE TRIGGER IF NOT EXISTS error_patterns_ad AFTER DELETE ON error_patterns BEGIN
    INSERT INTO error_patterns_fts(error_patterns_fts, rowid, error_text, cause, fix)
    VALUES ('delete', old.id, old.error_text, old.cause, old.fix);
END;
CREATE TRIGGER IF NOT EXISTS error_patterns_au AFTER UPDATE ON error_patterns BEGIN
    INSERT INTO error_patterns_fts(error_patterns_fts, rowid, error_text, cause, fix)
    VALUES ('delete', old.id, old.error_text, old.cause, old.fix);
    INSERT INTO error_patterns_fts(rowid, error_text, cause, fix)
    VALUES (new.id, new.error_text, new.cause, new.fix);
END;

CREATE INDEX IF NOT EXISTS idx_hint_state_box ON hint_state(box_id);

-- PROTOTYPE (loot tracker): creds/hashes/tokens/flags the operator
-- found. Timeline also gets an event_type='loot' row so reports can
-- narrate it chronologically. See trinity.loot and FEATURES_BACKLOG.md.
CREATE TABLE IF NOT EXISTS loot (
    id INTEGER PRIMARY KEY,
    box_id INTEGER NOT NULL REFERENCES boxes(id),
    kind TEXT NOT NULL,               -- 'credential', 'hash', 'token', 'flag', 'other'
    value TEXT NOT NULL,
    note TEXT,
    discovered_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_loot_box ON loot(box_id);

-- PROTOTYPE (curiosity unlocks, 2.1): per-box take/decline state for
-- local pedagogy cards. Card bodies live in unlocks.py, not here.
CREATE TABLE IF NOT EXISTS unlock_state (
    box_id INTEGER NOT NULL REFERENCES boxes(id),
    card_id TEXT NOT NULL,
    status TEXT NOT NULL,             -- 'taken' / 'declined'
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (box_id, card_id)
);

-- Update Framework (docs/UPDATE_FRAMEWORK.md): staging area for any
-- knowledge Trinity's own install generates (Agent Harness answers,
-- live-drafted Methods Index entries, etc.) that has NOT been vetted
-- by anyone but this one operator's one session. Nothing here is ever
-- read by trinity next/explain/error/the coach -- only approved
-- records that have been copied into their real destination table
-- (command_explanations/error_patterns/kb_entries/methods_index/*.yaml)
-- are live. This is a staging area in front of already-existing write
-- paths, not a new trust boundary of its own. See
-- docs/UPDATE_FRAMEWORK.md, "Part 2: the intake/review pipeline".
CREATE TABLE IF NOT EXISTS intake_candidates (
    id INTEGER PRIMARY KEY,
    kind TEXT NOT NULL,                -- 'explanation' | 'error_pattern' |
                                        -- 'kb_entry' | 'method'
    payload TEXT NOT NULL,             -- JSON blob shaped like the target
                                        -- table's row (command/explanation,
                                        -- error_text/cause/fix, etc.)
    source TEXT NOT NULL,              -- 'agent_harness' | 'methods_live_draft'
    box_id INTEGER REFERENCES boxes(id),  -- NULL if not session-scoped
    status TEXT NOT NULL DEFAULT 'pending',  -- 'pending' | 'approved' | 'rejected'
    reviewer_note TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    reviewed_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_intake_status ON intake_candidates(status);

-- Update Framework: last-synced timestamps per external data source
-- (GTFOBins, ExploitDB, PayloadsAllTheThings, ...), so the silent
-- auto-sync on launch can rate-limit itself instead of re-pulling on
-- every single command invocation. Its own small table rather than
-- overloading local_state's single-key/value shape with a growing
-- family of sync-timestamp keys. See docs/UPDATE_FRAMEWORK.md, "Part 1".
CREATE TABLE IF NOT EXISTS sync_state (
    source TEXT PRIMARY KEY,           -- 'gtfobins' | 'exploitdb' | ...
    last_synced_at TEXT,
    last_status TEXT,                  -- 'ok' | 'failed' | 'skipped'
    detail TEXT                        -- e.g. an error message on failure
);
"""


# Columns added to `suggestions` after its original CREATE TABLE shipped.
# `CREATE TABLE IF NOT EXISTS` does NOT retroactively add columns to an
# already-existing table file -- an operator's real ~/.trinity/trinity.db
# from before this column existed would otherwise blow up on the first
# INSERT/SELECT that touches it. Additive-only, never destructive; each
# tuple is (column_name, column_ddl_suffix).
_SUGGESTIONS_ADDITIVE_COLUMNS = [
    ("nudge", "TEXT"),
    ("required_tool", "TEXT"),
    ("finding_id", "INTEGER REFERENCES findings(id)"),
]

# PROTOTYPE columns on boxes. Same CREATE TABLE IF NOT EXISTS trap.
_BOXES_ADDITIVE_COLUMNS = [
    ("shell_level", "TEXT"),
    ("difficulty", "TEXT"),
]

_ENGAGEMENT_ADDITIVE_COLUMNS = [
    ("classification", "TEXT"),
    ("report_version", "TEXT"),
    ("distribution", "TEXT"),
]


def _ensure_additive_columns(conn: sqlite3.Connection) -> None:
    """Adds any columns newer than a table's original schema to an
    existing on-disk database, without touching data. In-memory test
    databases are always created fresh from the current SCHEMA string
    (see conftest.py), so this is a no-op for them -- it only matters
    for a real, previously-created ~/.trinity/trinity.db."""
    existing = {row["name"] for row in conn.execute("PRAGMA table_info(suggestions)").fetchall()}
    for column, ddl in _SUGGESTIONS_ADDITIVE_COLUMNS:
        if column not in existing:
            conn.execute(f"ALTER TABLE suggestions ADD COLUMN {column} {ddl}")

    box_cols = {row["name"] for row in conn.execute("PRAGMA table_info(boxes)").fetchall()}
    for column, ddl in _BOXES_ADDITIVE_COLUMNS:
        if column not in box_cols:
            conn.execute(f"ALTER TABLE boxes ADD COLUMN {column} {ddl}")

    eng_tables = {
        row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }
    if "engagement_meta" in eng_tables:
        eng_cols = {row["name"] for row in conn.execute("PRAGMA table_info(engagement_meta)").fetchall()}
        for column, ddl in _ENGAGEMENT_ADDITIVE_COLUMNS:
            if column not in eng_cols:
                conn.execute(f"ALTER TABLE engagement_meta ADD COLUMN {column} {ddl}")
    conn.commit()


def _seed_brain(conn: sqlite3.Connection) -> None:
    """Loads the KB, ELI5 explanation cache, and error-pattern library --
    the three things a brand-new install needs to be useful on the very
    first `trinity next`/`trinity explain`/`trinity error` call. Called
    from connect() (every real invocation), not just `trinity init`, so
    the wizard's happy path never hands someone an empty brain (see
    docs/CLAUDE_CURSOR_DEBATE.md, Hole B). All three seed functions are
    idempotent (INSERT-if-not-exists), so calling this on every connect()
    is cheap and never duplicates or overwrites a user's own entries."""
    from trinity.errors_seed import seed_error_patterns
    from trinity.explain_seed.combine import seed_all as seed_all_explanations
    from trinity.kb.seed import seed as seed_kb

    seed_kb(conn)
    seed_all_explanations(conn)
    seed_error_patterns(conn)


def connect(db_path: Path | None = None, *, seed_brain: bool = True) -> sqlite3.Connection:
    """Open (creating if needed) the Trinity database with schema applied.

    seed_brain=True (the default, used by every real CLI command) also
    auto-seeds the KB/explain/error libraries and ensures additive
    columns exist -- see _seed_brain and _ensure_additive_columns above.
    Tests pass seed_brain=False (or bypass connect() entirely in favor
    of the in-memory `conn` fixture) to keep unit tests fast and to let
    a few tests exercise a genuinely-empty DB on purpose."""
    path = db_path or DEFAULT_DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA)
    conn.commit()
    _ensure_additive_columns(conn)
    if seed_brain:
        _seed_brain(conn)
    return conn

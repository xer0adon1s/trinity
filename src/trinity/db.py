"""Trinity's local database: schema + connection management.

SQLite with FTS5 (full-text search) for the local knowledge base — no
external services, no network calls. Everything Trinity knows lives here.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

DEFAULT_DB_PATH = Path.home() / ".trinity" / "trinity.db"

# Sources a command_explanations/error_patterns row can carry.
# 'ai_escalation' is the direct-write-path default (see explain.py's
# save_explanation, errors.py's save_error_fix); the other three arrive
# via intake.py's approve_candidate(), which preserves the candidate's
# real provenance instead of flattening everything to 'ai_escalation'.
# These two names are the single definition of that vocabulary:
# intake.VALID_SOURCES is INTAKE_SOURCES, and sharing.py's share-export
# filter selects on AI_SOURCED. Adding a new intake source here (and
# only here) keeps the two halves from drifting apart -- when they did
# drift, approved harness/assimilator entries silently vanished from
# every share bundle.
# frozen on purpose: intake.VALID_SOURCES is an ALIAS of INTAKE_SOURCES,
# so a stray VALID_SOURCES.add(...) would mutate the vocabulary in place
# while AI_SOURCED -- built once, here, at import time -- stayed stale.
# That is the Fix 1 drift in miniature; frozenset makes it a TypeError at
# the call site instead of a silently-shrinking share bundle.
INTAKE_SOURCES = frozenset({"agent_harness", "methods_live_draft", "assimilator"})
AI_SOURCED = INTAKE_SOURCES | {"ai_escalation"}

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
-- costs a token twice). 'source' records provenance: pre-seeded/bulk-
-- authored entries (trinity_preseed) and hand-written ones (user_curated)
-- sit alongside the AI-sourced ones (ai_escalation from the direct
-- explain -> cache flow, plus agent_harness / methods_live_draft /
-- assimilator arriving via intake.py's approve_candidate) — a pre-seeded
-- explanation not yet checked against a live command is worth trusting
-- less than one an operator confirmed themselves. See AI_SOURCED below
-- for the set share-export treats as AI-sourced.
CREATE TABLE IF NOT EXISTS command_explanations (
    id INTEGER PRIMARY KEY,
    command TEXT NOT NULL UNIQUE,     -- normalized command string
    explanation TEXT NOT NULL,        -- ELI5 explanation
    source TEXT DEFAULT 'ai_escalation',  -- 'trinity_preseed' | 'user_curated' |
                                           -- any of AI_SOURCED (see below)
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
    source TEXT DEFAULT 'ai_escalation',  -- 'trinity_preseed' | 'user_curated' |
                                           -- any of AI_SOURCED (see below)
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

-- Assimilator's leverage ledger (docs/ASSIMILATOR_PROJECT.md §7). One
-- row per diagnose/hypothesize/verify attempt, from EITHER trigger:
-- 'offline' (Doc's batch sweep of the Coverage Sim corpus) or 'live'
-- (a student's `trinity show-me` invocation against a real box, see
-- docs/SHOW_ME_MODE.md). Both triggers are the same engine -- this is
-- one shared table, not two. `others_lifted` (not a `self`-inclusive
-- count) is the real leverage signal: how many OTHER boxes/situations
-- a fix also resolved, so a fix's own trivial self-fix doesn't get
-- counted as multiplier value.
CREATE TABLE IF NOT EXISTS assimilator_runs (
    id INTEGER PRIMARY KEY,
    trigger TEXT NOT NULL,              -- 'offline' | 'live'
    box_id INTEGER REFERENCES boxes(id),   -- NULL for offline corpus runs not tied to a live box
    box_name TEXT,                      -- corpus box name for offline runs (fixture-based, no box_id)
    trinity_commit TEXT,                -- git SHA this diagnosis/verification ran against
    primary_cause TEXT NOT NULL,        -- see docs/ASSIMILATOR_PROJECT.md §3 taxonomy
    secondary_causes TEXT,              -- JSON list
    fix_shape TEXT,                     -- kb_content|routing_rule|suggest_rule|parser|fixture|
                                         -- sync_policy|match_policy|new_subsystem|none
    hypothesis TEXT,                    -- what fix/approach was proposed
    verification_method TEXT,           -- 'fixture_replay' | 'live_target'
    verification_evidence TEXT,         -- path to transcript/log
    result TEXT NOT NULL,               -- 'verified_fix' | 'rejected_hypothesis' |
                                         -- 'escalated_capability_gap' | 'needs_policy_decision' |
                                         -- 'already_known' (see already_known_hits below)
    intake_candidate_id INTEGER REFERENCES intake_candidates(id),
    self_lifted INTEGER NOT NULL DEFAULT 0,   -- 0/1: did this fix resolve its own box/situation
    others_lifted TEXT,                  -- JSON list of other box/situation names also resolved
    boxes_regressed TEXT,                -- JSON list; must be empty at land time
    new_false_positives TEXT,            -- JSON list -- still-passing boxes made noisier
    already_known_hit INTEGER NOT NULL DEFAULT 0,  -- 0/1: see already_known_hits table --
                                                    -- set when the "solution" already existed
                                                    -- in the KB and the operator/engine just
                                                    -- missed routing to it
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    finished_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_assimilator_runs_box ON assimilator_runs(box_id);
CREATE INDEX IF NOT EXISTS idx_assimilator_runs_trigger ON assimilator_runs(trigger);

-- Show Me Mode's authoritative disclosure record (docs/SHOW_ME_MODE.md
-- §7). Independent of whether any individual timeline row survives --
-- this is the record report rendering checks to decide whether the
-- mandatory AI-assistance disclosure block must appear at all. Never
-- suppressible: report/data.py's gather_report_data() populates
-- ai_assisted_steps from this table whenever any row exists for the
-- box, and neither report renderer has a code path that omits it.
CREATE TABLE IF NOT EXISTS show_me_runs (
    id INTEGER PRIMARY KEY,
    box_id INTEGER NOT NULL REFERENCES boxes(id),
    milestone TEXT NOT NULL,            -- 'foothold' | 'privesc_to_user' | 'privesc_to_root'
    agent_used TEXT,                    -- which agent CLI actually ran it (hermes/claude/codex/...)
    outcome TEXT NOT NULL,              -- 'succeeded' | 'aborted' | 'failed' | 'already_known'
    commands_run TEXT,                  -- JSON list of the actual argv executed
    recipe_for_student TEXT,            -- the exact command sequence handed back for the
                                         -- student to run themselves (NULL if outcome != succeeded)
    assimilator_run_id INTEGER REFERENCES assimilator_runs(id),
    started_at TEXT DEFAULT CURRENT_TIMESTAMP,
    finished_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_show_me_runs_box ON show_me_runs(box_id);

-- Authorization attestation for Show Me Mode (docs/SHOW_ME_MODE.md §4,
-- docs/OPEN_DECISIONS.md's "Auto-run scans or exploits" entry). A
-- one-time, logged acknowledgment -- same legal shape as any pentest
-- tool's terms-of-use checkbox, NOT a hardcoded per-box target
-- allowlist (explicitly rejected, see that OPEN_DECISIONS entry).
CREATE TABLE IF NOT EXISTS show_me_attestation (
    id INTEGER PRIMARY KEY CHECK (id = 1),  -- single row, machine-wide
    accepted_at TEXT NOT NULL
);

-- Trinity's Voice v1 (docs/TRINITY_VOICE_DESIGN.md): a hand-authored
-- corpus of plain-English teaching text, one row per kb_entries.title
-- (NOT kb_entries.id -- id is an autoincrement, unstable across a
-- fresh install/re-seed; title is the stable, human-authored key
-- kb/seed.py already treats as unique). Deliberately NOT AI-generated
-- live -- see the design doc's "why this isn't live generation" for
-- the two independent reviews that led to this being an authored
-- corpus + deterministic renderer rather than a cache of AI output.
CREATE TABLE IF NOT EXISTS finding_explanations (
    id INTEGER PRIMARY KEY,
    kb_title TEXT NOT NULL UNIQUE,     -- joins to kb_entries.title
    what_it_is TEXT NOT NULL,          -- paragraph 1: what this is
    why_it_happens TEXT NOT NULL,      -- paragraph 2: the mechanism/story
    what_to_watch_for TEXT NOT NULL,   -- paragraph 3: the generalizable lesson
    source TEXT NOT NULL DEFAULT 'trinity_preseed',  -- reserved for
    -- when v2 (live generation) lands: distinguishes reviewed corpus
    -- rows from generated-cache rows so the two trust levels never
    -- silently mix. Not read anywhere yet in v1 -- only trinity_preseed
    -- rows exist -- but written now so v2 doesn't need a migration to
    -- add a column that should have been there from the start.
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
"""


# Columns added to a table after its original CREATE TABLE shipped.
# `CREATE TABLE IF NOT EXISTS` does NOT retroactively add columns to an
# already-existing table file -- an operator's real ~/.trinity/trinity.db
# from before a column existed would otherwise blow up on the first
# INSERT/SELECT that touches it. Additive-only, never destructive; each
# tuple is (column_name, column_ddl_suffix).
#
# EVERY table in SCHEMA belongs here, including ones with nothing to
# migrate yet -- an empty list is the registration that makes the first
# future column on that table Just Work. This used to be three
# hand-copied PRAGMA blocks, which is precisely why the three tables
# added later (assimilator_runs, show_me_runs, show_me_attestation) had
# no entry at all: the first column ever added to one of them would have
# silently no-op'd on every installed database. Add the table here the
# moment you add it to SCHEMA, not the moment you first need to migrate
# it -- test_db_migration.py's registry-coverage test fails the build if
# you forget.
_ADDITIVE_COLUMNS: dict[str, list[tuple[str, str]]] = {
    # Registered in SCHEMA order. An empty list means "nothing has been
    # added since this table shipped", NOT "this table is exempt".
    # (The 6 extra Assimilator fields in docs/ASSIMILATOR_PROJECT.md §7
    # are real feature scope tied to Show Me Mode's rebuild, and are
    # deliberately NOT pre-added here.)
    "boxes": [
        # PROTOTYPE columns on boxes.
        ("shell_level", "TEXT"),
        ("difficulty", "TEXT"),
    ],
    "engagement_meta": [
        ("classification", "TEXT"),
        ("report_version", "TEXT"),
        ("distribution", "TEXT"),
    ],
    "findings": [],
    "kb_entries": [],
    "command_explanations": [],
    "suggestions": [
        ("nudge", "TEXT"),
        ("required_tool", "TEXT"),
        ("finding_id", "INTEGER REFERENCES findings(id)"),
    ],
    "timeline": [],
    "local_state": [],
    "hint_state": [],
    "error_patterns": [],
    "loot": [],
    "unlock_state": [],
    "intake_candidates": [],
    "sync_state": [],
    "assimilator_runs": [],
    "show_me_runs": [],
    "show_me_attestation": [],
    "finding_explanations": [],
}


def _ensure_additive_columns(conn: sqlite3.Connection) -> None:
    """Adds any columns newer than a table's original schema to an
    existing on-disk database, without touching data. In-memory test
    databases are always created fresh from the current SCHEMA string
    (see conftest.py), so this is a no-op for them -- it only matters
    for a real, previously-created ~/.trinity/trinity.db."""
    for table, columns in _ADDITIVE_COLUMNS.items():
        # The existence guard is uniform across every registered table:
        # a database file old enough to predate the whole table must
        # migrate cleanly rather than raising here. (SCHEMA's CREATE
        # TABLE IF NOT EXISTS, run just before this in connect(), then
        # creates it at its current definition -- with no columns to
        # back-fill.)
        exists = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
        ).fetchone()
        if not exists:
            continue
        existing = {row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
        for column, ddl in columns:
            if column not in existing:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")
    conn.commit()


def _seed_brain(conn: sqlite3.Connection) -> None:
    """Loads the KB, ELI5 explanation cache, error-pattern library, and
    Trinity's Voice teaching corpus -- what a brand-new install needs
    to be useful on the very first `trinity next`/`trinity explain`/
    `trinity error`/`trinity watch` call. Called from connect() (every
    real invocation), not just `trinity init`, so the wizard's happy
    path never hands someone an empty brain (see
    docs/CLAUDE_CURSOR_DEBATE.md, Hole B). All four seed functions are
    idempotent (INSERT-if-not-exists), so calling this on every connect()
    is cheap and never duplicates or overwrites a user's own entries."""
    from trinity.errors_seed import seed_error_patterns
    from trinity.explain_seed.combine import seed_all as seed_all_explanations
    from trinity.kb.ad_seed import seed as seed_ad
    from trinity.kb.seed import seed as seed_kb
    from trinity.voice import seed_voice_entries

    seed_kb(conn)
    seed_ad(conn)
    seed_all_explanations(conn)
    seed_error_patterns(conn)
    seed_voice_entries(conn)


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

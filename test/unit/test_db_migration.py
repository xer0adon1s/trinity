"""On-disk schema shims: additive columns and auto-seed on connect()."""
from __future__ import annotations

import sqlite3

from trinity.db import connect


_OLD_SUGGESTIONS = """
CREATE TABLE boxes (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    target TEXT,
    platform TEXT,
    status TEXT DEFAULT 'active',
    mode TEXT DEFAULT 'educational'
);
CREATE TABLE suggestions (
    id INTEGER PRIMARY KEY,
    box_id INTEGER NOT NULL REFERENCES boxes(id),
    phase TEXT,
    command TEXT NOT NULL,
    rationale TEXT,
    accepted INTEGER DEFAULT 0
);
"""


def test_connect_adds_missing_suggestion_columns(tmp_path):
    path = tmp_path / "old.db"
    raw = sqlite3.connect(path)
    raw.executescript(_OLD_SUGGESTIONS)
    raw.commit()
    raw.close()

    conn = connect(path, seed_brain=False)
    names = {row["name"] for row in conn.execute("PRAGMA table_info(suggestions)")}
    assert {"nudge", "required_tool", "finding_id"} <= names
    conn.execute(
        "INSERT INTO boxes (name) VALUES ('LegacyBox')"
    )
    box_id = conn.execute("SELECT id FROM boxes WHERE name = 'LegacyBox'").fetchone()[0]
    conn.execute(
        "INSERT INTO suggestions (box_id, phase, command, rationale, nudge, required_tool) "
        "VALUES (?, 'enum', 'ftp $TARGET', 'why', 'nudge', 'ftp')",
        (box_id,),
    )
    conn.commit()
    row = conn.execute("SELECT nudge, required_tool FROM suggestions").fetchone()
    assert row["nudge"] == "nudge"
    assert row["required_tool"] == "ftp"


def test_connect_seeds_brain_on_a_fresh_file(tmp_path):
    conn = connect(tmp_path / "fresh.db", seed_brain=True)
    assert conn.execute("SELECT count(*) AS n FROM kb_entries").fetchone()["n"] > 0
    assert conn.execute("SELECT count(*) AS n FROM command_explanations").fetchone()["n"] > 0
    assert conn.execute("SELECT count(*) AS n FROM error_patterns").fetchone()["n"] > 0

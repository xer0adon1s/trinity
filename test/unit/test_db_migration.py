"""On-disk schema shims: additive columns and auto-seed on connect()."""
from __future__ import annotations

import sqlite3

import pytest

from trinity.db import SCHEMA, _ADDITIVE_COLUMNS, _ensure_additive_columns, connect


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
    box_cols = {row["name"] for row in conn.execute("PRAGMA table_info(boxes)")}
    assert {"shell_level", "difficulty"} <= box_cols
    tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"loot", "unlock_state"} <= tables
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


# --- the additive-column registry -------------------------------------
#
# `_ensure_additive_columns` used to be three hand-copied PRAGMA blocks,
# so every table added since (assimilator_runs, show_me_runs,
# show_me_attestation) had no entry at all and the first column ever
# added to one of them would have silently no-op'd on every existing
# installed database. These tests pin the registry itself: that every
# table in it really does get migrated, and that a table missing from an
# old database file is skipped rather than blowing up.

_OLD_ENGAGEMENT_META = """
CREATE TABLE boxes (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL
);
CREATE TABLE engagement_meta (
    box_id INTEGER PRIMARY KEY REFERENCES boxes(id),
    client_name TEXT,
    scope TEXT,
    authorization_ref TEXT,
    tester_name TEXT,
    start_date TEXT,
    end_date TEXT,
    notes TEXT
);
"""


@pytest.mark.parametrize("table", sorted(_ADDITIVE_COLUMNS))
def test_registry_migrates_every_registered_table(table, tmp_path, monkeypatch):
    # Covers all six registered tables from one body, including the
    # three whose real column list is (correctly) still empty: a probe
    # column is injected into the registry, so this asserts the
    # MECHANISM reaches the table, not that any particular column
    # exists yet.
    path = tmp_path / f"{table}_probe.db"
    raw = sqlite3.connect(path)
    raw.executescript(SCHEMA)
    raw.commit()
    raw.close()

    monkeypatch.setitem(
        _ADDITIVE_COLUMNS, table, [*_ADDITIVE_COLUMNS[table], ("_migration_probe", "TEXT")]
    )
    conn = connect(path, seed_brain=False)
    names = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}
    assert "_migration_probe" in names


@pytest.mark.skipif(
    sqlite3.sqlite_version_info < (3, 35, 0), reason="ALTER TABLE DROP COLUMN needs SQLite 3.35+"
)
@pytest.mark.parametrize(
    "table", sorted(t for t, cols in _ADDITIVE_COLUMNS.items() if cols)
)
def test_registry_restores_real_columns_dropped_from_an_old_db(table, tmp_path):
    # The same check against the registry's REAL data: strip every
    # registered column back off a current-schema database (i.e. make it
    # look like the older file it was before those columns shipped),
    # then connect() and assert they all come back.
    path = tmp_path / f"{table}_old.db"
    raw = sqlite3.connect(path)
    raw.executescript(SCHEMA)
    expected = {column for column, _ddl in _ADDITIVE_COLUMNS[table]}
    for column in expected:
        raw.execute(f"ALTER TABLE {table} DROP COLUMN {column}")
    raw.commit()
    present = {row[1] for row in raw.execute(f"PRAGMA table_info({table})")}
    assert not (expected & present), "old-schema fixture should be missing the columns"
    raw.close()

    conn = connect(path, seed_brain=False)
    names = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}
    assert expected <= names


def test_connect_adds_missing_engagement_meta_columns(tmp_path):
    # engagement_meta was the one table the old mechanism guarded with a
    # sqlite_master existence check, but nothing tested it.
    path = tmp_path / "old_engagement.db"
    raw = sqlite3.connect(path)
    raw.executescript(_OLD_ENGAGEMENT_META)
    raw.commit()
    raw.close()

    conn = connect(path, seed_brain=False)
    names = {row["name"] for row in conn.execute("PRAGMA table_info(engagement_meta)")}
    assert {"classification", "report_version", "distribution"} <= names


def test_migration_skips_tables_absent_from_an_old_db(tmp_path):
    # The existence guard, now applied uniformly to all six tables: a
    # database file predating a whole table must migrate cleanly rather
    # than raising on `PRAGMA table_info` of a table that isn't there.
    path = tmp_path / "no_such_tables.db"
    raw = sqlite3.connect(path)
    raw.executescript("CREATE TABLE boxes (id INTEGER PRIMARY KEY, name TEXT NOT NULL);")
    raw.commit()
    raw.close()

    missing = {"assimilator_runs", "show_me_runs", "engagement_meta"}
    _ensure_additive_columns(sqlite3.connect(path))  # must not raise on a bare file

    conn = connect(path, seed_brain=False)  # SCHEMA then creates them for real
    tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert missing <= tables

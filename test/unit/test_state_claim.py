"""Regression coverage for the "triple popup" bug: multiple Trinity
processes racing the same one-time-ever setup gate (notify opt-in,
first run) against the shared ~/.trinity/trinity.db, all reading the
gate as unset before any of them commits, and all acting on it --
concretely, all firing send_test_notification(), producing 2-3 stacked
desktop notifications instead of one.

state.claim_state() is the fix: a raw INSERT (not set_state's upsert)
against local_state's PRIMARY KEY only ever succeeds for one caller.
These tests exercise claim_state() directly against a real on-disk
DB shared by two connections (simulating two concurrent `trinity`
invocations against the same worktree's DB), and confirm the wizard's
notify gate only ever sends one test notification even when "raced".
"""
from __future__ import annotations

import sqlite3
from unittest.mock import patch

from trinity.db import SCHEMA
from trinity.state import NOTIFY_ENABLED, claim_state, get_state


def _file_conn(path):
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.executescript(SCHEMA)
    connection.commit()
    return connection


def test_claim_state_only_one_winner_across_two_connections(tmp_path):
    db_path = tmp_path / "trinity.db"
    conn_a = _file_conn(db_path)
    conn_b = _file_conn(db_path)

    # Simulates two `trinity` processes (e.g. two agent terminals)
    # starting up against the same shared DB at nearly the same time.
    won_a = claim_state(conn_a, "_notify_setup_claim")
    won_b = claim_state(conn_b, "_notify_setup_claim")

    assert won_a is True
    assert won_b is False


def test_claim_state_repeated_calls_only_win_once(conn):
    assert claim_state(conn, "_notify_setup_claim") is True
    assert claim_state(conn, "_notify_setup_claim") is False
    assert claim_state(conn, "_notify_setup_claim") is False


def test_run_intro_race_sends_exactly_one_test_notification(tmp_path):
    """The concrete bug: three near-simultaneous run_intro() calls
    (three agent terminals all doing first-run setup against the same
    shared DB) must only ever fire ONE test notification, not three."""
    from trinity.wizard import run_intro

    db_path = tmp_path / "trinity.db"
    conns = [_file_conn(db_path) for _ in range(3)]

    with patch("trinity.wizard.Confirm.ask", return_value=True), \
         patch("trinity.wizard.Prompt.ask", return_value=""), \
         patch("trinity.notify.send_test_notification", return_value=True) as mock_send:
        for c in conns:
            run_intro(c)

    assert mock_send.call_count == 1
    # And the setting itself landed exactly once, consistently.
    assert get_state(conns[0], NOTIFY_ENABLED) == "1"

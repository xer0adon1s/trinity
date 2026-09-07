"""Tests for the Update Framework's sync scheduler (update_sync.py)."""
from __future__ import annotations

from datetime import timedelta

from trinity.update_sync import (
    get_sync_status,
    is_sync_due,
    record_sync_result,
    run_sync_if_due,
)


def test_sync_is_due_when_never_synced(conn):
    assert is_sync_due(conn, "gtfobins") is True


def test_sync_not_due_right_after_a_recorded_success(conn):
    record_sync_result(conn, "gtfobins", ok=True)
    assert is_sync_due(conn, "gtfobins") is False


def test_sync_due_again_after_min_interval_elapses(conn):
    record_sync_result(conn, "gtfobins", ok=True)
    # A zero-length interval means "always due again immediately".
    assert is_sync_due(conn, "gtfobins", min_interval=timedelta(seconds=0)) is True


def test_run_sync_if_due_calls_the_function_when_due(conn):
    calls = []
    run_sync_if_due(conn, "gtfobins", lambda: calls.append(1))
    assert calls == [1]
    status = get_sync_status(conn, "gtfobins")
    assert status["last_status"] == "ok"


def test_run_sync_if_due_skips_when_not_due(conn):
    record_sync_result(conn, "gtfobins", ok=True)
    calls = []
    ran = run_sync_if_due(conn, "gtfobins", lambda: calls.append(1))
    assert ran is False
    assert calls == []


def test_run_sync_if_due_records_failure_without_raising(conn):
    def boom():
        raise RuntimeError("network unreachable")

    ran = run_sync_if_due(conn, "gtfobins", boom)
    assert ran is True  # attempted
    status = get_sync_status(conn, "gtfobins")
    assert status["last_status"] == "failed"
    assert "network unreachable" in status["detail"]


def test_different_sources_track_independently(conn):
    record_sync_result(conn, "gtfobins", ok=True)
    assert is_sync_due(conn, "exploitdb") is True
    assert is_sync_due(conn, "gtfobins") is False


def test_get_sync_status_none_when_never_synced(conn):
    assert get_sync_status(conn, "never-synced-source") is None

"""Tests for trinity.assimilator — the shared diagnose/verify/land
leverage ledger fed by both the offline sweep (future work) and the
live trigger (Show Me Mode, tested in test_show_me.py)."""
from __future__ import annotations

import pytest

from trinity.assimilator import (
    check_already_known,
    finish_run,
    leverage_summary,
    start_run,
)
from trinity.boxes import create_box


def test_start_run_rejects_invalid_trigger(conn):
    with pytest.raises(ValueError):
        start_run(conn, "sideways", "missing_kb_entry")


def test_start_run_rejects_invalid_primary_cause(conn):
    with pytest.raises(ValueError):
        start_run(conn, "live", "not_a_real_cause")


def test_start_and_finish_run_round_trip(conn):
    box = create_box(conn, "AssimBox", target="10.10.10.5")
    run_id = start_run(conn, "live", "capability_gap", box_id=box.id, hypothesis="try X")
    finish_run(conn, run_id, "verified_fix", self_lifted=True, others_lifted=["otherbox"])

    row = conn.execute("SELECT * FROM assimilator_runs WHERE id = ?", (run_id,)).fetchone()
    assert row["result"] == "verified_fix"
    assert row["self_lifted"] == 1
    assert "otherbox" in row["others_lifted"]
    assert row["finished_at"] is not None


def test_finish_run_rejects_invalid_result(conn):
    run_id = start_run(conn, "offline", "missing_kb_entry", box_name="lame")
    with pytest.raises(ValueError):
        finish_run(conn, run_id, "not_a_real_result")


def test_check_already_known_finds_confirmed_kb_hit(seeded_conn):
    # vsftpd 2.3.4 is the seeded confirmed backdoor entry (see test_match_engine.py).
    hit = check_already_known(seeded_conn, service="ftp", product="vsftpd", version="2.3.4")
    assert hit is not None
    assert "backdoor" in hit.title.lower()


def test_check_already_known_returns_none_for_unknown_service(seeded_conn):
    hit = check_already_known(seeded_conn, service="totally-unknown-svc-xyz", product=None, version=None)
    assert hit is None


def test_leverage_summary_counts_already_known_hits_separately(conn):
    box = create_box(conn, "LeverageBox", target="10.10.10.6")
    r1 = start_run(conn, "live", "capability_gap", box_id=box.id)
    finish_run(conn, r1, "already_known", already_known_hit=True, self_lifted=True)
    r2 = start_run(conn, "live", "missing_kb_entry", box_id=box.id)
    finish_run(conn, r2, "verified_fix", self_lifted=True, others_lifted=["a", "b"])

    summary = leverage_summary(conn)
    assert summary.total_runs == 2
    assert summary.verified_fixes == 1
    assert summary.already_known_hits == 1
    assert summary.others_lifted_total == 2

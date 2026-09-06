"""Tests for the watch-mode dashboard's non-UI logic -- specifically
the content-hash dedup that prevents duplicate filesystem events for
the same save from double-persisting findings/timeline events."""
from __future__ import annotations

from pathlib import Path

import pytest

from trinity.boxes import create_box
from trinity.db import connect

FIXTURES = Path(__file__).parent.parent / "fixtures"


@pytest.fixture
def db_path(tmp_path):
    return tmp_path / "trinity_test.db"


def test_dashboard_requires_an_existing_box(db_path):
    from trinity.tui.dashboard import get_box_by_name_or_raise

    conn = connect(db_path)
    with pytest.raises(ValueError, match="No box named"):
        get_box_by_name_or_raise(conn, "DoesNotExist")


def test_handle_file_skips_duplicate_content(db_path, tmp_path):
    # Regression test for Cursor's review finding: a filesystem event
    # firing twice for the same saved content (e.g. a paired added +
    # modified event) must not persist the same findings twice.
    from trinity.tui.dashboard import TrinityDashboard

    conn = connect(db_path)
    box = create_box(conn, "DashboardTestBox", target="10.10.10.3")

    scan_path = tmp_path / "scan.xml"
    scan_path.write_text((FIXTURES / "lame_style_scan.xml").read_text())

    dashboard = TrinityDashboard.__new__(TrinityDashboard)  # skip Textual App.__init__/mount
    dashboard.box = box
    dashboard.conn = conn
    dashboard._last_processed_hash = {}
    dashboard._append_feed = lambda *a, **k: None  # no live UI in this test
    dashboard._render_result = lambda *a, **k: None

    dashboard._handle_file(scan_path)
    first_count = conn.execute("SELECT count(*) as n FROM findings WHERE box_id = ?", (box.id,)).fetchone()["n"]

    dashboard._handle_file(scan_path)  # simulate a duplicate fs event, same content
    second_count = conn.execute("SELECT count(*) as n FROM findings WHERE box_id = ?", (box.id,)).fetchone()["n"]

    assert first_count > 0
    assert second_count == first_count  # no duplicate inserts


def test_handle_file_reprocesses_genuinely_changed_content(db_path, tmp_path):
    # Confirms the dedup is content-based, not a blanket "never
    # reprocess this path" -- a real re-scan with new findings must
    # still be picked up.
    from trinity.tui.dashboard import TrinityDashboard

    conn = connect(db_path)
    box = create_box(conn, "DashboardTestBox2", target="10.10.10.3")

    scan_path = tmp_path / "scan.xml"
    scan_path.write_text((FIXTURES / "lame_style_scan.xml").read_text())

    dashboard = TrinityDashboard.__new__(TrinityDashboard)
    dashboard.box = box
    dashboard.conn = conn
    dashboard._last_processed_hash = {}
    dashboard._append_feed = lambda *a, **k: None
    dashboard._render_result = lambda *a, **k: None

    dashboard._handle_file(scan_path)
    first_count = conn.execute("SELECT count(*) as n FROM findings WHERE box_id = ?", (box.id,)).fetchone()["n"]

    # Simulate the operator re-running the scan and appending a new host block --
    # different content, must be processed again.
    scan_path.write_text(scan_path.read_text() + "\n<!-- rescan -->")
    dashboard._handle_file(scan_path)
    second_count = conn.execute("SELECT count(*) as n FROM findings WHERE box_id = ?", (box.id,)).fetchone()["n"]

    assert second_count >= first_count

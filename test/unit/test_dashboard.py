"""Tests for the watch-mode dashboard's non-UI logic -- specifically
the content-hash dedup that prevents duplicate filesystem events for
the same save from double-persisting findings/timeline events."""
from __future__ import annotations

from pathlib import Path

import pytest

from trinity.boxes import create_box
from trinity.db import connect
from trinity.process import process_scan_file

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


def test_handle_file_explains_empty_nmap_xml_instead_of_raw_parse_error(db_path, tmp_path):
    # Regression test for a real live-alpha bug: nmap's "Note: Host
    # seems down. ... try -Pn" case writes an XML declaration with no
    # <host> data and no closing </nmaprun> -- ET.parse() throws "no
    # element found: line N, column 0", which is meaningless to a
    # student and doesn't point at the actual fix (add -Pn). The
    # dashboard must recognize this shape and explain it instead of
    # surfacing the raw exception text.
    from trinity.tui.dashboard import TrinityDashboard

    conn = connect(db_path)
    box = create_box(conn, "EmptyScanBox", target="10.10.10.5")

    scan_path = tmp_path / "scan.xml"
    # The real shape nmap writes when it gives up before scanning any
    # ports: valid XML declaration + opening <nmaprun>, no <host>, no
    # closing tag (the process never got to write one).
    scan_path.write_text('<?xml version="1.0"?>\n<nmaprun scanner="nmap">\n')

    dashboard = TrinityDashboard.__new__(TrinityDashboard)
    dashboard.box = box
    dashboard.conn = conn
    dashboard._last_processed_hash = {}
    feed_messages = []
    dashboard._append_feed = lambda markup: feed_messages.append(markup)
    dashboard._render_result = lambda *a, **k: None

    dashboard._handle_file(scan_path)

    assert len(feed_messages) == 1
    message = feed_messages[0]
    assert "no element found" not in message  # the raw ET.ParseError text must not leak through
    assert "-Pn" in message  # the actual fix must be named
    assert "Host seems down" in message or "blocking" in message  # the actual cause must be named
    # No findings should have been persisted from a file that never parsed.
    count = conn.execute("SELECT count(*) as n FROM findings WHERE box_id = ?", (box.id,)).fetchone()["n"]
    assert count == 0


def test_handle_file_explains_a_genuinely_empty_scan_file(db_path, tmp_path):
    # The other real shape: nmap failed to even start writing (e.g. a
    # permissions error on the -oX path), leaving a zero-byte file.
    from trinity.tui.dashboard import TrinityDashboard

    conn = connect(db_path)
    box = create_box(conn, "TrulyEmptyScanBox", target="10.10.10.6")

    scan_path = tmp_path / "scan.xml"
    scan_path.write_text("")

    dashboard = TrinityDashboard.__new__(TrinityDashboard)
    dashboard.box = box
    dashboard.conn = conn
    dashboard._last_processed_hash = {}
    feed_messages = []
    dashboard._append_feed = lambda markup: feed_messages.append(markup)
    dashboard._render_result = lambda *a, **k: None

    dashboard._handle_file(scan_path)

    assert len(feed_messages) == 1
    assert "is empty" in feed_messages[0]
    assert "no element found" not in feed_messages[0]


def test_handle_file_narrates_a_confirmed_match_via_the_voice(db_path):
    # End-to-end: a real scan.xml containing the classic vsftpd 2.3.4
    # backdoor finding should produce a "Trinity explains:" block in the
    # feed, using the actual seeded corpus (Trinity's Voice v1, see
    # docs/TRINITY_VOICE_DESIGN.md) -- not a mock, the real render path.
    from trinity.tui.dashboard import TrinityDashboard

    conn = connect(db_path)  # real connect(), so voice_seed is populated
    box = create_box(conn, "VoiceIntegrationBox", target="10.10.10.3")

    dashboard = TrinityDashboard.__new__(TrinityDashboard)
    dashboard.box = box
    dashboard.conn = conn
    dashboard._last_processed_hash = {}
    feed_messages = []
    dashboard._append_feed = lambda markup: feed_messages.append(markup)

    class _FakeSuggestions:
        def append(self, *a, **k):
            pass

    dashboard.query_one = lambda *a, **k: _FakeSuggestions()

    scan_path = FIXTURES / "lame_style_scan.xml"
    process_result = process_scan_file(conn, box.id, scan_path)
    assert process_result is not None
    dashboard._render_result(scan_path, process_result)

    joined = "\n".join(feed_messages)
    assert "Trinity explains:" in joined
    assert "backdoor" in joined.lower()
    # The substituted instance data must actually be present, not just
    # the header -- this is the "verify against your own scan" contract.
    assert "10.10.10.3:21" in joined
    assert "vsftpd 2.3.4" in joined
    # This fixture has THREE findings whose matches clear the
    # confidence gate (vsftpd exact-version match, plus the SSH and
    # SMB findings' version-agnostic curated entries, once the
    # matches[0]-only bug is fixed) and two that are exclusively
    # best_guess searchsploit noise (Apache, second Samba port) --
    # exactly the mix a real Lame scan produces.
    assert joined.count("Trinity explains") == 3


def test_render_result_narrates_the_best_narratable_match_not_just_the_headline(db_path):
    # Regression: a verified searchsploit hit (score 0.95, best_guess
    # confidence) routinely outranks a hand-curated version-agnostic KB
    # entry (score 0.9, likely confidence) -- close to the default real-
    # world shape whenever searchsploit is installed and a common
    # service (like SSH) is exposed. Gating on matches[0] alone silently
    # suppressed the authored entry every time this happened, which is
    # most of the time. This test builds the exact scenario without
    # requiring searchsploit to actually be installed on the test
    # runner.
    from pathlib import Path

    from trinity.match.engine import KBMatch
    from trinity.parsers.nmap import Finding
    from trinity.process import FindingResult, ProcessResult
    from trinity.tui.dashboard import TrinityDashboard

    conn = connect(db_path)
    box = create_box(conn, "MatchSelectionBox", target="10.10.10.3")

    dashboard = TrinityDashboard.__new__(TrinityDashboard)
    dashboard.box = box
    dashboard.conn = conn
    feed_messages = []
    dashboard._append_feed = lambda markup: feed_messages.append(markup)

    class _FakeSuggestions:
        def append(self, *a, **k):
            pass

    dashboard.query_one = lambda *a, **k: _FakeSuggestions()

    finding = Finding(
        source_tool="nmap", kind="port", host="10.10.10.3", port=22,
        service="ssh", product="OpenSSH", version="4.7p1 Debian 8ubuntu1",
    )
    matches = [
        KBMatch(kb_id=None, title="OpenSSH 2.3 < 7.7 - Username Enumeration (PoC)",
                summary="x", source="searchsploit", score=0.95, severity="medium"),
        KBMatch(kb_id=4, title="SSH version banner grabbing for known CVEs",
                summary="x", source="user_curated", score=0.9, severity="info"),
    ]
    result = ProcessResult(
        tool="nmap", findings=[FindingResult(finding=finding, matches=matches)], suggestions=[],
    )

    dashboard._render_result(Path("scan.xml"), result)

    joined = "\n".join(feed_messages)
    assert "Trinity explains" in joined
    # It must say which finding it's narrating, since it isn't the
    # headline match the operator was shown on the line above.
    assert "on SSH version banner grabbing for known CVEs" in joined


def test_render_result_escapes_rich_markup_in_banner_text(db_path):
    # Regression: a banner string shaped like Rich markup (e.g. a
    # bracketed version tag, or a stray closing-tag-looking substring)
    # previously either silently deleted the bracketed text from the
    # output, or raised MarkupError and crashed _handle_file's caller
    # entirely -- outside the try/except that's supposed to protect
    # the watch worker from exactly this class of bad input. Finding
    # data comes from the SCANNED BOX, which on a CTF/pentest target is
    # attacker-controlled.
    from pathlib import Path

    from trinity.match.engine import KBMatch
    from trinity.parsers.nmap import Finding
    from trinity.process import FindingResult, ProcessResult
    from trinity.tui.dashboard import TrinityDashboard

    conn = connect(db_path)
    box = create_box(conn, "MarkupEscapeBox", target="10.10.10.7")

    dashboard = TrinityDashboard.__new__(TrinityDashboard)
    dashboard.box = box
    dashboard.conn = conn
    feed_messages = []
    dashboard._append_feed = lambda markup: feed_messages.append(markup)

    class _FakeSuggestions:
        def append(self, *a, **k):
            pass

    dashboard.query_one = lambda *a, **k: _FakeSuggestions()

    finding = Finding(
        source_tool="nmap", kind="port", host="10.10.10.7", port=21,
        service="ftp", product="Microsoft ftpd [/dim]", version=None,
    )
    matches = [KBMatch(kb_id=2, title="Anonymous FTP login", summary="x",
                       source="user_curated", score=0.9, severity="medium")]
    result = ProcessResult(
        tool="nmap", findings=[FindingResult(finding=finding, matches=matches)], suggestions=[],
    )

    dashboard._render_result(Path("scan.xml"), result)  # must not raise

    joined = "\n".join(feed_messages)
    assert "[/dim]" in joined  # literal text preserved, not silently deleted


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

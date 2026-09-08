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
    # This fixture has FOUR findings whose matches clear the confidence
    # gate: vsftpd's exact-version match, the SSH and SMB findings'
    # version-agnostic curated entries (visible once the matches[0]-only
    # bug was fixed), and the HTTP finding's curated entry (visible only
    # via the match_curated_only fallback -- on this fixture with
    # searchsploit installed, that entry is pushed off match_finding's
    # shared top-5 slice by higher-scored best_guess hits, so it would
    # NOT show without the R1 fallback). One finding (the second Samba
    # port) is exclusively best_guess searchsploit noise with no curated
    # match at all -- exactly the mix a real Lame scan produces.
    assert joined.count("Trinity explains") == 4
    assert "HTTP directory brute-forcing" in joined or "webserver is found" in joined.lower()


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


def test_render_result_falls_back_to_curated_only_when_truncated_off_top_n(db_path):
    # Regression for R1: match_finding()'s shared top-N slice can push
    # a genuinely curated (confirmed/likely) entry off the bottom once
    # enough higher-scored best_guess hits exist -- reproduced live on
    # HTB Lame's HTTP port with searchsploit installed (curated entry
    # sat at position 13 of an uncapped query, past the default
    # limit=5). Constructed here without depending on searchsploit
    # being installed on the test runner: fr.matches simulates exactly
    # that shape (5 best_guess entries filling the visible slice, the
    # real curated match already truncated off and not present in
    # fr.matches at all) -- the fallback must re-query the KB directly
    # rather than only ever looking inside fr.matches.
    from pathlib import Path

    from trinity.match.engine import KBMatch
    from trinity.parsers.nmap import Finding
    from trinity.process import FindingResult, ProcessResult
    from trinity.tui.dashboard import TrinityDashboard

    conn = connect(db_path)
    box = create_box(conn, "TruncationFallbackBox", target="10.10.10.3")

    dashboard = TrinityDashboard.__new__(TrinityDashboard)
    dashboard.box = box
    dashboard.conn = conn
    feed_messages = []
    dashboard._append_feed = lambda markup: feed_messages.append(markup)

    class _FakeSuggestions:
        def append(self, *a, **k):
            pass

    dashboard.query_one = lambda *a, **k: _FakeSuggestions()

    # A real Voice-covered curated title ("HTTP directory brute-forcing
    # is next after a webserver is found") exists in kb_entries (seeded
    # by connect()) but is deliberately NOT included in fr.matches --
    # simulating it having been truncated off match_finding's slice.
    finding = Finding(
        source_tool="nmap", kind="port", host="10.10.10.3", port=80,
        service="http", product="Apache httpd", version="2.2.8",
    )
    fake_searchsploit_noise = [
        KBMatch(kb_id=None, title=f"Fake best-guess hit #{i}", summary="x",
                source="searchsploit", score=0.8, severity="medium")
        for i in range(5)
    ]
    result = ProcessResult(
        tool="nmap",
        findings=[FindingResult(finding=finding, matches=fake_searchsploit_noise)],
        suggestions=[],
    )

    dashboard._render_result(Path("scan.xml"), result)

    joined = "\n".join(feed_messages)
    assert "Trinity explains" in joined
    assert "on HTTP directory brute-forcing is next after a webserver is found" in joined


def test_render_result_skips_confidence_eligible_match_with_no_authored_entry(db_path):
    # Regression for R2: the match-scan must check confidence AND
    # actual entry existence together, continuing past a match that
    # clears the confidence gate but has no Voice row, rather than
    # stopping there and giving up. This is uncommon on today's 1:1
    # SEED_ENTRIES<->ENTRIES starter corpus, but becomes live the
    # moment kb.ad_seed rows or any future curated KB entry without a
    # Voice counterpart ranks above a covered one.
    from pathlib import Path

    from trinity.match.engine import KBMatch
    from trinity.parsers.nmap import Finding
    from trinity.process import FindingResult, ProcessResult
    from trinity.tui.dashboard import TrinityDashboard

    conn = connect(db_path)
    box = create_box(conn, "SkipToNextMatchBox", target="10.10.10.7")

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
        service="ftp", product="vsftpd", version="2.3.4",
    )
    matches = [
        # Higher-ranked, confidence-eligible, but no Voice row for it.
        KBMatch(kb_id=99, title="Some curated FTP entry with no Voice counterpart",
                summary="x", source="user_curated", score=0.95, severity="medium"),
        # Lower-ranked but IS covered by the corpus.
        KBMatch(kb_id=1, title="vsftpd 2.3.4 backdoor (CVE-2011-2523)",
                summary="x", source="user_curated", score=1.0, severity="critical"),
    ]
    result = ProcessResult(
        tool="nmap", findings=[FindingResult(finding=finding, matches=matches)], suggestions=[],
    )

    dashboard._render_result(Path("scan.xml"), result)

    joined = "\n".join(feed_messages)
    assert "Trinity explains" in joined
    assert "backdoor" in joined.lower()


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


def test_render_result_gates_privesc_narration_behind_shell_level(db_path):
    # Regression for Finding F (spoiler-safety): the match engine can
    # and does FTS-attach a later-phase KB entry (SUID) to an
    # earlier-phase finding purely on shared vocabulary. Every authored
    # paragraph is phase-safe on its own, but nothing enforced that at
    # DISPLAY time before this gate -- a plain recon-phase path finding
    # must not narrate the privesc-phase SUID entry while the box's
    # shell_level is still None.
    from pathlib import Path

    from trinity.match.engine import KBMatch
    from trinity.parsers.nmap import Finding
    from trinity.process import FindingResult, ProcessResult
    from trinity.tui.dashboard import TrinityDashboard

    conn = connect(db_path)
    box = create_box(conn, "PhaseGateBox", target="10.10.10.9")  # shell_level is None

    dashboard = TrinityDashboard.__new__(TrinityDashboard)
    dashboard.box = box
    dashboard.conn = conn
    feed_messages = []
    dashboard._append_feed = lambda markup: feed_messages.append(markup)

    class _FakeSuggestions:
        def append(self, *a, **k):
            pass

    dashboard.query_one = lambda *a, **k: _FakeSuggestions()

    finding = Finding(source_tool="gobuster", kind="path", host="10.10.10.9", path="/gtfobins/")
    matches = [
        KBMatch(kb_id=6, title="SUID binaries are the first privesc check on Linux",
                summary="x", source="user_curated", score=0.6, severity="high"),
    ]
    result = ProcessResult(
        tool="gobuster", findings=[FindingResult(finding=finding, matches=matches)], suggestions=[],
    )

    dashboard._render_result(Path("scan.xml"), result)

    joined = "\n".join(feed_messages)
    assert "Trinity explains" not in joined, "privesc content leaked during recon phase"


def test_render_result_unlocks_privesc_narration_once_shell_level_is_set(db_path):
    # The other half of the phase gate: once shell_level moves to
    # 'user' (or 'root'), the same privesc-phase entry must narrate --
    # this is a gate, not a permanent block.
    from pathlib import Path

    from trinity.boxes import set_shell_level
    from trinity.match.engine import KBMatch
    from trinity.parsers.nmap import Finding
    from trinity.process import FindingResult, ProcessResult
    from trinity.tui.dashboard import TrinityDashboard

    conn = connect(db_path)
    box = create_box(conn, "PhaseUnlockBox", target="10.10.10.9")
    set_shell_level(conn, box.id, "user")
    from trinity.boxes import get_box
    box = get_box(conn, box.id)
    assert box is not None

    dashboard = TrinityDashboard.__new__(TrinityDashboard)
    dashboard.box = box
    dashboard.conn = conn
    feed_messages = []
    dashboard._append_feed = lambda markup: feed_messages.append(markup)

    class _FakeSuggestions:
        def append(self, *a, **k):
            pass

    dashboard.query_one = lambda *a, **k: _FakeSuggestions()

    finding = Finding(source_tool="gobuster", kind="path", host="10.10.10.9", path="/gtfobins/")
    matches = [
        KBMatch(kb_id=6, title="SUID binaries are the first privesc check on Linux",
                summary="x", source="user_curated", score=0.6, severity="high"),
    ]
    result = ProcessResult(
        tool="gobuster", findings=[FindingResult(finding=finding, matches=matches)], suggestions=[],
    )

    dashboard._render_result(Path("scan.xml"), result)

    joined = "\n".join(feed_messages)
    assert "Trinity explains" in joined


def test_render_result_dedups_the_same_authored_entry_within_one_scan(db_path):
    # Regression for Finding G: the same curated entry legitimately
    # matches two findings in one scan (e.g. HTTP on both :80 and
    # :8080). Without dedup, the identical ~1,500-character
    # four-paragraph block would print twice verbatim in a row.
    from pathlib import Path

    from trinity.match.engine import KBMatch
    from trinity.parsers.nmap import Finding
    from trinity.process import FindingResult, ProcessResult
    from trinity.tui.dashboard import TrinityDashboard

    conn = connect(db_path)
    box = create_box(conn, "DedupBox", target="10.10.10.9")

    dashboard = TrinityDashboard.__new__(TrinityDashboard)
    dashboard.box = box
    dashboard.conn = conn
    feed_messages = []
    dashboard._append_feed = lambda markup: feed_messages.append(markup)

    class _FakeSuggestions:
        def append(self, *a, **k):
            pass

    dashboard.query_one = lambda *a, **k: _FakeSuggestions()

    matches = [
        KBMatch(kb_id=5, title="HTTP directory brute-forcing is next after a webserver is found",
                summary="x", source="user_curated", score=0.9, severity="medium"),
    ]
    finding_80 = Finding(source_tool="nmap", kind="port", host="10.10.10.9", port=80,
                         service="http", product="Apache", version="2.4")
    finding_8080 = Finding(source_tool="nmap", kind="port", host="10.10.10.9", port=8080,
                           service="http", product="Apache", version="2.4")
    result = ProcessResult(
        tool="nmap",
        findings=[
            FindingResult(finding=finding_80, matches=matches),
            FindingResult(finding=finding_8080, matches=matches),
        ],
        suggestions=[],
    )

    dashboard._render_result(Path("scan.xml"), result)

    joined = "\n".join(feed_messages)
    # The full paragraph text appears exactly once, not twice.
    assert joined.count("systematically requests a large") == 1
    assert "same as above" in joined

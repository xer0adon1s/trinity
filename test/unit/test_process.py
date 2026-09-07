"""Tests for the shared scan-file processing pipeline (detection +
parsing + matching + persistence) used by both the CLI and watch-mode."""
from __future__ import annotations

from pathlib import Path

from trinity.boxes import create_box
from trinity.process import detect_and_parse, process_scan_file

FIXTURES = Path(__file__).parent.parent / "fixtures"


def test_detect_and_parse_recognizes_nmap_xml():
    result = detect_and_parse(FIXTURES / "lame_style_scan.xml")
    assert result is not None
    tool, findings = result
    assert tool == "nmap"
    assert len(findings) == 5


def test_detect_and_parse_recognizes_ffuf_json():
    result = detect_and_parse(FIXTURES / "ffuf_sample.json")
    assert result is not None
    tool, findings = result
    assert tool == "ffuf"
    assert len(findings) == 2


def test_detect_and_parse_recognizes_nikto_json():
    result = detect_and_parse(FIXTURES / "nikto_sample.json")
    assert result is not None
    tool, findings = result
    assert tool == "nikto"
    assert len(findings) == 2


def test_detect_and_parse_recognizes_enum4linux_ng_json():
    result = detect_and_parse(FIXTURES / "enum4linux_ng_sample.json")
    assert result is not None
    tool, findings = result
    assert tool == "enum4linux-ng"


def test_detect_and_parse_recognizes_whatweb_by_name(tmp_path):
    # whatweb output has no distinguishing top-level key, so detection
    # falls back to filename pattern -- verify that path.
    src = FIXTURES / "whatweb_sample.jsonl"
    dest = tmp_path / "whatweb_output.jsonl"
    dest.write_text(src.read_text())
    result = detect_and_parse(dest)
    assert result is not None
    tool, findings = result
    assert tool == "whatweb"


def test_detect_and_parse_recognizes_gobuster_by_name(tmp_path):
    src = FIXTURES / "gobuster_sample.txt"
    dest = tmp_path / "gobuster_admin.txt"
    dest.write_text(src.read_text())
    result = detect_and_parse(dest)
    assert result is not None
    tool, findings = result
    assert tool == "gobuster"


def test_detect_and_parse_recognizes_whatweb_json_extension(tmp_path):
    # Regression test: whatweb's OWN documented invocation is
    # `whatweb --log-json=out.json` -- a `.json`-suffixed file that is
    # actually JSON Lines content. This must be detected without
    # relying on the filename containing "whatweb".
    src = FIXTURES / "whatweb_sample.jsonl"
    dest = tmp_path / "whatweb.json"
    dest.write_text(src.read_text())
    result = detect_and_parse(dest)
    assert result is not None
    tool, findings = result
    assert tool == "whatweb"


def test_detect_and_parse_still_recognizes_ffuf_json_after_whatweb_fix(tmp_path):
    # Guards against the whatweb-first-branch fix accidentally
    # swallowing genuine single-JSON-document formats (ffuf/nikto/
    # enum4linux-ng all share the .json suffix).
    result = detect_and_parse(FIXTURES / "ffuf_sample.json")
    assert result is not None
    tool, _ = result
    assert tool == "ffuf"


def test_detect_and_parse_recognizes_unrecognized_dot_json_as_none(tmp_path):
    dest = tmp_path / "something.json"
    dest.write_text('{"totally": "unrelated", "shape": true}')
    assert detect_and_parse(dest) is None


def test_detect_and_parse_returns_none_for_unrecognized_file(tmp_path):
    dest = tmp_path / "notes.txt"
    dest.write_text("just some random notes, not scan output")
    assert detect_and_parse(dest) is None


def test_detect_and_parse_returns_none_for_malformed_json(tmp_path):
    dest = tmp_path / "broken.json"
    dest.write_text("{not valid json")
    assert detect_and_parse(dest) is None


def test_process_scan_file_persists_findings_and_returns_matches(conn):
    box = create_box(conn, "WatchBox", target="10.10.10.3")
    result = process_scan_file(conn, box.id, FIXTURES / "lame_style_scan.xml")

    assert result is not None
    assert result.tool == "nmap"
    assert len(result.findings) == 5

    stored = conn.execute("SELECT count(*) as n FROM findings WHERE box_id = ?", (box.id,)).fetchone()
    assert stored["n"] == 5

    # The vsftpd finding should have matched something (KB or searchsploit).
    vsftpd_result = next(fr for fr in result.findings if fr.finding.port == 21)
    assert len(vsftpd_result.matches) > 0


def test_process_scan_file_logs_timeline_events(conn):
    box = create_box(conn, "WatchBox2", target="10.10.10.3")
    process_scan_file(conn, box.id, FIXTURES / "lame_style_scan.xml")

    events = conn.execute(
        "SELECT event_type FROM timeline WHERE box_id = ?", (box.id,)
    ).fetchall()
    event_types = {e["event_type"] for e in events}
    assert "scan" in event_types
    assert "match" in event_types


def test_process_scan_file_returns_none_for_unrecognized_file(conn, tmp_path):
    box = create_box(conn, "WatchBox3")
    dest = tmp_path / "irrelevant.txt"
    dest.write_text("nothing useful here")
    assert process_scan_file(conn, box.id, dest) is None


def test_process_scan_file_generates_suggestions(conn):
    box = create_box(conn, "WatchBox4", target="10.10.10.3")
    result = process_scan_file(conn, box.id, FIXTURES / "lame_style_scan.xml")
    assert len(result.suggestions) > 0


def test_process_autorecon_results_persists_findings_and_matches(conn, tmp_path):
    from trinity.process import process_autorecon_results

    target_dir = tmp_path / "results" / "10.10.10.3"
    xml_dir = target_dir / "scans" / "xml"
    xml_dir.mkdir(parents=True)
    (xml_dir / "tcp_21_ftp_nmap.xml").write_text((FIXTURES / "lame_style_scan.xml").read_text())
    (target_dir / "scans" / "tcp_80_http_gobuster.txt").write_text(
        (FIXTURES / "gobuster_sample.txt").read_text()
    )
    # AutoRecon's own bookkeeping -- must not choke the walk.
    (target_dir / "scans" / "_commands.log").write_text("nmap ...\n")

    box = create_box(conn, "AutoReconBox", target="10.10.10.3")
    result, skipped = process_autorecon_results(conn, box.id, target_dir)

    assert result.tool == "autorecon"
    assert len(result.findings) == 9  # 5 nmap ports + 4 gobuster paths
    assert any("_commands.log" in note for note in skipped)

    stored = conn.execute("SELECT count(*) as n FROM findings WHERE box_id = ?", (box.id,)).fetchone()
    assert stored["n"] == 9

    vsftpd_result = next(fr for fr in result.findings if fr.finding.port == 21)
    assert len(vsftpd_result.matches) > 0


def test_process_autorecon_results_handles_empty_dir(conn, tmp_path):
    from trinity.process import process_autorecon_results

    box = create_box(conn, "EmptyAutoReconBox")
    empty_dir = tmp_path / "results" / "nothing"  # does not exist
    result, skipped = process_autorecon_results(conn, box.id, empty_dir)
    assert result.findings == []
    assert skipped  # explains why nothing was found, doesn't raise

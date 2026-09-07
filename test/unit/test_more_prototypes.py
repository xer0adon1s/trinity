from __future__ import annotations

from pathlib import Path

from trinity.achievements import evaluate
from trinity.boxes import create_box, set_status
from trinity.deadends import dead_end_line
from trinity.graduation import NUDGE_AFTER, autorecon_nudge
from trinity.gtfobins import lookup as gtf_lookup
from trinity.hashes import classify_hash
from trinity.loot import add_loot
from trinity.parsers.rustscan import parse_rustscan_text
from trinity.process import detect_and_parse
from trinity.report.data import gather_report_data
from trinity.report.render import render_report
from trinity.payloads import lookup as payload_lookup
from trinity.sharing import scrub_identifying
from trinity.stats import compute_stats


def test_stats_hidden_until_first_root(conn):
    create_box(conn, "A")
    stats = compute_stats(conn)
    assert stats.ready is False
    assert stats.rooted == 0


def test_stats_ready_after_root(conn):
    box = create_box(conn, "B")
    set_status(conn, box.id, "rooted")
    stats = compute_stats(conn)
    assert stats.ready is True
    assert stats.rooted == 1
    assert stats.streak >= 1


def test_hash_shapes():
    assert classify_hash("5f4dcc3b5aa765d61d8327deb882cf99").label == "md5 or NTLM (32-hex)"
    assert classify_hash("$2a$12$R9h/cIPz0gi.URNNX3kh2OPST9/PgUk.sbJiXDc2mN0g8iK0yEAJa").label == "bcrypt"
    assert classify_hash("eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0In0.dozjgNryP4J3jVmNHl0w5N_XgL0n3I9PlFUP0THsR8U").label == "JWT"
    assert classify_hash("????").label == "unknown"


def test_hash_shapes_sha1_and_sha256_and_crypt_variants():
    from trinity.hashes import classify_hash

    assert classify_hash("da39a3ee5e6b4b0d3255bfef95601890afd80709").label == "sha1 (hex)"
    assert classify_hash("e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855").label == "sha256 (hex)"
    assert classify_hash("$1$abcdefgh$dXc4L0EIkQqCJKtJk1RYT0").label == "md5crypt ($1$)"
    assert classify_hash("$6$somesalt$rest.of.a.sha512crypt.hash.string.here").label == "sha512crypt ($6$)"


def test_hash_shape_ntlm_and_md5_are_indistinguishable_by_design():
    # 32-hex is genuinely ambiguous between md5 and NTLM -- the
    # classifier says so explicitly rather than silently guessing one.
    guess = classify_hash("5f4dcc3b5aa765d61d8327deb882cf99")
    assert "NTLM" in guess.next_step
    assert "md5" in guess.next_step.lower()


def test_gtfobins_vim_cites_source():
    hit = gtf_lookup("vim")
    assert hit is not None
    assert "gtfobins.github.io" in hit.source_url
    assert gtf_lookup("not-a-bin") is None


def test_notebook_renderer_includes_loot(conn):
    box = create_box(conn, "NoteBox")
    add_loot(conn, box.id, "flag", "HTB{n}")
    data = gather_report_data(conn, box.id)
    text = render_report(data, "notebook")
    assert "HTB{n}" in text
    assert "Lab notebook" in text


def test_scrub_replaces_ipv4():
    assert "$TARGET" in scrub_identifying("nmap -sV 10.10.10.99")
    assert "10.10.10.99" not in scrub_identifying("nmap -sV 10.10.10.99")


def test_rustscan_parser_greppable_format(tmp_path):
    path = tmp_path / "rustscan.txt"
    path.write_text("10.10.10.3 -> [21,80]\n")
    findings = parse_rustscan_text(path)
    assert {f.port for f in findings} == {21, 80}
    assert all(f.host == "10.10.10.3" for f in findings)
    tool, parsed = detect_and_parse(path)
    assert tool == "rustscan"
    assert len(parsed) == 2


def test_rustscan_parser_streaming_discovered_format(tmp_path):
    path = tmp_path / "rustscan.txt"
    path.write_text(
        "Discovered open port 22/tcp on 10.10.10.3\n"
        "Discovered open port 80/tcp on 10.10.10.3\n"
    )
    findings = parse_rustscan_text(path)
    assert {f.port for f in findings} == {22, 80}
    tool, parsed = detect_and_parse(path)
    assert tool == "rustscan"
    assert len(parsed) == 2


def test_rustscan_parser_dedupes_across_both_formats(tmp_path):
    path = tmp_path / "rustscan.txt"
    path.write_text(
        "Discovered open port 22/tcp on 10.10.10.3\n"
        "10.10.10.3 -> [22,80]\n"
    )
    findings = parse_rustscan_text(path)
    assert {f.port for f in findings} == {22, 80}
    assert len(findings) == 2  # port 22 not duplicated


def test_rustscan_parser_ignores_unrelated_txt_content(tmp_path):
    # A plain notes file must not be misidentified as rustscan output.
    path = tmp_path / "notes.txt"
    path.write_text("Remember to check the admin panel later.\n")
    assert parse_rustscan_text(path) == []
    assert detect_and_parse(path) is None


def test_dead_end_smb():
    line = dead_end_line("enum4linux-ng -A $TARGET")
    assert "Park" in line or "empty" in line.lower() or "normal" in line.lower()


def test_dead_end_matches_are_case_insensitive_and_substring_based():
    from trinity.deadends import dead_end_line

    assert dead_end_line("SMBCLIENT -L //10.10.10.3") == dead_end_line("smbclient -L //10.10.10.3")


def test_dead_end_ftp_and_ssh_and_gobuster_and_nikto_have_distinct_lines():
    from trinity.deadends import dead_end_line

    ftp = dead_end_line("ftp $TARGET")
    ssh = dead_end_line("ssh user@$TARGET")
    gobuster = dead_end_line("gobuster dir -u $TARGET -w common.txt")
    nikto = dead_end_line("nikto -h $TARGET")
    lines = {ftp, ssh, gobuster, nikto}
    assert len(lines) == 4  # each keyword gets its own line, none collide


def test_dead_end_unknown_command_gets_generic_fallback_not_none():
    from trinity.deadends import dead_end_line

    line = dead_end_line("xyzzy-totally-unrecognized-tool $TARGET")
    assert line is not None
    assert "Park" in line or "skill" in line.lower()


def test_graduation_after_enough_gobusters(conn):
    box = create_box(conn, "Grad")
    for i in range(NUDGE_AFTER):
        conn.execute(
            "INSERT INTO suggestions (box_id, phase, command, rationale, accepted) "
            "VALUES (?, 'enum', ?, 'why', 1)",
            (box.id, f"gobuster dir -u http://x/{i}"),
        )
    conn.commit()
    assert autorecon_nudge(conn) is not None


def test_payloads_index_is_titles_plus_urls():
    hit = payload_lookup("lfi")
    assert hit is not None
    assert "github.com/swisskyrepo" in hit.source_url


def test_achievements_unlock_on_flag(conn):
    box = create_box(conn, "Ach")
    add_loot(conn, box.id, "flag", "FLAG")
    rows = {a.id: a.unlocked for a in evaluate(conn)}
    assert rows["first_flag"] is True
    assert rows["nmap_scan"] is False

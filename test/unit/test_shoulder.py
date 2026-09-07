"""Tests for Shoulder Mode's milestone detection (shoulder.py). Only
the pure-function half (scan_for_milestones/apply_milestones) is
tested here -- record_session() needs a real pty/terminal and is
covered by live verification instead, per docs/SHOULDER_MODE.md."""
from __future__ import annotations

from trinity.boxes import create_box, get_box
from trinity.shoulder import apply_milestones, scan_for_milestones


def test_no_milestone_in_plain_recon_output():
    text = "Starting Nmap 7.94 ( https://nmap.org )\nNmap scan report for 10.10.10.3\n"
    assert scan_for_milestones(text) == []


def test_detects_user_shell_via_id_output():
    text = "www-data@lame:/var/www/html$ id\nuid=33(www-data) gid=33(www-data) groups=33(www-data)\n"
    hits = scan_for_milestones(text)
    names = [h.name for h in hits]
    assert "shell_landed" in names
    hit = next(h for h in hits if h.name == "shell_landed")
    assert hit.shell_level == "user"
    assert hit.phase == "foothold"


def test_detects_root_via_uid0():
    text = "root@lame:~# id\nuid=0(root) gid=0(root) groups=0(root)\n"
    hits = scan_for_milestones(text)
    names = [h.name for h in hits]
    assert "root_landed" in names
    hit = next(h for h in hits if h.name == "root_landed")
    assert hit.shell_level == "root"
    assert hit.phase == "privesc"


def test_only_reports_root_when_both_user_and_root_present():
    # Specific-before-general: a transcript with both a low-priv shell
    # AND a later privesc escalation should not ALSO report the weaker
    # user-level milestone once root is detected on the same scan pass.
    text = (
        "www-data@lame:/var/www/html$ id\n"
        "uid=33(www-data) gid=33(www-data)\n"
        "root@lame:~# id\n"
        "uid=0(root) gid=0(root)\n"
    )
    hits = scan_for_milestones(text)
    levels = {h.shell_level for h in hits}
    assert "root" in levels
    assert "user" not in levels  # root supersedes user in the same scan


def test_powershell_prompt_detected_as_user_shell():
    text = "PS C:\\Users\\svc-account> whoami\nlame\\svc-account\n"
    hits = scan_for_milestones(text)
    assert any(h.name == "shell_landed" for h in hits)


def test_does_not_false_positive_on_the_word_root_in_prose():
    # An nmap/searchsploit banner mentioning "root" shouldn't trip
    # detection -- only real prompt/id-output shapes should.
    text = "vsftpd 2.3.4 - Backdoor Command Execution (gives root access if exploited)\n"
    assert scan_for_milestones(text) == []


def test_apply_milestones_logs_timeline_and_promotes_shell_level(conn):
    box = create_box(conn, "ShoulderBox")
    hits = scan_for_milestones("www-data@lame:/var/www/html$ id\nuid=33(www-data) gid=33(www-data)\n")
    applied = apply_milestones(conn, box.id, hits)
    assert len(applied) == 1

    updated = get_box(conn, box.id)
    assert updated.shell_level == "user"

    timeline_rows = conn.execute(
        "SELECT * FROM timeline WHERE box_id = ? AND event_type = 'shoulder_milestone'", (box.id,),
    ).fetchall()
    assert len(timeline_rows) == 1


def test_apply_milestones_never_downgrades_shell_level(conn):
    box = create_box(conn, "ShoulderBox2")
    root_hits = scan_for_milestones("root@lame:~# id\nuid=0(root) gid=0(root)\n")
    apply_milestones(conn, box.id, root_hits)
    assert get_box(conn, box.id).shell_level == "root"

    # A later scan that only shows a user-level shell should never
    # downgrade an already-root box.
    user_hits = scan_for_milestones("www-data@lame:/var/www/html$ id\nuid=33(www-data) gid=33(www-data)\n")
    apply_milestones(conn, box.id, user_hits)
    assert get_box(conn, box.id).shell_level == "root"


def test_apply_milestones_never_reapplies_the_same_milestone(conn):
    box = create_box(conn, "ShoulderBox3")
    text = "www-data@lame:/var/www/html$ id\nuid=33(www-data) gid=33(www-data)\n"
    first = apply_milestones(conn, box.id, scan_for_milestones(text))
    second = apply_milestones(conn, box.id, scan_for_milestones(text))
    assert len(first) == 1
    assert len(second) == 0  # already recorded, no duplicate timeline entry

    timeline_rows = conn.execute(
        "SELECT * FROM timeline WHERE box_id = ? AND event_type = 'shoulder_milestone'", (box.id,),
    ).fetchall()
    assert len(timeline_rows) == 1


def test_apply_milestones_on_unknown_box_returns_empty_without_raising(conn):
    hits = scan_for_milestones("root@lame:~# id\nuid=0(root) gid=0(root)\n")
    assert apply_milestones(conn, 999999, hits) == []

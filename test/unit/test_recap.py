"""Tests for trinity.recap — the non-gamified end-of-box summary."""
from __future__ import annotations

from trinity.boxes import create_box
from trinity.loot import add_loot
from trinity.recap import build_recap, render_recap
from trinity.timeline import log_event


def test_recap_on_fresh_box_has_no_phases_or_techniques(conn):
    box = create_box(conn, "FreshBox")
    recap = build_recap(conn, box.id)
    assert recap.phases == []
    assert recap.techniques == []
    assert recap.loot_count == 0
    assert recap.nudge_count == 0


def test_recap_collects_phases_and_techniques_from_timeline(conn):
    box = create_box(conn, "RecapBox")
    log_event(conn, box.id, "match", "10.10.10.5:21 matched: vsftpd 2.3.4 Backdoor",
              phase="recon", severity="critical")
    log_event(conn, box.id, "match", "10.10.10.5:80 matched: Apache directory listing",
              phase="enum", severity="low")
    recap = build_recap(conn, box.id)
    assert {p.phase for p in recap.phases} == {"recon", "enum"}
    assert "vsftpd 2.3.4 Backdoor" in recap.techniques
    assert "Apache directory listing" in recap.techniques


def test_recap_dedupes_repeated_technique_titles(conn):
    box = create_box(conn, "DedupeBox")
    for _ in range(3):
        log_event(conn, box.id, "match", "10.10.10.5:445 matched: SMB null session",
                  phase="enum", severity="medium")
    recap = build_recap(conn, box.id)
    assert recap.techniques.count("SMB null session") == 1


def test_recap_counts_loot_and_nudges(conn):
    box = create_box(conn, "StuckBox")
    add_loot(conn, box.id, "flag", "HTB{demo}")
    log_event(conn, box.id, "nudge", "you might be stuck on SMB", phase="enum")
    recap = build_recap(conn, box.id)
    assert recap.loot_count == 1
    assert recap.nudge_count == 1


def test_render_recap_mentions_stuck_moments_without_shaming(conn):
    box = create_box(conn, "GentleBox")
    log_event(conn, box.id, "nudge", "stuck signal", phase="enum")
    recap = build_recap(conn, box.id)
    text = render_recap(recap)
    assert "normal, not a black mark" in text


def test_render_recap_reflects_shell_level(conn):
    from trinity.milestones import record_shell

    box = create_box(conn, "RootedBox")
    record_shell(conn, box.id, "root")
    recap = build_recap(conn, box.id)
    text = render_recap(recap)
    assert "rooted" in text.lower()

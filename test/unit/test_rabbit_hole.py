from __future__ import annotations

from trinity.boxes import create_box
from trinity.frustration import ENCOURAGEMENT, checkpoint_text
from trinity.rabbit_hole import detect_rabbit_hole, log_nudge, recent_nudge_count
from trinity.timeline import log_event


def _suggest(conn, box_id, command, phase="enum"):
    conn.execute(
        "INSERT INTO suggestions (box_id, phase, command, rationale, nudge) VALUES (?, ?, ?, 'why', 'nudge')",
        (box_id, phase, command),
    )
    conn.commit()


def test_stalled_progress_after_old_finding(conn):
    box = create_box(conn, "HoleBox")
    conn.execute(
        "INSERT INTO timeline (box_id, ts, event_type, summary) VALUES (?, '2020-01-01 00:00:00', 'finding', 'old')",
        (box.id,),
    )
    conn.execute(
        "INSERT INTO timeline (box_id, ts, event_type, summary) VALUES (?, '2020-01-01 01:00:00', 'note', 'later')",
        (box.id,),
    )
    _suggest(conn, box.id, "gobuster dir -u http://$TARGET")
    _suggest(conn, box.id, "enum4linux-ng -A $TARGET")
    signal = detect_rabbit_hole(conn, box.id, finding_gap_minutes=20)
    assert signal is not None
    assert signal.kind == "stalled_progress"
    assert signal.alternative_command


def test_hint_ladder_signal(conn):
    box = create_box(conn, "HintHole")
    _suggest(conn, box.id, "ftp $TARGET")
    sid = conn.execute("SELECT id FROM suggestions").fetchone()[0]
    conn.execute(
        "INSERT INTO hint_state (box_id, suggestion_id, level) VALUES (?, ?, 3)",
        (box.id, sid),
    )
    conn.execute(
        "INSERT INTO suggestions (box_id, phase, command, rationale, nudge) VALUES (?, 'enum', 'other', 'why', 'nudge')",
        (box.id,),
    )
    conn.execute(
        "INSERT INTO hint_state (box_id, suggestion_id, level) VALUES (?, ?, 3)",
        (box.id, sid + 1),
    )
    conn.commit()
    signal = detect_rabbit_hole(conn, box.id, finding_gap_minutes=9999)
    assert signal is not None
    assert signal.kind == "hint_ladder"


def test_fresh_box_is_not_a_rabbit_hole(conn):
    box = create_box(conn, "FreshHole")
    _suggest(conn, box.id, "nmap -sC -sV")
    assert detect_rabbit_hole(conn, box.id) is None


def test_nudge_logging_and_frustration(conn):
    box = create_box(conn, "Frust")
    _suggest(conn, box.id, "cmd")
    conn.execute(
        "INSERT INTO timeline (box_id, ts, event_type, summary) VALUES (?, '2020-01-01 00:00:00', 'finding', 'old')",
        (box.id,),
    )
    conn.execute(
        "INSERT INTO timeline (box_id, ts, event_type, summary) VALUES (?, '2020-01-01 02:00:00', 'note', 'later')",
        (box.id,),
    )
    conn.commit()
    signal = detect_rabbit_hole(conn, box.id, finding_gap_minutes=10)
    assert signal
    assert checkpoint_text(0) is None
    log_nudge(conn, box.id, signal)
    assert recent_nudge_count(conn, box.id) == 1
    assert ENCOURAGEMENT in (checkpoint_text(1) or "")

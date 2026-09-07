"""Tests for the advisory-priority-slot arbitration system
(advisories.py) -- the root-cause fix for `next`'s output-stacking
problem, replacing a flat character cap with real prioritized
selection: only ONE advisory ever wins, everything else is deferred."""
from __future__ import annotations

from unittest.mock import patch

from trinity.advisories import Advisory, pick_advisory
from trinity.boxes import create_box


def test_no_advisory_when_nothing_has_anything_to_say(conn):
    box = create_box(conn, "AdvisoryQuietBox")
    assert pick_advisory(conn, box) is None


def test_difficulty_advisory_fires_for_hard_only(conn):
    easy = create_box(conn, "EasyBox", difficulty="easy")
    hard = create_box(conn, "HardBox", difficulty="hard")
    assert pick_advisory(conn, easy) is None
    result = pick_advisory(conn, hard)
    assert result is not None
    assert result.kind == "difficulty"


def test_rabbit_hole_outranks_unlock_when_both_present(conn):
    box = create_box(conn, "BothBox", target="10.10.10.3")
    box.shell_level = "user"  # not persisted, just for the mock path below

    rabbit_advisory = Advisory(kind="rabbit_hole", priority=0, sentence="stuck signal")
    unlock_advisory = Advisory(kind="unlock", priority=30, sentence="curiosity card")

    with patch(
        "trinity.advisories.PROVIDERS",
        [lambda c, b: rabbit_advisory, lambda c, b: unlock_advisory, lambda c, b: None, lambda c, b: None],
    ):
        winner = pick_advisory(conn, box)

    assert winner is not None
    assert winner.kind == "rabbit_hole"  # priority 0 beats priority 30


def test_only_one_advisory_is_ever_returned_never_a_list(conn):
    box = create_box(conn, "OnlyOneBox")

    all_four = [
        Advisory(kind="rabbit_hole", priority=0, sentence="a"),
        Advisory(kind="unlock", priority=30, sentence="b"),
        Advisory(kind="difficulty", priority=40, sentence="c"),
        Advisory(kind="autorecon", priority=50, sentence="d"),
    ]

    with patch(
        "trinity.advisories.PROVIDERS",
        [lambda c, b, a=a: a for a in all_four],
    ):
        winner = pick_advisory(conn, box)

    assert winner is not None
    assert winner.kind == "rabbit_hole"  # only the single highest-priority one


def test_lower_priority_advisory_wins_when_it_is_the_only_one(conn):
    box = create_box(conn, "OnlyLowBox")

    autorecon_only = Advisory(kind="autorecon", priority=50, sentence="autorecon nudge")

    with patch(
        "trinity.advisories.PROVIDERS",
        [lambda c, b: None, lambda c, b: None, lambda c, b: None, lambda c, b: autorecon_only],
    ):
        winner = pick_advisory(conn, box)

    assert winner is not None
    assert winner.kind == "autorecon"


def test_autorecon_advisory_silent_in_professional_mode(conn):
    box = create_box(conn, "ProAutorecon", mode="professional")
    for _ in range(5):
        conn.execute(
            "INSERT INTO suggestions (box_id, phase, command, rationale, accepted) "
            "VALUES (?, 'enum', 'gobuster dir -u http://x -w y', 'why', 1)",
            (box.id,),
        )
    conn.commit()
    from trinity.advisories import _autorecon_advisory
    assert _autorecon_advisory(conn, box) is None


def test_unlock_advisory_names_the_real_box_in_its_sentence(conn):
    box = create_box(conn, "NamedBox")
    from trinity.advisories import _unlock_advisory
    from trinity.unlocks import UnlockCard

    fake_card = UnlockCard(id="after_user_shell", trigger="user", title="t", body="b")
    with patch("trinity.unlocks.peek_card", return_value=fake_card):
        result = _unlock_advisory(conn, box)
    assert result is not None
    assert "NamedBox" in result.sentence

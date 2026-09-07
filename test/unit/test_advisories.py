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


def _insert_completed_gobuster(conn, box_id: int, count: int) -> None:
    for _ in range(count):
        conn.execute(
            "INSERT INTO suggestions (box_id, phase, command, rationale, accepted) "
            "VALUES (?, 'enum', 'gobuster dir -u http://x -w y', 'why', 1)",
            (box_id,),
        )
    conn.commit()


def test_autorecon_advisory_only_fires_once_per_box(conn):
    box = create_box(conn, "OnceOnlyBox")
    _insert_completed_gobuster(conn, box.id, 3)

    first = pick_advisory(conn, box)
    assert first is not None
    assert first.kind == "autorecon"

    second = pick_advisory(conn, box)
    assert second is None  # already shown once, never fires again for this box


def test_autorecon_advisory_stays_eligible_if_outranked_by_a_higher_priority_advisory(conn):
    box = create_box(conn, "DeferredBox")
    _insert_completed_gobuster(conn, box.id, 3)

    rabbit_advisory = Advisory(kind="rabbit_hole", priority=0, sentence="stuck signal")
    from trinity.advisories import _autorecon_advisory

    with patch(
        "trinity.advisories.PROVIDERS",
        [lambda c, b: rabbit_advisory, lambda c, b: None, lambda c, b: None, _autorecon_advisory],
    ):
        first = pick_advisory(conn, box)
    assert first is not None
    assert first.kind == "rabbit_hole"  # outranked the autorecon nudge

    # AutoRecon's nudge was eligible but never actually shown -- it
    # must still be eligible on a later call, not silently burned.
    with patch(
        "trinity.advisories.PROVIDERS",
        [lambda c, b: None, lambda c, b: None, lambda c, b: None, _autorecon_advisory],
    ):
        second = pick_advisory(conn, box)
    assert second is not None
    assert second.kind == "autorecon"


def test_autorecon_advisory_is_scoped_per_box_not_global(conn):
    box_a = create_box(conn, "ScopeBoxA")
    box_b = create_box(conn, "ScopeBoxB")
    _insert_completed_gobuster(conn, box_a.id, 3)
    # box_b has NO completed gobuster suggestions of its own.

    from trinity.advisories import _autorecon_advisory
    assert _autorecon_advisory(conn, box_a) is not None
    assert _autorecon_advisory(conn, box_b) is None


def _make_stuck(conn, box_id: int) -> None:
    """Produces a real stalled_progress rabbit-hole signal: an old
    finding followed by a much later timeline event, same shape as
    test_rabbit_hole.py's test_stalled_progress_after_old_finding."""
    conn.execute(
        "INSERT INTO suggestions (box_id, phase, command, rationale, nudge) "
        "VALUES (?, 'enum', 'gobuster dir -u http://$TARGET', 'why', 'nudge')",
        (box_id,),
    )
    conn.execute(
        "INSERT INTO timeline (box_id, ts, event_type, summary) "
        "VALUES (?, '2020-01-01 00:00:00', 'finding', 'old')",
        (box_id,),
    )
    conn.execute(
        "INSERT INTO timeline (box_id, ts, event_type, summary) "
        "VALUES (?, '2020-01-01 01:00:00', 'note', 'later')",
        (box_id,),
    )
    conn.commit()


def test_rabbit_hole_offers_methods_index_when_box_is_indexed(conn):
    box = create_box(conn, "Lame")  # matches methods_index/lame.yaml (case-insensitive)
    _make_stuck(conn, box.id)

    from trinity.advisories import _rabbit_hole_advisory
    advisory = _rabbit_hole_advisory(conn, box)

    assert advisory is not None
    assert advisory.offers_methods_index is True
    assert "trinity methods" in advisory.sentence
    assert "Lame" in advisory.sentence
    # Never the content itself -- just the offer + the command to run.
    assert "CVE" not in advisory.sentence
    assert "0xdf" not in advisory.sentence


def test_rabbit_hole_does_not_offer_methods_index_for_unindexed_box(conn):
    box = create_box(conn, "TotallyUnindexedBoxName")
    _make_stuck(conn, box.id)

    from trinity.advisories import _rabbit_hole_advisory
    advisory = _rabbit_hole_advisory(conn, box)

    assert advisory is not None
    assert advisory.offers_methods_index is False
    assert "trinity methods" not in advisory.sentence


def test_methods_index_offer_fires_once_per_episode(conn):
    box = create_box(conn, "Lame")
    _make_stuck(conn, box.id)

    from trinity.advisories import _rabbit_hole_advisory
    first = _rabbit_hole_advisory(conn, box)
    assert first is not None
    assert first.offers_methods_index is True
    assert "trinity methods" in first.sentence

    # Still stuck (same episode) -- the offer must NOT repeat, even
    # though the underlying rabbit-hole signal itself still fires.
    second = _rabbit_hole_advisory(conn, box)
    assert second is not None
    assert second.offers_methods_index is False
    assert "trinity methods" not in second.sentence

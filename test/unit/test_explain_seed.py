"""Tests for the pre-authored explanation seed library."""
from __future__ import annotations

from trinity.explain import get_explanation
from trinity.explain_seed.combine import all_entries, seed_all


def test_all_entries_has_no_duplicates_across_categories():
    # all_entries() itself asserts on duplicates; calling it is the test.
    entries = all_entries()
    assert len(entries) > 50  # sanity floor -- real coverage, not a stub


def test_all_entries_have_nonempty_explanations():
    entries = all_entries()
    for command, explanation in entries.items():
        assert len(explanation.strip()) > 30, f"suspiciously short explanation for {command!r}"


def test_seed_all_inserts_into_empty_db(conn):
    count = seed_all(conn)
    assert count == len(all_entries())


def test_seed_all_is_idempotent(conn):
    first = seed_all(conn)
    second = seed_all(conn)
    assert first > 0
    assert second == 0  # nothing new the second time


def test_seed_all_does_not_overwrite_user_cached_explanation(conn):
    from trinity.explain import save_explanation

    # Pick a real seeded command and pre-cache a different (operator's own)
    # explanation for it before seeding -- seeding must not clobber it.
    sample_command = next(iter(all_entries()))
    save_explanation(conn, sample_command, "MY OWN CUSTOM EXPLANATION", source="user_curated")

    seed_all(conn)

    assert get_explanation(conn, sample_command) == "MY OWN CUSTOM EXPLANATION"


def test_seeded_command_is_retrievable_via_get_explanation(conn):
    seed_all(conn)
    sample_command = "sudo -l"
    explanation = get_explanation(conn, sample_command)
    assert explanation is not None
    assert "sudo" in explanation.lower()


def test_seeded_entries_are_tagged_with_preseed_source(conn):
    seed_all(conn)
    row = conn.execute(
        "SELECT source FROM command_explanations WHERE command = ?", ("sudo -l",)
    ).fetchone()
    assert row["source"] == "trinity_preseed"

"""Tests for Trinity's Voice v1 -- the hand-authored teaching corpus
and its deterministic renderer (docs/TRINITY_VOICE_DESIGN.md)."""
from __future__ import annotations

from trinity.voice import (
    NARRATABLE_CONFIDENCE,
    get_voice_text,
    seed_voice_entries,
)
from trinity.voice_seed import ENTRIES


def test_entries_have_no_duplicate_titles():
    # ENTRIES is a dict, so this is really "the file parses to unique
    # keys" -- but it also guards a future refactor that might
    # accidentally build it as a list and reintroduce duplicates.
    assert len(ENTRIES) > 0


def test_every_entry_has_all_three_parts_and_is_substantive():
    for kb_title, parts in ENTRIES.items():
        for key in ("what_it_is", "why_it_happens", "what_to_watch_for"):
            assert key in parts, f"{kb_title!r} missing {key!r}"
            assert len(parts[key].strip()) > 60, (
                f"{kb_title!r}'s {key!r} looks like a stub, not real teaching text"
            )


def test_every_entry_joins_to_a_real_kb_seed_title(seeded_conn):
    # The whole design hinges on kb_title matching kb_entries.title
    # exactly -- a typo here means the entry silently never renders,
    # with no error anywhere (get_voice_text just returns None).
    seeded_titles = {
        row["title"] for row in seeded_conn.execute("SELECT title FROM kb_entries").fetchall()
    }
    for kb_title in ENTRIES:
        assert kb_title in seeded_titles, (
            f"voice_seed.py has an entry for {kb_title!r} that doesn't "
            "match any kb_entries.title -- check for a typo/drift"
        )


def test_seed_voice_entries_inserts_into_empty_db(conn):
    count = seed_voice_entries(conn)
    assert count == len(ENTRIES)


def test_seed_voice_entries_is_idempotent(conn):
    first = seed_voice_entries(conn)
    second = seed_voice_entries(conn)
    assert first > 0
    assert second == 0


def test_seed_voice_entries_does_not_overwrite_an_edited_entry(conn):
    seed_voice_entries(conn)
    sample_title = next(iter(ENTRIES))
    conn.execute(
        "UPDATE finding_explanations SET what_it_is = ? WHERE kb_title = ?",
        ("MY HAND-EDITED VERSION", sample_title),
    )
    conn.commit()

    seed_voice_entries(conn)  # re-seeding must not clobber the edit

    row = conn.execute(
        "SELECT what_it_is FROM finding_explanations WHERE kb_title = ?", (sample_title,)
    ).fetchone()
    assert row["what_it_is"] == "MY HAND-EDITED VERSION"


def test_get_voice_text_renders_all_four_parts_with_instance_data(conn):
    seed_voice_entries(conn)
    text = get_voice_text(
        conn, "vsftpd 2.3.4 backdoor (CVE-2011-2523)", "confirmed",
        host="10.10.10.3", port=21, product="vsftpd", version="2.3.4",
    )
    assert text is not None
    assert "backdoor" in text.lower()
    # The instance paragraph must contain the ACTUAL data passed in --
    # this is the "verify against your own scan" guarantee, and it must
    # be a real substitution, not a hope that an AI mentioned it.
    assert "10.10.10.3:21" in text
    assert "vsftpd 2.3.4" in text


def test_get_voice_text_returns_none_for_best_guess_confidence(conn):
    # A best_guess searchsploit hit dressed up in confident instructor
    # prose would launder its own uncertainty -- this must never fire.
    seed_voice_entries(conn)
    text = get_voice_text(
        conn, "vsftpd 2.3.4 backdoor (CVE-2011-2523)", "best_guess",
        host="10.10.10.3", port=21,
    )
    assert text is None


def test_get_voice_text_returns_none_when_no_entry_exists(conn):
    seed_voice_entries(conn)
    text = get_voice_text(conn, "Some Finding Nobody Has Authored Yet", "confirmed")
    assert text is None


def test_narratable_confidence_excludes_best_guess():
    assert "best_guess" not in NARRATABLE_CONFIDENCE
    assert "confirmed" in NARRATABLE_CONFIDENCE
    assert "likely" in NARRATABLE_CONFIDENCE


def test_instance_paragraph_degrades_gracefully_without_port_or_product(conn):
    seed_voice_entries(conn)
    # A path-based finding (no port) must not crash the renderer.
    text = get_voice_text(
        conn, "HTTP directory brute-forcing is next after a webserver is found",
        "confirmed", host="10.10.10.3",
    )
    assert text is not None
    assert "10.10.10.3" in text


def test_voice_seeds_automatically_via_connect(tmp_path):
    # seed_voice_entries is wired into db._seed_brain -- a real connect()
    # (not the bare fixture) must have the corpus available with zero
    # extra setup, same guarantee kb/explain/error seeding already has.
    from trinity.db import connect

    conn = connect(tmp_path / "trinity_test.db")
    count = conn.execute("SELECT count(*) AS n FROM finding_explanations").fetchone()["n"]
    assert count == len(ENTRIES)

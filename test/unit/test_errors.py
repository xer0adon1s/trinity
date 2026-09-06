"""Tests for the error-diagnosis cache."""
from __future__ import annotations

from trinity.errors import build_error_escalation_prompt, find_error_match, save_error_fix
from trinity.errors_seed import seed_error_patterns


def test_find_error_match_returns_none_on_miss(conn):
    assert find_error_match(conn, "some completely novel error nobody has ever seen") is None


def test_save_and_find_error_fix_roundtrip(conn):
    save_error_fix(conn, "Connection refused on port 4444", "listener wasn't up", "start nc first")
    match = find_error_match(conn, "Connection refused on port 4444")
    assert match is not None
    assert match.cause == "listener wasn't up"
    assert match.fix == "start nc first"
    assert match.source == "ai_escalation"


def test_fuzzy_match_on_overlapping_tokens(conn):
    save_error_fix(conn, "Permission denied (publickey) when connecting via ssh", "no matching key", "use password auth")
    # A differently-worded but related error should still fuzzy-match
    # on shared tokens (permission, denied, publickey, ssh).
    match = find_error_match(conn, "permission denied publickey ssh error")
    assert match is not None


def test_build_error_escalation_prompt_includes_error_text():
    prompt = build_error_escalation_prompt("Connection timed out")
    assert "Connection timed out" in prompt


def test_seed_error_patterns_inserts_and_is_idempotent(conn):
    first = seed_error_patterns(conn)
    assert first > 0
    second = seed_error_patterns(conn)
    assert second == 0


def test_seeded_error_patterns_are_findable(conn):
    seed_error_patterns(conn)
    match = find_error_match(conn, "Connection refused")
    assert match is not None
    assert match.source == "trinity_preseed"


def test_novel_error_sharing_only_a_generic_word_does_not_false_match(conn):
    # Regression test: a genuinely novel error that happens to share
    # only the word "error" with a seeded pattern (e.g. "syntax error")
    # must NOT be treated as a match -- one generic shared token is not
    # meaningful overlap.
    seed_error_patterns(conn)
    match = find_error_match(conn, "some totally weird never before seen error xyzzy123")
    assert match is None


def test_long_generic_words_do_not_cause_false_positive_matches(conn):
    # Regression test for Cursor's review finding: the old ">= 8 chars
    # is distinctive" rule let long-but-generic English words
    # ("connection", "forbidden", "unexpected") count as a meaningful
    # match on their own, causing confident-looking wrong diagnoses.
    seed_error_patterns(conn)

    # None of these should match ANY seeded pattern on the strength of
    # a single shared generic word alone.
    assert find_error_match(conn, "connection error happened somewhere") is None
    assert find_error_match(conn, "got a connection problem") is None
    assert find_error_match(conn, "forbidden page shown") is None
    # "unexpected" alone (no other overlapping token) must not match --
    # note this is deliberately a DIFFERENT phrase than the seeded
    # "syntax error near unexpected token" pattern, which legitimately
    # shares 2 tokens ("unexpected", "token") with that seed and is
    # expected to match on real 2-token overlap, not treated as a bug.
    assert find_error_match(conn, "totally unexpected result from the server") is None


def test_distinctive_single_token_still_matches(conn):
    # A single genuinely distinctive token (not a common English word)
    # should still be enough on its own -- the fix must not overcorrect
    # into requiring 2+ tokens for every case.
    save_error_fix(conn, "Permission denied (publickey)", "no matching key", "use password auth")
    match = find_error_match(conn, "just saw publickey mentioned somewhere")
    assert match is not None

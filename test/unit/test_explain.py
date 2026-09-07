"""Tests for the ELI5 explanation cache."""
from __future__ import annotations

from trinity.explain import build_escalation_prompt, get_explanation, normalize, save_explanation


def test_normalize_collapses_whitespace():
    assert normalize("nmap  -sC   -sV\n") == "nmap -sC -sV"


def test_get_explanation_returns_none_when_uncached(conn):
    assert get_explanation(conn, "nmap -sC -sV") is None


def test_save_then_get_roundtrip(conn):
    save_explanation(conn, "nmap -sC -sV", "Runs default scripts and detects service versions.")
    assert get_explanation(conn, "nmap -sC -sV") == "Runs default scripts and detects service versions."


def test_cache_hit_is_normalized(conn):
    save_explanation(conn, "nmap -sC -sV", "explanation text")
    # Different whitespace, same logical command — should still hit cache.
    assert get_explanation(conn, "nmap  -sC   -sV") == "explanation text"


def test_save_explanation_overwrites_existing(conn):
    save_explanation(conn, "gobuster dir -u x -w y", "first version")
    save_explanation(conn, "gobuster dir -u x -w y", "corrected version")
    assert get_explanation(conn, "gobuster dir -u x -w y") == "corrected version"


def test_build_escalation_prompt_includes_command():
    prompt = build_escalation_prompt("nmap -sC -sV 10.10.10.3")
    assert "nmap -sC -sV 10.10.10.3" in prompt
    assert "ELI5" in prompt


def test_real_target_ip_hits_templated_seed_entry(conn):
    """Regression test: found live while reviewing the AD engine's
    explain-seed entries, but confirmed as a systemic bug affecting
    the ENTIRE ~86-entry pre-authored library, not just AD. Every seed
    entry is keyed with the literal template token '<target>', but a
    real suggested command substitutes an actual IP -- so no real
    command from `trinity next`/`suggest` could ever hit a seed cache
    entry under plain string equality before this fix."""
    save_explanation(conn, "nmap -sC -sV <target>", "seed explanation", source="trinity_preseed")
    assert get_explanation(conn, "nmap -sC -sV 10.10.10.3") == "seed explanation"


def test_dollar_target_placeholder_hits_templated_seed_entry(conn):
    """Same bug, the other real substitution shape: suggest/engine.py
    uses the literal string $TARGET when no host is known yet (see
    _effective_host's fallback) -- that must also hit the seed cache."""
    save_explanation(conn, "enum4linux-ng -A <target>", "seed explanation", source="trinity_preseed")
    assert get_explanation(conn, "enum4linux-ng -A $TARGET") == "seed explanation"


def test_exact_match_still_takes_priority_over_templated_fallback(conn):
    """An operator-corrected explanation for the EXACT real command
    (via the normal explain -> cache-explanation flow) must win over
    the generic templated seed entry, not be silently shadowed by it."""
    save_explanation(conn, "nmap -sC -sV <target>", "generic seed text", source="trinity_preseed")
    save_explanation(conn, "nmap -sC -sV 10.10.10.3", "specific corrected text", source="user_curated")
    assert get_explanation(conn, "nmap -sC -sV 10.10.10.3") == "specific corrected text"


def test_command_with_no_target_at_all_does_not_false_hit(conn):
    """A command containing neither an IPv4 literal nor $TARGET must
    not be mangled into matching an unrelated seed entry."""
    save_explanation(conn, "id", "seed explanation for id", source="trinity_preseed")
    assert get_explanation(conn, "whoami") is None


def test_real_getnpusers_command_hits_ad_seed_entry(conn):
    """Regression test for docs/AD_ENGINE_OPEN_QUESTIONS.md's "explain
    cache still misses real AD commands": GetNPUsers.py's real
    domain/-usersfile/-dc-ip substitutions must hit the seed entry,
    not just the target-only fix."""
    save_explanation(
        conn,
        "GetNPUsers.py <domain>/ -usersfile <userlist> -no-pass -dc-ip <target>",
        "seed explanation",
        source="trinity_preseed",
    )
    real = "GetNPUsers.py htb.local/ -usersfile users.txt -no-pass -dc-ip 10.10.10.161"
    assert get_explanation(conn, real) == "seed explanation"


def test_real_ldapsearch_dn_command_hits_ad_seed_entry(conn):
    """Same bug, ldapsearch's -b DN shape (from
    suggest/engine.py's _suggest_for_ldap_anon)."""
    save_explanation(
        conn,
        "ldapsearch -x -H ldap://<target> -b '<base>' '(objectClass=user)' sAMAccountName",
        "seed explanation",
        source="trinity_preseed",
    )
    real = "ldapsearch -x -H ldap://10.10.10.161 -b 'DC=htb,DC=local' '(objectClass=user)' sAMAccountName"
    assert get_explanation(conn, real) == "seed explanation"


def test_getnpusers_domain_templating_does_not_affect_unrelated_commands(conn):
    """The GetNPUsers/-usersfile/-b templating is gated on a command
    PREFIX check so it never touches unrelated commands that happen to
    contain similar-looking tokens elsewhere."""
    save_explanation(conn, "id", "seed explanation for id", source="trinity_preseed")
    assert get_explanation(conn, "echo GetNPUsers.py fake/ -usersfile x") is None

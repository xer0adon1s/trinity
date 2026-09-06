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

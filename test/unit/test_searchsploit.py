"""Tests for searchsploit integration -- primarily the argv-injection
guard, since search terms ultimately come from scan-derived (not fully
operator-controlled) data."""
from __future__ import annotations

from unittest.mock import patch

from trinity.kb.searchsploit import _sanitize_terms, search


def test_sanitize_terms_drops_leading_dash_terms():
    assert _sanitize_terms(("-u",)) == []
    assert _sanitize_terms(("--help",)) == []
    assert _sanitize_terms(("--update",)) == []


def test_sanitize_terms_keeps_legitimate_terms():
    assert _sanitize_terms(("vsftpd", "2.3.4")) == ["vsftpd", "2.3.4"]


def test_sanitize_terms_drops_only_the_dangerous_ones_mixed_in():
    assert _sanitize_terms(("samba", "-u", "3.0.20")) == ["samba", "3.0.20"]


def test_sanitize_terms_drops_empty_strings():
    assert _sanitize_terms(("", "vsftpd", "")) == ["vsftpd"]


def test_search_never_invokes_subprocess_with_a_leading_dash_term():
    # Regression test for the exact bug Cursor's review found:
    # scan-derived product/version fields like "-u" must never reach
    # subprocess.run as a bare argv token. Note: searchsploit's CLI
    # does NOT understand a "--" end-of-options separator (it errors
    # with "illegal option"), so the fix drops dangerous terms outright
    # rather than trying to escape them with "--".
    with patch("trinity.kb.searchsploit.is_available", return_value=True), \
         patch("trinity.kb.searchsploit.subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = '{"RESULTS_EXPLOIT": []}'

        search("-u", "1.0")

        called_argv = mock_run.call_args[0][0]
        assert "-u" not in called_argv
        assert "1.0" in called_argv


def test_search_returns_empty_when_all_terms_are_unsafe():
    with patch("trinity.kb.searchsploit.is_available", return_value=True), \
         patch("trinity.kb.searchsploit.subprocess.run") as mock_run:
        result = search("-u", "--help")
        assert result == []
        mock_run.assert_not_called()

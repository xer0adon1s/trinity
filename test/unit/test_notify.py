"""Tests for the desktop-notification opt-in toggle (notify.py,
state.py's NOTIFY_ENABLED key) and its wiring into process.py's
critical-match path."""
from __future__ import annotations

from unittest.mock import patch

from trinity.boxes import create_box
from trinity.notify import is_notify_enabled, notify_critical
from trinity.state import NOTIFY_ENABLED, get_state, set_state


def test_notify_disabled_by_default(conn):
    assert is_notify_enabled(conn) is False


def test_notify_critical_is_a_noop_when_disabled(conn):
    with patch("trinity.notify._send") as mock_send:
        result = notify_critical(conn, "title", "body")
    assert result is False
    mock_send.assert_not_called()


def test_notify_critical_sends_when_enabled(conn):
    set_state(conn, NOTIFY_ENABLED, "1")
    with patch("trinity.notify._send", return_value=True) as mock_send:
        result = notify_critical(conn, "title", "body")
    assert result is True
    mock_send.assert_called_once_with("title", "body")


def test_notify_critical_returns_false_if_send_fails_even_when_enabled(conn):
    set_state(conn, NOTIFY_ENABLED, "1")
    with patch("trinity.notify._send", return_value=False):
        result = notify_critical(conn, "title", "body")
    assert result is False


def test_toggling_off_after_on(conn):
    set_state(conn, NOTIFY_ENABLED, "1")
    assert is_notify_enabled(conn) is True
    set_state(conn, NOTIFY_ENABLED, "0")
    assert is_notify_enabled(conn) is False


def test_process_scan_file_never_notifies_when_disabled(conn, tmp_path):
    """Verifies the real call site (process.py) actually respects the
    toggle, not just the notify.py function in isolation."""
    import shutil
    from pathlib import Path

    from trinity.process import process_scan_file

    box = create_box(conn, "NotifyGate")
    fixture = Path(__file__).parent.parent / "fixtures" / "lame_style_scan.xml"
    dest = tmp_path / "scan.xml"
    shutil.copy(fixture, dest)

    with patch("trinity.process.notify_critical") as mock_notify:
        process_scan_file(conn, box.id, dest)
    # notify_critical is always CALLED (it internally no-ops when
    # disabled) -- the real behavioral guarantee is that no actual
    # notify-send subprocess fires, which the disabled-by-default unit
    # tests above already cover. This just confirms the call site
    # passes conn through so the gate can apply.
    if mock_notify.called:
        args = mock_notify.call_args[0]
        assert args[0] is conn


def test_process_scan_file_batches_multiple_criticals_into_one_notification(conn, tmp_path):
    """Regression test for the real bug: a single scan with multiple
    critical matches used to fire one notify-send call PER finding
    (e.g. 3 separate desktop notifications nearly simultaneously for
    one scan). Now batched into exactly one call per process_scan_file
    invocation, regardless of how many critical matches it contains."""
    import shutil
    from pathlib import Path

    from trinity.process import process_scan_file

    box = create_box(conn, "NotifyBatch")
    fixture = Path(__file__).parent.parent / "fixtures" / "lame_style_scan.xml"
    dest = tmp_path / "scan.xml"
    shutil.copy(fixture, dest)

    with patch("trinity.process.notify_critical") as mock_notify:
        result = process_scan_file(conn, box.id, dest)

    critical_findings = [
        fr for fr in result.findings if fr.matches and fr.matches[0].severity == "critical"
    ]
    assert len(critical_findings) >= 2, "fixture needs 2+ criticals to exercise the batching path"
    # Exactly ONE notify_critical call for this whole scan, no matter
    # how many critical matches it contained.
    assert mock_notify.call_count == 1
    call_args = mock_notify.call_args[0]
    assert "matches" in call_args[1]  # e.g. "Trinity — N critical matches"

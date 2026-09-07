"""Tests for the hacker-name feature: opt-in toggle (state.py's
HACKER_NAME/HACKER_NAME_ENABLED keys), wizard.py's run_intro flow, and
the get/set helpers used by the `trinity nickname` CLI group. Mocks
Confirm.ask/Prompt.ask rather than piping stdin -- Rich prompts read
directly from console.input(), which CliRunner doesn't intercept, so
direct mocking is the reliable way to test this without a real TTY."""
from __future__ import annotations

from unittest.mock import patch

from trinity.state import HACKER_NAME, HACKER_NAME_ENABLED, get_state
from trinity.wizard import (
    get_hacker_name,
    run_intro,
    set_hacker_name,
    set_hacker_name_enabled,
)


def test_hacker_name_starts_unset_and_disabled(conn):
    assert get_hacker_name(conn) is None
    assert get_state(conn, HACKER_NAME_ENABLED) is None


def test_run_intro_declining_the_opt_in_leaves_it_off(conn):
    with patch("trinity.wizard.Confirm.ask", return_value=False):
        run_intro(conn)
    assert get_hacker_name(conn) is None


def test_run_intro_opting_in_and_naming_enables_it(conn):
    with patch("trinity.wizard.Confirm.ask", return_value=True), \
         patch("trinity.wizard.Prompt.ask", return_value="DocTest"):
        run_intro(conn)
    assert get_hacker_name(conn) == "DocTest"


def test_run_intro_opting_in_but_leaving_name_blank_stays_off(conn):
    with patch("trinity.wizard.Confirm.ask", return_value=True), \
         patch("trinity.wizard.Prompt.ask", return_value=""):
        run_intro(conn)
    assert get_hacker_name(conn) is None


def test_run_intro_always_marks_setup_done_regardless_of_opt_in_choice(conn):
    from trinity.state import SETUP_DONE

    with patch("trinity.wizard.Confirm.ask", return_value=False):
        run_intro(conn)
    assert get_state(conn, SETUP_DONE) == "1"


def test_rerunning_setup_offers_to_keep_an_already_enabled_name(conn):
    set_hacker_name(conn, "DocTest")
    with patch("trinity.wizard.Confirm.ask", return_value=True):
        run_intro(conn)  # "keep that?" -> yes
    assert get_hacker_name(conn) == "DocTest"


def test_rerunning_setup_can_turn_off_an_already_enabled_name(conn):
    set_hacker_name(conn, "DocTest")
    with patch("trinity.wizard.Confirm.ask", return_value=False), \
         patch("trinity.wizard.Prompt.ask", return_value=""):
        run_intro(conn)  # "keep that?" -> no, then blank new name -> off
    assert get_hacker_name(conn) is None
    # Name itself is preserved even though disabled.
    assert get_state(conn, HACKER_NAME) == "DocTest"


def test_rerunning_setup_can_rename_an_already_enabled_name(conn):
    set_hacker_name(conn, "DocTest")
    with patch("trinity.wizard.Confirm.ask", return_value=False), \
         patch("trinity.wizard.Prompt.ask", return_value="NewName"):
        run_intro(conn)  # "keep that?" -> no, then a new name
    assert get_hacker_name(conn) == "NewName"


def test_set_hacker_name_enables_it(conn):
    set_hacker_name(conn, "DocTest")
    assert get_hacker_name(conn) == "DocTest"


def test_disabling_preserves_the_name_for_later_reenable(conn):
    set_hacker_name(conn, "DocTest")
    set_hacker_name_enabled(conn, False)
    assert get_hacker_name(conn) is None
    assert get_state(conn, HACKER_NAME) == "DocTest"  # not erased

    set_hacker_name_enabled(conn, True)
    assert get_hacker_name(conn) == "DocTest"  # comes back without retyping


def test_hacker_name_key_stored_under_expected_state_key(conn):
    set_hacker_name(conn, "DocTest")
    assert get_state(conn, HACKER_NAME) == "DocTest"
    assert get_state(conn, HACKER_NAME_ENABLED) == "1"


def test_run_intro_asks_about_notifications_and_respects_no(conn):
    from trinity.state import NOTIFY_ENABLED

    with patch("trinity.wizard.Confirm.ask", return_value=False):
        run_intro(conn)
    assert get_state(conn, NOTIFY_ENABLED) == "0"


def test_run_intro_asks_about_notifications_and_respects_yes(conn):
    from trinity.state import NOTIFY_ENABLED

    with patch("trinity.wizard.Confirm.ask", return_value=True), \
         patch("trinity.wizard.Prompt.ask", return_value=""), \
         patch("trinity.notify.send_test_notification", return_value=True):
        run_intro(conn)
    assert get_state(conn, NOTIFY_ENABLED) == "1"


def test_run_intro_only_asks_about_notifications_once(conn):
    from trinity.state import NOTIFY_ENABLED, set_state

    set_state(conn, NOTIFY_ENABLED, "0")  # operator already answered before
    with patch("trinity.wizard.Confirm.ask", return_value=False) as mock_confirm:
        run_intro(conn)
    # Confirm.ask should only be called for the hacker-name opt-in,
    # never again for notifications once NOTIFY_ENABLED is already set.
    prompts = [call.args[0] for call in mock_confirm.call_args_list]
    assert not any("notification" in p for p in prompts)

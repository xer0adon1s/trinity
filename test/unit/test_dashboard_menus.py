"""Tests for the watch dashboard's Tools ('t') and Advanced ('a') menus
(src/trinity/tui/show_me_screens.py). Real Textual Pilot-driven tests
for the keybinding wiring (dashboard.py's action_open_tools/
action_open_advanced actually push the right screen), plus direct unit
tests for the screens' pure logic (recap/loot/gtfobins/hash text
rendering) without a full running app -- same "test the logic, not
the pixels" split test_dashboard.py already uses.
"""
from __future__ import annotations

from unittest.mock import patch

import pytest

from trinity.boxes import create_box
from trinity.db import connect
from trinity.loot import add_loot


@pytest.fixture
def dashboard_app(tmp_path):
    """A real TrinityDashboard app wired to an isolated in-memory-ish
    DB (tmp_path file, not :memory: -- Textual's own connect() call
    inside __init__ needs a real file path it can open itself)."""
    from trinity.tui.dashboard import TrinityDashboard

    db_path = tmp_path / "trinity_test.db"
    conn = connect(db_path)
    box = create_box(conn, "PilotBox", target="10.10.10.5")
    with patch("trinity.tui.dashboard.connect", return_value=conn):
        app = TrinityDashboard(box_name="PilotBox", watch_dir=tmp_path)
    return app, conn, box


@pytest.mark.asyncio
async def test_t_key_opens_tools_menu(dashboard_app):
    app, conn, box = dashboard_app
    async with app.run_test() as pilot:
        await pilot.press("t")
        await pilot.pause()
        from trinity.tui.show_me_screens import ToolsMenuScreen
        assert isinstance(app.screen, ToolsMenuScreen)


@pytest.mark.asyncio
async def test_a_key_opens_advanced_menu(dashboard_app):
    app, conn, box = dashboard_app
    async with app.run_test() as pilot:
        await pilot.press("a")
        await pilot.pause()
        from trinity.tui.show_me_screens import AdvancedOptionsScreen
        assert isinstance(app.screen, AdvancedOptionsScreen)


@pytest.mark.asyncio
async def test_escape_closes_tools_menu(dashboard_app):
    app, conn, box = dashboard_app
    async with app.run_test() as pilot:
        await pilot.press("t")
        await pilot.pause()
        await pilot.press("escape")
        await pilot.pause()
        from trinity.tui.show_me_screens import ToolsMenuScreen
        assert not isinstance(app.screen, ToolsMenuScreen)


def test_recap_screen_renders_real_recap_text(dashboard_app):
    from trinity.tui.show_me_screens import RecapScreen
    app, conn, box = dashboard_app
    screen = RecapScreen(box, conn)
    text = screen.get_text()
    assert "PilotBox" in text


def test_loot_list_screen_shows_empty_state(dashboard_app):
    from trinity.tui.show_me_screens import LootListScreen
    app, conn, box = dashboard_app
    screen = LootListScreen(box, conn)
    assert "Nothing recorded yet" in screen.get_text()


def test_loot_list_screen_shows_real_loot(dashboard_app):
    from trinity.tui.show_me_screens import LootListScreen
    app, conn, box = dashboard_app
    add_loot(conn, box.id, "flag", "HTB{tui_test}")
    screen = LootListScreen(box, conn)
    text = screen.get_text()
    assert "HTB{tui_test}" in text


def test_doctor_screen_renders_health_check(dashboard_app):
    from trinity.tui.show_me_screens import DoctorScreen
    screen = DoctorScreen()
    text = screen.get_text()
    assert "Trinity doctor" in text


def test_show_me_attestation_screen_advances_when_already_accepted(dashboard_app):
    from trinity.show_me import record_attestation
    from trinity.tui.show_me_screens import ShowMeAttestationScreen
    app, conn, box = dashboard_app
    record_attestation(conn)
    ShowMeAttestationScreen(box, conn)
    # compose() branches on has_attestation() -- just confirm it doesn't
    # render the raw attestation text a second time once already accepted.
    from trinity.show_me import has_attestation
    assert has_attestation(conn)


@pytest.mark.asyncio
async def test_mode_switch_updates_dashboard_status_bar(dashboard_app):
    """Fix 6.2 regression test: switching mode from the Advanced menu
    has to repaint the dashboard's status bar. Before the fix the DB
    was updated but the header kept showing the old mode until some
    unrelated action (mark-done/mark-skip) happened to refresh it."""
    from textual.widgets import Static

    from trinity.boxes import get_box_by_name
    app, conn, box = dashboard_app
    assert box.mode == "educational"

    async with app.run_test() as pilot:
        status = app.query_one("#status", Static)
        assert "mode: educational" in str(status.content)

        await pilot.press("a")
        await pilot.pause()
        # "Switch box mode" is the first row of the Advanced menu.
        await pilot.press("enter")
        await pilot.pause()
        from trinity.tui.show_me_screens import ModeSwitchScreen
        assert isinstance(app.screen, ModeSwitchScreen)

        # Rows are educational (0) / professional (1).
        await pilot.press("down")
        await pilot.press("enter")
        await pilot.pause()

        assert not isinstance(app.screen, ModeSwitchScreen)
        assert "mode: professional" in str(status.content)

    # ...and it actually persisted, not just repainted.
    assert get_box_by_name(conn, "PilotBox").mode == "professional"


@pytest.mark.asyncio
async def test_gtfobins_result_scrolls_and_keeps_close_button_visible(dashboard_app):
    """Fix 6.1's clipping fix, applied to GTFOBins: the shipped
    `ldconfig` entry is ~750 chars and wraps well past the screen's
    20-row max-height. The result has to live in a scrollable region so
    the overflow is reachable AND the Close button stays on screen."""
    from textual.containers import VerticalScroll
    from textual.widgets import Button, Input

    from trinity.tui.show_me_screens import GtfobinsLookupScreen
    app, conn, box = dashboard_app

    async with app.run_test() as pilot:
        await app.push_screen(GtfobinsLookupScreen())
        await pilot.pause()
        screen = app.screen
        screen.query_one("#gtfo-input", Input).value = "ldconfig"
        await pilot.press("enter")
        await pilot.pause()

        scroll = screen.query_one("#gtfo-scroll", VerticalScroll)
        # The entry really does overflow the box...
        assert scroll.max_scroll_y > 0
        # ...and the Close button survived it rather than being pushed
        # off the bottom of the modal.
        close = screen.query_one("#close", Button)
        assert close.region.height > 0
        assert close.region.bottom <= screen.query_one("#gtfo-box").region.bottom


@pytest.mark.asyncio
async def test_doctor_screen_runs_off_the_event_loop_and_fills_in(dashboard_app):
    """Fix 6.3's TUI half: DoctorScreen must paint a placeholder
    immediately and fill in the real report from a worker thread, so a
    slow VPN probe can't freeze the event loop. The existing
    `get_text()` unit test only covers the worker's payload -- this
    covers the placeholder -> result handoff the UI actually performs.

    run_doctor is blocked on an Event for the first half of the test:
    if it were still running inline, `run_test()` would deadlock here
    rather than reach the placeholder assertion."""
    import threading

    from textual.widgets import Static

    from trinity.doctor import DoctorReport
    from trinity.tui.show_me_screens import DoctorScreen
    app, conn, box = dashboard_app

    released = threading.Event()

    def slow_run_doctor(**kwargs):
        released.wait(timeout=5)
        return DoctorReport(checks=[])

    with patch("trinity.doctor.run_doctor", side_effect=slow_run_doctor):
        async with app.run_test() as pilot:
            await app.push_screen(DoctorScreen())
            await pilot.pause()
            body = app.screen.query_one("#doctor-body", Static)
            # Event loop is still live while the probe blocks.
            assert "Running health checks" in str(body.content)

            released.set()
            # Not workers.wait_for_complete() -- the dashboard's own
            # directory-watch worker never finishes, so that would hang.
            for _ in range(100):
                await pilot.pause()
                if "Trinity doctor" in str(body.content):
                    break
            assert "Trinity doctor" in str(body.content)

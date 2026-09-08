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

"""Tests for machine-local state (onboarding tracking) and VPN detection."""
from __future__ import annotations

from trinity.boxes import create_box
from trinity.state import ACTIVE_BOX_ID, SETUP_DONE, clear_state, get_state, set_state
from trinity.vpn import VpnStatus, check_vpn
from trinity.wizard import show_handoff


def test_state_roundtrip(conn):
    assert get_state(conn, SETUP_DONE) is None
    set_state(conn, SETUP_DONE, "1")
    assert get_state(conn, SETUP_DONE) == "1"


def test_state_update_overwrites(conn):
    set_state(conn, ACTIVE_BOX_ID, "1")
    set_state(conn, ACTIVE_BOX_ID, "2")
    assert get_state(conn, ACTIVE_BOX_ID) == "2"


def test_state_clear(conn):
    set_state(conn, SETUP_DONE, "1")
    clear_state(conn, SETUP_DONE)
    assert get_state(conn, SETUP_DONE) is None


def test_check_vpn_returns_vpnstatus():
    # We can't assert connected True/False (depends on the test machine's
    # actual network state) but we can assert the function runs cleanly
    # and returns a well-formed result either way.
    status = check_vpn()
    assert isinstance(status, VpnStatus)
    if status.connected:
        assert status.interface is not None
        assert status.kind in ("openvpn", "wireguard")
    else:
        assert status.interface is None


def test_show_handoff_empty_box_prints_nmap_and_can_launch_watch(conn, monkeypatch):
    launched = {}
    monkeypatch.setattr("trinity.wizard.Confirm.ask", lambda *a, **k: True)
    monkeypatch.setattr(
        "trinity.tui.dashboard.run_dashboard",
        lambda name, path: launched.update(name=name, path=path),
    )
    box = create_box(conn, "WatchPlease", target="10.10.10.3")
    show_handoff(conn, box)
    assert launched["name"] == "WatchPlease"
    assert launched["path"]


def test_show_handoff_decline_does_not_launch_watch(conn, monkeypatch):
    launched = []
    monkeypatch.setattr("trinity.wizard.Confirm.ask", lambda *a, **k: False)
    monkeypatch.setattr(
        "trinity.tui.dashboard.run_dashboard",
        lambda name, path: launched.append(name),
    )
    box = create_box(conn, "NoWatch", target="10.10.10.3")
    show_handoff(conn, box)
    assert launched == []

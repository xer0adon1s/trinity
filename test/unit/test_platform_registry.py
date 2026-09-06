"""Tests for the platform registry (theming, VPN-need flags, local
override merging)."""
from __future__ import annotations

from trinity.platform_registry import (
    get_omarchy_theme,
    get_platform,
    list_platform_ids,
    load_registry,
    resolve_theme,
)


def test_load_registry_has_expected_platforms():
    ids = list_platform_ids()
    for expected in ("htb", "thm", "portswigger", "overthewire", "ctf", "other"):
        assert expected in ids


def test_get_platform_returns_none_for_unknown():
    assert get_platform("definitely_not_a_real_platform") is None


def test_get_platform_returns_none_for_none():
    assert get_platform(None) is None


def test_htb_and_thm_need_vpn():
    assert get_platform("htb").needs_vpn is True
    assert get_platform("thm").needs_vpn is True


def test_portswigger_and_overthewire_do_not_need_vpn():
    assert get_platform("portswigger").needs_vpn is False
    assert get_platform("overthewire").needs_vpn is False


def test_every_platform_has_a_theme():
    for platform in load_registry().values():
        assert platform.theme.accent.startswith("#")
        assert platform.theme.background.startswith("#")
        assert platform.theme.foreground.startswith("#")


def test_resolve_theme_falls_back_to_default_for_unknown_platform():
    theme = resolve_theme("nonexistent_platform", prefer_omarchy=False)
    assert theme.accent == "#5f87ff"


def test_resolve_theme_uses_platform_theme_when_not_preferring_omarchy():
    theme = resolve_theme("htb", prefer_omarchy=False)
    assert theme.accent == get_platform("htb").theme.accent


def test_get_omarchy_theme_does_not_raise_on_any_system():
    # Whether or not this machine is running Omarchy, this must never
    # throw -- it should just return None on non-Omarchy systems.
    result = get_omarchy_theme()
    assert result is None or hasattr(result, "accent")

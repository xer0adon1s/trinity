"""Tests for the tool-availability registry."""
from __future__ import annotations

from unittest.mock import patch

from trinity.tools import build_install_guidance, get_tool_info, is_tool_installed


def test_get_tool_info_known_tool():
    info = get_tool_info("gobuster")
    assert info is not None
    assert info.check_binary == "gobuster"


def test_get_tool_info_unknown_tool_returns_none():
    assert get_tool_info("definitely_not_a_real_tool_xyz") is None


def test_is_tool_installed_true_when_which_finds_it():
    with patch("trinity.tools.shutil.which", return_value="/usr/bin/gobuster"):
        assert is_tool_installed("gobuster") is True


def test_is_tool_installed_false_when_which_finds_nothing():
    with patch("trinity.tools.shutil.which", return_value=None):
        assert is_tool_installed("gobuster") is False


def test_unknown_tool_name_still_gets_a_real_path_check():
    # An unregistered tool has no install-guidance metadata, but its
    # availability must still be checked for real (using its own name
    # as the binary) -- never silently assumed installed, which would
    # give a false "you're all set" for a genuinely missing tool.
    with patch("trinity.tools.shutil.which", return_value=None) as mock_which:
        assert is_tool_installed("some_tool_not_in_registry") is False
        mock_which.assert_called_once_with("some_tool_not_in_registry")

    with patch("trinity.tools.shutil.which", return_value="/usr/bin/some_tool_not_in_registry"):
        assert is_tool_installed("some_tool_not_in_registry") is True


def test_build_install_guidance_includes_multiple_platforms():
    guidance = build_install_guidance("gobuster")
    assert "apt" in guidance.lower()
    assert "pacman" in guidance.lower()
    assert "gobuster" in guidance


def test_build_install_guidance_unknown_tool_gives_generic_fallback():
    guidance = build_install_guidance("some_tool_not_in_registry")
    assert "some_tool_not_in_registry" in guidance


def test_every_registered_tool_has_at_least_one_install_path():
    # Guards against a registry entry that's all Nones -- would give
    # an operator zero actionable guidance.
    from trinity.tools import _REGISTRY
    for name, info in _REGISTRY.items():
        has_guidance = any([info.install_apt, info.install_pacman, info.install_brew, info.install_other])
        assert has_guidance, f"{name} has no install guidance at all"

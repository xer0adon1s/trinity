"""Platform registry: loads the shipped platforms.yaml, merges in a
local override file if present, and provides theme lookup -- including
an "omarchy" pseudo-mode that pulls live colors from the operator's
current Omarchy desktop theme instead of a fixed platform palette.

This is what makes Trinity platform-agnostic in practice (not just in
DESIGN.md prose): new platforms are data, not code, and an operator can
add their own (a university's private CTFd instance, a personal lab)
without ever touching Trinity's source.
"""
from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

import yaml

_SHIPPED_REGISTRY_PATH = Path(__file__).parent / "platforms.yaml"
_LOCAL_OVERRIDE_PATH = Path.home() / ".trinity" / "platforms.yaml"

_OMARCHY_THEME_LINK = Path.home() / ".local" / "state" / "omarchy" / "current" / "theme"


@dataclass
class PlatformTheme:
    accent: str
    background: str
    foreground: str


@dataclass
class Platform:
    id: str
    name: str
    theme: PlatformTheme
    scope_hint: str
    needs_vpn: bool
    vpn_help: str
    beginner_track: dict | None = None  # PROTOTYPE (2.6): skills band, not a writeup


def _load_yaml(path: Path) -> dict:
    if not path.exists():
        return {}
    with path.open() as f:
        return yaml.safe_load(f) or {}


def load_registry() -> dict[str, Platform]:
    """Loads the shipped registry, then merges a local override file on
    top if one exists at ~/.trinity/platforms.yaml -- local entries win
    on id collisions, and can add brand-new platform ids entirely."""
    shipped = _load_yaml(_SHIPPED_REGISTRY_PATH).get("platforms", {})
    local = _load_yaml(_LOCAL_OVERRIDE_PATH).get("platforms", {})

    merged: dict[str, dict] = {**shipped, **local}

    registry: dict[str, Platform] = {}
    for platform_id, data in merged.items():
        theme_data = data.get("theme", {})
        registry[platform_id] = Platform(
            id=platform_id,
            name=data.get("name", platform_id),
            theme=PlatformTheme(
                accent=theme_data.get("accent", "#5f87ff"),
                background=theme_data.get("background", "#101010"),
                foreground=theme_data.get("foreground", "#e0e0e0"),
            ),
            scope_hint=data.get("scope_hint", "").strip(),
            needs_vpn=bool(data.get("needs_vpn", False)),
            vpn_help=data.get("vpn_help", "").strip(),
            beginner_track=data.get("beginner_track"),
        )
    return registry


def get_platform(platform_id: str | None) -> Platform | None:
    if not platform_id:
        return None
    return load_registry().get(platform_id)


def list_platform_ids() -> list[str]:
    return sorted(load_registry().keys())


def get_omarchy_theme() -> PlatformTheme | None:
    """Reads the operator's live Omarchy desktop theme colors, if
    Omarchy is present and a theme is currently applied. Returns None
    on any non-Omarchy system or if anything about the lookup fails --
    this must never crash Trinity on a system that isn't running
    Omarchy at all."""
    try:
        theme_path = _OMARCHY_THEME_LINK.resolve(strict=True)
        colors_path = theme_path / "colors.toml"
        if not colors_path.exists():
            return None
        import tomllib
        with colors_path.open("rb") as f:
            data = tomllib.load(f)
        return PlatformTheme(
            accent=data.get("accent", "#5f87ff"),
            background=data.get("background", "#101010"),
            foreground=data.get("foreground", "#e0e0e0"),
        )
    except (OSError, ValueError, KeyError):
        return None


def resolve_theme(platform_id: str | None, prefer_omarchy: bool = False) -> PlatformTheme:
    """The single place theme choice happens: prefer the operator's
    live Omarchy desktop theme if requested and available, otherwise
    fall back to the box's platform theme, otherwise a neutral default."""
    if prefer_omarchy:
        omarchy_theme = get_omarchy_theme()
        if omarchy_theme:
            return omarchy_theme

    platform = get_platform(platform_id)
    if platform:
        return platform.theme

    return PlatformTheme(accent="#5f87ff", background="#101010", foreground="#e0e0e0")

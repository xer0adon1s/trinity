"""PROTOTYPE — tiny local GTFOBins-style lookup (DESIGN.md roadmap).

Hand-authored subset only. Not a scrape of gtfobins.github.io.
Enough that `sudo -l` → `trinity gtfobins vim` is useful after a
user-shell milestone. Link out; do not paste exploit scripts.
"""
from __future__ import annotations

from pydantic import BaseModel

# Keep this small and PR-able. Each entry is a one-line shape + URL.
_ENTRIES: dict[str, tuple[str, str]] = {
    "vim": (
        "If sudo allows vim, it can spawn a shell (`:!sh`) or write files as the privileged user.",
        "https://gtfobins.github.io/gtfobins/vim/",
    ),
    "find": (
        "If sudo allows find, `-exec` runs a command as that user.",
        "https://gtfobins.github.io/gtfobins/find/",
    ),
    "python": (
        "If sudo allows python, a one-liner can spawn a pty shell as that user.",
        "https://gtfobins.github.io/gtfobins/python/",
    ),
    "bash": (
        "If sudo allows bash, you already have the shell — run it.",
        "https://gtfobins.github.io/gtfobins/bash/",
    ),
    "less": (
        "If sudo allows less, `!sh` inside the pager is a shell.",
        "https://gtfobins.github.io/gtfobins/less/",
    ),
    "nmap": (
        "Older sudo nmap can `--interactive` then `!sh`; newer ones still write files via `-oG`.",
        "https://gtfobins.github.io/gtfobins/nmap/",
    ),
    "env": (
        "If sudo allows env, `sudo env /bin/sh` is enough.",
        "https://gtfobins.github.io/gtfobins/env/",
    ),
    "awk": (
        "If sudo allows awk, it can execute a shell snippet.",
        "https://gtfobins.github.io/gtfobins/awk/",
    ),
}


class GtfobinsHit(BaseModel):
    binary: str
    summary: str
    source_url: str


def lookup(binary: str) -> GtfobinsHit | None:
    key = binary.strip().lower().rsplit("/", 1)[-1]
    if key not in _ENTRIES:
        return None
    summary, url = _ENTRIES[key]
    return GtfobinsHit(binary=key, summary=summary, source_url=url)


def known_binaries() -> list[str]:
    return sorted(_ENTRIES)

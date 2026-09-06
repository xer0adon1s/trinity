"""Tool availability registry: checks whether a required binary is
actually installed before Trinity recommends a command that needs it,
and gives the operator real, platform-appropriate install guidance if
not. Trinity never installs anything itself -- the operator installs
their own tools, in their own terminal, same as they run their own
scans; this is the "I do / we do" boundary applied to tooling, not
just recon commands.

Distinct concept from platform_registry.py: that maps CTF/lab
platforms (HTB, THM, ...) to theming/VPN needs. This maps RECON TOOLS
(gobuster, enum4linux-ng, ...) to install checks/instructions. Same
shape (a small data-driven registry, shippable + locally extensible)
for a different axis of "things Trinity needs to know about."
"""
from __future__ import annotations

import shutil
from dataclasses import dataclass


@dataclass
class ToolInfo:
    name: str
    check_binary: str  # the actual binary name to look for on PATH
    install_apt: str | None = None
    install_pacman: str | None = None
    install_brew: str | None = None
    install_other: str | None = None  # fallback instructions/URL when no
                                       # clean package exists (e.g. a
                                       # GitHub release, a go install)


# Shipped registry of tools Trinity's suggestion engine currently
# recommends. Deliberately small and hand-maintained, same spirit as
# platforms.yaml -- grows via contribution as new suggestion rules are
# added, not meant to be exhaustive on day one.
_REGISTRY: dict[str, ToolInfo] = {
    "gobuster": ToolInfo(
        name="gobuster",
        check_binary="gobuster",
        install_apt="sudo apt install gobuster",
        install_pacman="sudo pacman -S gobuster",
        install_brew="brew install gobuster",
        install_other="https://github.com/OJ/gobuster (or: go install github.com/OJ/gobuster/v3@latest)",
    ),
    "enum4linux-ng": ToolInfo(
        name="enum4linux-ng",
        check_binary="enum4linux-ng",
        install_apt="sudo apt install enum4linux-ng",
        install_pacman=None,  # not in official Arch repos as of writing
        install_brew=None,
        install_other="https://github.com/cddmp/enum4linux-ng (pip install or clone + run directly)",
    ),
    "searchsploit": ToolInfo(
        name="searchsploit",
        check_binary="searchsploit",
        install_apt="sudo apt install exploitdb",
        install_pacman="sudo pacman -S exploitdb",
        install_brew="brew install exploitdb",
        install_other="https://www.exploit-db.com/searchsploit",
    ),
    "ftp": ToolInfo(
        name="ftp",
        check_binary="ftp",
        install_apt="sudo apt install ftp",
        install_pacman="sudo pacman -S inetutils",  # Arch ships ftp in inetutils
        install_brew="brew install inetutils",
        install_other=None,
    ),
    "nikto": ToolInfo(
        name="nikto",
        check_binary="nikto",
        install_apt="sudo apt install nikto",
        install_pacman="sudo pacman -S nikto",
        install_brew="brew install nikto",
        install_other="https://github.com/sullo/nikto",
    ),
    "whatweb": ToolInfo(
        name="whatweb",
        check_binary="whatweb",
        install_apt="sudo apt install whatweb",
        install_pacman=None,
        install_brew="brew install whatweb",
        install_other="https://github.com/urbanadventurer/WhatWeb",
    ),
    "nmap": ToolInfo(
        name="nmap",
        check_binary="nmap",
        install_apt="sudo apt install nmap",
        install_pacman="sudo pacman -S nmap",
        install_brew="brew install nmap",
        install_other="https://nmap.org/download.html",
    ),
    "ffuf": ToolInfo(
        name="ffuf",
        check_binary="ffuf",
        install_apt="sudo apt install ffuf",
        install_pacman="sudo pacman -S ffuf",
        install_brew="brew install ffuf",
        install_other="https://github.com/ffuf/ffuf (or: go install github.com/ffuf/ffuf/v2@latest)",
    ),
}


def get_tool_info(name: str) -> ToolInfo | None:
    return _REGISTRY.get(name)


def is_tool_installed(name: str) -> bool:
    """Checks whether a tool's binary is on PATH. For tools in the
    registry, uses their specific `check_binary` (in case the package
    name and binary name ever differ); for unregistered tools, checks
    PATH using the name itself -- still a real check, just without
    registry-sourced install guidance available if it's missing (see
    build_install_guidance)."""
    info = get_tool_info(name)
    check_binary = info.check_binary if info else name
    return shutil.which(check_binary) is not None


def build_install_guidance(name: str) -> str:
    """Returns plain-text install instructions for a missing tool.
    Always phrased as something the OPERATOR runs themselves -- Trinity
    never executes an install command on their behalf, same boundary
    as it never runs a scan/exploit on their behalf."""
    info = get_tool_info(name)
    if info is None:
        return (
            f"'{name}' doesn't have install instructions in Trinity's tool "
            "registry yet -- try your system's package manager, or search "
            f"for \"{name} install\" for the official instructions."
        )

    lines = [f"'{info.name}' isn't installed. Depending on your system:"]
    if info.install_apt:
        lines.append(f"  Debian/Ubuntu:  {info.install_apt}")
    if info.install_pacman:
        lines.append(f"  Arch:           {info.install_pacman}")
    if info.install_brew:
        lines.append(f"  macOS/Homebrew: {info.install_brew}")
    if info.install_other:
        lines.append(f"  Otherwise:      {info.install_other}")
    return "\n".join(lines)

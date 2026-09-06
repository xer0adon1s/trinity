"""Wordlist discovery: resolves a real, existing wordlist path before a
suggested gobuster/ffuf command is printed, instead of hardcoding
`/usr/share/wordlists/dirb/common.txt` (a Kali-specific path) and
letting the operator discover it's missing the hard way. Same "verify,
don't assume" spirit as vpn.py's real interface check and tools.py's
`shutil.which` check -- see docs/CLAUDE_CURSOR_DEBATE.md, Hole E.

Search paths are DATA, not hardcoded Kali strings, so contributing a
new distro's default wordlist location is a one-line PR, same
contribution model as platforms.yaml / tools.py.
"""
from __future__ import annotations

from pathlib import Path

# Ordered by how likely each is to exist and be a decent general-purpose
# directory wordlist -- Kali's dirb list first (most common existing
# habit to copy from tutorials), then common Arch/Omarchy/manual-install
# locations, then a couple of common personal-download spots.
_CANDIDATE_PATHS = [
    "/usr/share/wordlists/dirb/common.txt",
    "/usr/share/dirb/wordlists/common.txt",
    "/usr/share/seclists/Discovery/Web-Content/common.txt",
    "/usr/share/wordlists/seclists/Discovery/Web-Content/common.txt",
    "~/wordlists/common.txt",
    "~/SecLists/Discovery/Web-Content/common.txt",
    "~/.local/share/wordlists/common.txt",
]


def find_wordlist() -> str | None:
    """Returns the first candidate wordlist path that actually exists
    on this machine, or None if none of them do. Never raises."""
    for candidate in _CANDIDATE_PATHS:
        path = Path(candidate).expanduser()
        if path.is_file():
            return str(path)
    return None


def resolve_wordlist_in_command(command: str, placeholder: str = "/usr/share/wordlists/dirb/common.txt") -> str:
    """Rewrites a generated command's hardcoded wordlist placeholder to
    a real path found on this machine, if one was found. If nothing was
    found, leaves the command as-is -- the caller (coach.py's
    tool-missing-style presentation) is responsible for telling the
    operator no wordlist was found rather than silently sending them
    into the same 'file not found' ditch."""
    found = find_wordlist()
    if found and placeholder in command:
        return command.replace(placeholder, found)
    return command


NO_WORDLIST_GUIDANCE = (
    "No wordlist was found in any of the usual locations on this machine "
    "(checked Kali/dirb/SecLists paths and ~/wordlists). Install SecLists "
    "(https://github.com/danielmiessler/SecLists) or point the command at "
    "your own wordlist file before running it."
)

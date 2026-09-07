"""PROTOTYPE — deliberate dead-end language (Trinity_suggestions.md 2.9).

Beginners need permission to stop. Used when they skip a suggestion
so Trinity is not only capable of adding more work.
"""
from __future__ import annotations

_LINES: dict[str, str] = {
    "smb": "SMB gave you nothing. That is normal. Park it. If a website is still untouched, that is the more common door.",
    "enum4linux": "Share enum coming up empty is a result, not a failure. Write it down and leave it.",
    "ftp": "Anonymous FTP is often closed. You checked. That is the move. Don't live there.",
    "ssh": "SSH without creds is a locked front door. Fine. The interesting rooms are usually not behind it yet.",
    "gobuster": "A quiet wordlist is information. Try a different list later, or go look at a path you already have.",
    "nikto": "Nikto noise is real. One interesting path beats fifty info findings. Park the rest.",
}


def dead_end_line(command: str) -> str | None:
    hay = command.lower()
    for key, line in _LINES.items():
        if key in hay:
            return line
    return "Parking a lead is a skill. The box still has whatever you have not touched yet."

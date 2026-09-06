"""A tiny, data-driven library of human-sounding WHY sentences, keyed by
(phase, service). Exists because the coach's original WHY copy read
like a state machine explaining itself ("this is an enumeration-phase
step, and enumeration comes before the later phases...") -- true, but
lifeless. Per docs/CLAUDE_CURSOR_DEBATE.md's 1.8: same ranking data,
better sentence, kept as data (not more Python branches) so it's
PR-able the same way platforms.yaml/tools.py are.

Deliberately THIN for this pass -- four services, not forty. Grow it
from what an actual beginner gets stuck on, the same rationale as
error_patterns.py's seed set, rather than front-loading an encyclopedia
nobody asked for.
"""
from __future__ import annotations

# Keyed by (phase, service_keyword). service_keyword is matched as a
# case-insensitive substring of the suggestion's required_tool OR
# command, since Suggestion doesn't carry the raw service string --
# good enough for a handful of entries; revisit with a real join if
# this list grows past ~15.
_PHRASES: dict[tuple[str, str], str] = {
    ("enum", "gobuster"): "You have a website and you haven't looked inside it. Easy boxes hide the door in a path, not on the port.",
    ("enum", "enum4linux"): "Windows file shares love to talk if you just ask nicely — no login required, most of the time.",
    ("enum", "ftp"): "FTP servers sometimes just let anyone in. Costs nothing to check before assuming you need real credentials.",
    ("recon", "searchsploit"): "You already know the exact software and version. That's specific enough to check against a real exploit database, not guess.",
}


def phrase_for(phase: str, command: str, required_tool: str) -> str | None:
    """Looks up a human-sounding WHY line for this suggestion's
    (phase, tool-ish-keyword), falling back to None (caller keeps the
    existing mechanical phrasing) if nothing matches -- never raises,
    never forces a phrase that doesn't fit."""
    haystack = f"{command} {required_tool}".lower()
    for (phase_key, keyword), phrase in _PHRASES.items():
        if phase_key == phase and keyword in haystack:
            return phrase
    return None

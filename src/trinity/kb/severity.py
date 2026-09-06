"""Deterministic severity rating for KB/searchsploit matches.

No AI, no network call — a small local heuristic that's honest about being
a heuristic. Real CVSS scores (when we wire in a local NVD feed) always
take priority over this; this exists so every match has *some* severity
label even before that feed exists, which matters a lot for professional
mode's report (a pentest deliverable without severity ratings isn't
useful to a client).
"""
from __future__ import annotations

SEVERITY_ORDER = ["info", "low", "medium", "high", "critical"]

# Keyword signals in an exploit/KB title or tags, checked in order —
# first match wins. Deliberately conservative: RCE/backdoor/command
# execution always critical, auth bypass and privesc high, DoS and
# info-leak low/medium. Anything unmatched defaults to 'medium' rather
# than silently under- or over-stating risk.
_CRITICAL_SIGNALS = ["backdoor", "remote code execution", " rce", "command execution", "code execution"]
_HIGH_SIGNALS = ["privilege escalation", "auth bypass", "authentication bypass", "sql injection", "buffer overflow", "heap overflow", "arbitrary file"]
_MEDIUM_SIGNALS = ["information disclosure", "directory traversal", "xss", "cross-site", "csrf", "username enumeration"]
_LOW_SIGNALS = ["denial of service", " dos", "information leak"]


def rate_severity(title: str, tags: str | None = None) -> str:
    """Heuristically rate severity from an exploit/KB entry's title (and
    optional tags). Returns one of SEVERITY_ORDER. This is a best-effort
    local classifier, not a substitute for a real CVSS score — callers
    that have a cvss_score should prefer severity_from_cvss() instead."""
    text = f"{title} {tags or ''}".lower()

    for signal in _CRITICAL_SIGNALS:
        if signal in text:
            return "critical"
    for signal in _HIGH_SIGNALS:
        if signal in text:
            return "high"
    for signal in _MEDIUM_SIGNALS:
        if signal in text:
            return "medium"
    for signal in _LOW_SIGNALS:
        if signal in text:
            return "low"

    return "medium"


def severity_from_cvss(score: float) -> str:
    """Map a CVSS v3.x base score (0.0-10.0) to a severity label, using
    the standard FIRST.org CVSS v3 rating bands."""
    if score >= 9.0:
        return "critical"
    if score >= 7.0:
        return "high"
    if score >= 4.0:
        return "medium"
    if score > 0.0:
        return "low"
    return "info"

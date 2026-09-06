"""The suggestion engine: given what's been found on a box so far, propose
the next logical command to run. Pure rules, zero AI — deterministic
enumeration playbook knowledge, same as any experienced operator would
apply on autopilot for the first pass of a box.
"""
from __future__ import annotations

import sqlite3

from pydantic import BaseModel


class Suggestion(BaseModel):
    phase: str
    command: str
    rationale: str


# Rules are (predicate, builder) pairs, checked per-finding. Each rule
# looks at one finding and, if it applies, returns a Suggestion. Keeping
# these as small independent functions (rather than one giant branching
# mess) makes it cheap to add a new service/tool later without touching
# the ones that already work.


def _suggest_for_finding(finding: sqlite3.Row, already_suggested: set[str]) -> Suggestion | None:
    service = (finding["service"] or "").lower()
    product = (finding["product"] or "").lower()
    port = finding["port"]
    host = finding["host"] or "<target>"

    def fresh(command: str) -> str | None:
        """Return the command if it hasn't been suggested for this box
        yet, else None — avoids nagging with the same suggestion every
        time a new unrelated port is parsed."""
        return command if command not in already_suggested else None

    # HTTP/HTTPS: directory brute-force is always the next move.
    if service in ("http", "https", "http-proxy", "http-alt") or "apache" in product or "nginx" in product:
        scheme = "https" if service == "https" else "http"
        cmd = fresh(
            f"gobuster dir -u {scheme}://{host}:{port} "
            f"-w /usr/share/wordlists/dirb/common.txt -x php,txt,html"
        )
        if cmd:
            return Suggestion(
                phase="enum",
                command=cmd,
                rationale=(
                    f"Port {port} is serving HTTP — directory brute-forcing "
                    "is the standard next step to find hidden admin panels, "
                    "backups, or API routes before anything else."
                ),
            )

    # SMB: enumerate shares/users before anything else.
    if service in ("microsoft-ds", "netbios-ssn") or "samba" in product:
        cmd = fresh(f"enum4linux-ng -A {host}")
        if cmd:
            return Suggestion(
                phase="enum",
                command=cmd,
                rationale=(
                    f"Port {port} is SMB — enum4linux-ng pulls shares, users, "
                    "groups, and OS info in one pass, often without needing "
                    "credentials at all."
                ),
            )

    # FTP: check anonymous login before anything else.
    if service == "ftp":
        cmd = fresh(f"ftp {host}")
        if cmd:
            return Suggestion(
                phase="enum",
                command=cmd,
                rationale=(
                    f"Port {port} is FTP — always worth a quick anonymous "
                    "login check (username 'anonymous', any password) "
                    "before assuming credentials are needed."
                ),
            )

    # SSH: no active enum step (brute-forcing SSH isn't a sane default
    # suggestion), but flag it for version-based exploit research.
    if service == "ssh":
        cmd = fresh(f"searchsploit {product or 'openssh'} {finding['version'] or ''}".strip())
        if cmd:
            return Suggestion(
                phase="recon",
                command=cmd,
                rationale=(
                    f"Port {port} is SSH — checking the exact version against "
                    "the local exploit database is worth doing early, even "
                    "though SSH itself is rarely the first foothold."
                ),
            )

    return None


def suggest_next_commands(conn: sqlite3.Connection, box_id: int, limit: int = 10) -> list[Suggestion]:
    """Look at every finding recorded for a box and propose next commands,
    skipping anything already suggested for this box (checked against the
    suggestions table, not just this call) so repeated parses don't spam
    the same advice on every run."""
    already = {
        row["command"]
        for row in conn.execute(
            "SELECT command FROM suggestions WHERE box_id = ?", (box_id,)
        ).fetchall()
    }

    findings = conn.execute(
        "SELECT * FROM findings WHERE box_id = ? AND kind = 'port'", (box_id,)
    ).fetchall()

    suggestions: list[Suggestion] = []
    for finding in findings:
        suggestion = _suggest_for_finding(finding, already)
        if suggestion:
            already.add(suggestion.command)  # don't suggest the same thing twice in one call either
            suggestions.append(suggestion)
        if len(suggestions) >= limit:
            break

    return suggestions

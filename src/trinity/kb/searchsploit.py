"""Live integration with searchsploit — the offline ExploitDB mirror.

This isn't a file parser like the others; it's a query-time shell-out.
searchsploit ships with a full local copy of Exploit-DB (installed via the
`exploitdb` package) and updates itself independently with `searchsploit -u`.
Wrapping it means Trinity never has to maintain its own CVE/exploit dataset
for the common case — it defers to a purpose-built, actively-maintained,
fully offline tool that's often already on an operator's box.
"""
from __future__ import annotations

import json
import shutil
import subprocess

from pydantic import BaseModel


class ExploitDBResult(BaseModel):
    title: str
    edb_id: str
    date_published: str | None = None
    author: str | None = None
    type_: str | None = None
    platform: str | None = None
    verified: bool = False
    codes: str | None = None          # e.g. "CVE-2011-2523;OSVDB-73573"
    path: str | None = None           # local filesystem path to the PoC


def is_available() -> bool:
    """Whether searchsploit is installed on this system."""
    return shutil.which("searchsploit") is not None


def search(*terms: str, timeout: float = 15.0) -> list[ExploitDBResult]:
    """Query the local ExploitDB mirror for the given search terms.
    Returns an empty list (never raises) if searchsploit isn't installed
    or the query fails — this is a best-effort local lookup, not a
    critical-path dependency.
    """
    if not is_available():
        return []

    try:
        proc = subprocess.run(
            ["searchsploit", "-j", *terms],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except (subprocess.TimeoutExpired, OSError):
        return []

    if proc.returncode != 0 or not proc.stdout.strip():
        return []

    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return []

    results = []
    for entry in data.get("RESULTS_EXPLOIT", []):
        results.append(
            ExploitDBResult(
                title=entry.get("Title", "").strip(),
                edb_id=entry.get("EDB-ID", ""),
                date_published=entry.get("Date_Published") or None,
                author=entry.get("Author") or None,
                type_=entry.get("Type") or None,
                platform=entry.get("Platform") or None,
                verified=entry.get("Verified") == "1",
                codes=entry.get("Codes") or None,
                path=entry.get("Path") or None,
            )
        )

    return results


def search_cve(cve_id: str, timeout: float = 15.0) -> list[ExploitDBResult]:
    """Look up a specific CVE (e.g. 'CVE-2021-44228' or '2021-44228')."""
    if not is_available():
        return []

    cve_id = cve_id.upper().removeprefix("CVE-")

    try:
        proc = subprocess.run(
            ["searchsploit", "--cve", cve_id, "-j"],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except (subprocess.TimeoutExpired, OSError):
        return []

    if proc.returncode != 0 or not proc.stdout.strip():
        return []

    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return []

    results = []
    for entry in data.get("RESULTS_EXPLOIT", []):
        results.append(
            ExploitDBResult(
                title=entry.get("Title", "").strip(),
                edb_id=entry.get("EDB-ID", ""),
                date_published=entry.get("Date_Published") or None,
                author=entry.get("Author") or None,
                type_=entry.get("Type") or None,
                platform=entry.get("Platform") or None,
                verified=entry.get("Verified") == "1",
                codes=entry.get("Codes") or None,
                path=entry.get("Path") or None,
            )
        )

    return results

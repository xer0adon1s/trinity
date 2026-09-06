"""Parse gobuster's directory/vhost/dns enumeration text output.

Gobuster's `dir` mode (as of 3.8.x) has no built-in JSON output, so this
parses its standard line format:

    /admin                (Status: 301) [Size: 178] [--> http://target/admin/]
    /login.php            (Status: 200) [Size: 2421]

Works against output captured with `gobuster dir -u <url> -w <wordlist> -o out.txt`
or piped stdout.
"""
from __future__ import annotations

import re
from pathlib import Path

from trinity.parsers.nmap import Finding

# Matches: leading path, "(Status: N)", optional "[Size: N]"
_LINE_RE = re.compile(
    r"^(?P<path>\S+)\s+\(Status:\s*(?P<status>\d+)\)\s*(?:\[Size:\s*(?P<size>\d+)\])?"
)


def parse_gobuster_text(path: str | Path, host: str | None = None) -> list[Finding]:
    """Parse gobuster dir-mode text output into Findings, one per
    discovered path. `host` is optional context (gobuster's own output
    doesn't repeat the target on every line)."""
    path = Path(path)
    findings: list[Finding] = []

    for line in path.read_text(errors="ignore").splitlines():
        line = line.strip()
        match = _LINE_RE.match(line)
        if not match:
            continue

        findings.append(
            Finding(
                source_tool="gobuster",
                kind="path",
                host=host,
                path=match.group("path"),
                status_code=int(match.group("status")),
                detail=f"size={match.group('size')}" if match.group("size") else None,
                raw_ref=str(path),
            )
        )

    return findings

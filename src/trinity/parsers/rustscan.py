"""PROTOTYPE — rustscan greppable-ish text parser (suggestions 4.2).

Expects lines like `Open 10.10.10.3:80`. Prefer nmap XML when the
operator has it; this exists so a rustscan-first habit still lands
in the timeline.
"""
from __future__ import annotations

import re
from pathlib import Path

from trinity.parsers.nmap import Finding

_OPEN = re.compile(r"Open\s+(\S+):(\d+)", re.IGNORECASE)


def parse_rustscan_text(path: str | Path) -> list[Finding]:
    text = Path(path).read_text(errors="ignore")
    findings: list[Finding] = []
    seen: set[tuple[str, int]] = set()
    for match in _OPEN.finditer(text):
        host, port_s = match.group(1), match.group(2)
        port = int(port_s)
        key = (host, port)
        if key in seen:
            continue
        seen.add(key)
        findings.append(
            Finding(
                source_tool="rustscan",
                kind="port",
                host=host,
                port=port,
                service=None,
                detail="rustscan open-port line (no version probe — follow with nmap -sC -sV)",
                raw_ref=str(path),
            )
        )
    return findings

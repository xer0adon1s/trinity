"""rustscan output parser.

Prefer nmap XML when the operator has it (richer service/version
data); this exists so a rustscan-first habit still lands findings in
the timeline. Supports the two real rustscan output shapes (verified
against the actual installed `rustscan` binary, not assumed):

1. Greppable mode (`rustscan -g` / `--greppable`):
       10.10.10.3 -> [22,80,445]
   One line per host, ports as a bracketed comma list. No per-port
   service/state info at all in this mode.

2. Default streaming mode (no -g): rustscan prints one line per
   discovered port as it finds it, before handing off to nmap for the
   -sV/-sC follow-up (which is nmap's own text table, not rustscan's
   -- if the operator saved that whole combined output, only the
   rustscan-native "Discovered open port" lines are parsed here; run
   the nmap XML parser separately on any nmap -oX output for the
   version-probed data):
       Discovered open port 22/tcp on 10.10.10.3
"""
from __future__ import annotations

import re
from pathlib import Path

from trinity.parsers.nmap import Finding

_GREPPABLE = re.compile(r"^(\S+)\s*->\s*\[([\d,]+)\]", re.MULTILINE)
_DISCOVERED = re.compile(r"Discovered open port (\d+)/tcp on (\S+)", re.IGNORECASE)


def parse_rustscan_text(path: str | Path) -> list[Finding]:
    text = Path(path).read_text(errors="ignore")
    findings: list[Finding] = []
    seen: set[tuple[str, int]] = set()

    def _add(host: str, port: int) -> None:
        key = (host, port)
        if key in seen:
            return
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

    for match in _GREPPABLE.finditer(text):
        host = match.group(1)
        for port_s in match.group(2).split(","):
            if port_s.strip().isdigit():
                _add(host, int(port_s))

    for match in _DISCOVERED.finditer(text):
        port, host = int(match.group(1)), match.group(2)
        _add(host, port)

    return findings

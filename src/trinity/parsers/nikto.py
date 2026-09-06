"""Parse nikto's JSON output (`nikto -h <target> -Format json -output out.json`).

Nikto's JSON schema (stable across 2.x):
{
  "host": "...", "ip": "...", "port": "80",
  "vulnerabilities": [
    {"id": "...", "method": "GET", "url": "/path", "msg": "description..."},
    ...
  ]
}
"""
from __future__ import annotations

import json
from pathlib import Path

from trinity.parsers.nmap import Finding


def parse_nikto_json(path: str | Path) -> list[Finding]:
    path = Path(path)
    data = json.loads(path.read_text(errors="ignore"))

    host = data.get("host")
    port_raw = data.get("port")
    port = int(port_raw) if port_raw and str(port_raw).isdigit() else None

    findings: list[Finding] = []
    for vuln in data.get("vulnerabilities", []):
        findings.append(
            Finding(
                source_tool="nikto",
                kind="vuln",
                host=host,
                port=port,
                path=vuln.get("url"),
                detail=vuln.get("msg"),
                raw_ref=str(path),
            )
        )

    return findings

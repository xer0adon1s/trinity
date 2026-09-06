"""Parse whatweb's JSON output (`whatweb --log-json=out.json <target>`).

whatweb emits one JSON object per line (JSON Lines), one per scanned URL:
{
  "target": "http://...", "http_status": 200,
  "plugins": {
    "Apache": {"version": ["2.2.8"], ...},
    "PHP": {"version": ["5.2.4"], ...},
    ...
  }
}
"""
from __future__ import annotations

import json
from pathlib import Path

from trinity.parsers.nmap import Finding


def parse_whatweb_json(path: str | Path) -> list[Finding]:
    path = Path(path)
    findings: list[Finding] = []

    for line in path.read_text(errors="ignore").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue

        target = record.get("target")
        status = record.get("http_status")
        plugins = record.get("plugins", {})

        for plugin_name, plugin_data in plugins.items():
            version = None
            if isinstance(plugin_data, dict):
                versions = plugin_data.get("version")
                if isinstance(versions, list) and versions:
                    version = versions[0]

            findings.append(
                Finding(
                    source_tool="whatweb",
                    kind="header",
                    host=target,
                    status_code=status,
                    product=plugin_name,
                    version=version,
                    raw_ref=str(path),
                )
            )

    return findings

"""Parse enum4linux-ng's JSON output (`enum4linux-ng -oJ out <target>`,
which writes `out.json`).

Schema (enum4linux-ng >= 1.0): a dict keyed by section, e.g.:
{
  "target": "...",
  "users": {"5000 (user1)": {"username": "user1", ...}, ...},
  "shares": {"C$": {"comment": "...", "mapping": "..."}, ...},
  "os_info": {"OS version": "...", ...},
  ...
}
Sections vary by what enum succeeded, so this reads defensively.
"""
from __future__ import annotations

import json
from pathlib import Path

from trinity.parsers.nmap import Finding


def parse_enum4linux_ng_json(path: str | Path) -> list[Finding]:
    path = Path(path)
    data = json.loads(path.read_text(errors="ignore"))

    host = data.get("target")
    findings: list[Finding] = []

    users = data.get("users") or {}
    if isinstance(users, dict):
        for key, info in users.items():
            username = info.get("username") if isinstance(info, dict) else key
            findings.append(
                Finding(
                    source_tool="enum4linux-ng",
                    kind="user",
                    host=host,
                    detail=f"user: {username}",
                    raw_ref=str(path),
                )
            )

    shares = data.get("shares") or {}
    if isinstance(shares, dict):
        for share_name, info in shares.items():
            comment = info.get("comment") if isinstance(info, dict) else None
            findings.append(
                Finding(
                    source_tool="enum4linux-ng",
                    kind="share",
                    host=host,
                    path=share_name,
                    detail=comment,
                    raw_ref=str(path),
                )
            )

    os_info = data.get("os_info") or {}
    if isinstance(os_info, dict) and os_info:
        summary = "; ".join(f"{k}: {v}" for k, v in os_info.items() if v)
        if summary:
            findings.append(
                Finding(
                    source_tool="enum4linux-ng",
                    kind="os_info",
                    host=host,
                    detail=summary,
                    raw_ref=str(path),
                )
            )

    return findings

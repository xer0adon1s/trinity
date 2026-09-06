"""Parse ffuf's JSON output (`ffuf ... -o out.json -of json`).

ffuf's JSON schema (stable since early 2.x):
{
  "commandline": "...",
  "results": [
    {"input": {"FUZZ": "admin"}, "url": "...", "status": 200,
     "length": 1234, "words": 10, "lines": 5, "host": "target", ...},
    ...
  ]
}
"""
from __future__ import annotations

import json
from pathlib import Path

from trinity.parsers.nmap import Finding


def parse_ffuf_json(path: str | Path) -> list[Finding]:
    path = Path(path)
    data = json.loads(path.read_text(errors="ignore"))

    findings: list[Finding] = []
    for result in data.get("results", []):
        fuzz_value = None
        fuzz_input = result.get("input", {})
        if isinstance(fuzz_input, dict) and fuzz_input:
            fuzz_value = next(iter(fuzz_input.values()))

        findings.append(
            Finding(
                source_tool="ffuf",
                kind="path",
                host=result.get("host"),
                path=result.get("url") or fuzz_value,
                status_code=result.get("status"),
                detail=(
                    f"length={result.get('length')} words={result.get('words')}"
                    if result.get("length") is not None
                    else None
                ),
                raw_ref=str(path),
            )
        )

    return findings

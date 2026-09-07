"""Shared "process one scan file" logic used by both the CLI parse-*
commands and watch-mode. Detects which parser to use by file shape
(extension + a peek at content), parses, matches, persists findings +
timeline events, and returns a summary — the single code path both the
one-shot CLI and the live watcher funnel through, so they can never
drift out of sync with each other.
"""
from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path

from pydantic import BaseModel

from trinity.match.engine import KBMatch, match_finding
from trinity.parsers.enum4linux_ng import parse_enum4linux_ng_json
from trinity.parsers.ffuf import parse_ffuf_json
from trinity.parsers.gobuster import parse_gobuster_text
from trinity.parsers.nikto import parse_nikto_json
from trinity.notify import notify_critical
from trinity.parsers.nmap import Finding, parse_nmap_xml
from trinity.parsers.rustscan import parse_rustscan_text
from trinity.parsers.whatweb import parse_whatweb_json
from trinity.suggest.engine import suggest_next_commands
from trinity.timeline import log_event


class FindingResult(BaseModel):
    finding: Finding
    matches: list[KBMatch]


class ProcessResult(BaseModel):
    tool: str
    findings: list[FindingResult]
    suggestions: list[str]  # command strings, for a quick summary line


def detect_and_parse(path: Path) -> tuple[str, list[Finding]] | None:
    """Guess which tool produced a file and parse it. Returns
    (tool_name, findings) or None if the file doesn't look like any
    known scan output (e.g. a partial/unrelated file the watcher
    happened to see).

    whatweb's own documented invocation (`whatweb --log-json=out.json`)
    produces a `.json`-suffixed file that is actually JSON Lines (one
    object per line), not a single JSON document -- so whatweb
    detection must be tried for ANY `.json`/`.jsonl` file based on
    content shape, not gated behind the filename containing "whatweb"
    or the suffix being exactly `.jsonl`. This was a real bug: a file
    saved as `whatweb.json` (whatweb's own default-ish naming) was
    silently undetectable."""
    suffix = path.suffix.lower()
    name = path.name.lower()

    try:
        if suffix == ".xml":
            text = path.read_text(errors="ignore")
            if "<nmaprun" in text:
                return "nmap", parse_nmap_xml(path)
            return None

        if suffix in (".json", ".jsonl"):
            text = path.read_text(errors="ignore").strip()
            if not text:
                return None

            # Try whatweb's JSON-Lines shape first: one JSON object per
            # line, each with "target"/"plugins" keys. This must come
            # before the single-JSON-document branches below, since a
            # multi-line JSONL file will fail json.loads() on the
            # whole text and would otherwise fall through to None.
            first_line = text.splitlines()[0]
            try:
                first_record = json.loads(first_line)
                if isinstance(first_record, dict) and "plugins" in first_record:
                    return "whatweb", parse_whatweb_json(path)
            except json.JSONDecodeError:
                pass

            # Otherwise, try it as one single JSON document (ffuf,
            # nikto, enum4linux-ng all emit one JSON object for the
            # whole scan, not one per line).
            try:
                data = json.loads(text)
            except json.JSONDecodeError:
                return None
            if isinstance(data, dict) and "results" in data and "commandline" in data:
                return "ffuf", parse_ffuf_json(path)
            if isinstance(data, dict) and "vulnerabilities" in data:
                return "nikto", parse_nikto_json(path)
            if isinstance(data, dict) and any(k in data for k in ("users", "shares", "os_info")):
                return "enum4linux-ng", parse_enum4linux_ng_json(path)
            return None

        if "whatweb" in name:
            # Fallback for whatweb output saved under a non-JSON-ish
            # extension (e.g. whatweb_output.txt) -- still JSON Lines
            # content, just an unusual filename.
            first_line = path.read_text(errors="ignore").strip().splitlines()
            if first_line:
                json.loads(first_line[0])  # sanity check it's JSON lines
                return "whatweb", parse_whatweb_json(path)
            return None

        if suffix in (".txt", ".out") and "gobuster" in name:
            return "gobuster", parse_gobuster_text(path)

        if suffix in (".txt", ".out"):
            rustscan_hits = parse_rustscan_text(path)
            if rustscan_hits and ("rustscan" in name or _mostly_rustscan_lines(path)):
                return "rustscan", rustscan_hits

    except (json.JSONDecodeError, ValueError, OSError, IndexError):
        return None

    return None


def _mostly_rustscan_lines(path: Path) -> bool:
    """Heuristic gate so a .txt file that merely CONTAINS a rustscan-
    shaped line somewhere (e.g. pasted into a larger notes file)
    doesn't get misidentified. Requires the file to be genuinely
    rustscan-shaped: either at least one greppable 'host -> [ports]'
    line, or at least one 'Discovered open port' line."""
    text = path.read_text(errors="ignore")
    if re.search(r"^\S+\s*->\s*\[[\d,]+\]", text, re.MULTILINE):
        return True
    return bool(re.search(r"Discovered open port \d+/tcp on \S+", text, re.IGNORECASE))


def process_scan_file(conn: sqlite3.Connection, box_id: int, path: Path) -> ProcessResult | None:
    """Parse a scan file, match every finding, persist findings + a
    timeline scan event + match events, and log/persist any new
    suggestions. Returns None if the file wasn't recognized as scan
    output.

    Critical-severity matches are batched into a SINGLE desktop
    notification per call, not one notify-send per finding -- a scan
    with 3 critical matches (a common real shape: multiple vulnerable
    services on one box) used to fire 3 separate notifications nearly
    simultaneously. See docs/FEATURES_BACKLOG.md's notify-storm note."""
    detected = detect_and_parse(path)
    if detected is None:
        return None

    tool, findings = detected
    if not findings:
        return ProcessResult(tool=tool, findings=[], suggestions=[])

    log_event(
        conn, box_id, "scan", f"{tool} scan parsed: {len(findings)} finding(s)",
        phase="recon", detail=str(path),
    )

    results: list[FindingResult] = []
    critical_titles: list[str] = []
    for finding in findings:
        cursor = conn.execute(
            """
            INSERT INTO findings
                (box_id, source_tool, kind, host, port, service, product, version, path, status_code, detail, raw_ref)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                box_id, finding.source_tool, finding.kind, finding.host, finding.port,
                finding.service, finding.product, finding.version, finding.path,
                finding.status_code, finding.detail, finding.raw_ref,
            ),
        )
        conn.commit()
        finding_id = cursor.lastrowid

        matches = match_finding(conn, finding)
        results.append(FindingResult(finding=finding, matches=matches))

        if matches:
            conn.execute("UPDATE findings SET matched = 1 WHERE id = ?", (finding_id,))
            conn.commit()
            top = matches[0]
            label = f"{finding.host}:{finding.port}" if finding.port else (finding.path or finding.host or "?")
            log_event(
                conn, box_id, "match", f"{label} matched: {top.title}",
                phase="recon", detail=top.summary, severity=top.severity, ref_id=finding_id,
            )
            if top.severity == "critical":
                critical_titles.append(top.title)
        else:
            label = f"{finding.host}:{finding.port}" if finding.port else (finding.path or finding.host or "?")
            log_event(
                conn, box_id, "finding", f"{label} — no local match",
                phase="recon", ref_id=finding_id,
            )

    if critical_titles:
        if len(critical_titles) == 1:
            notify_critical(conn, "Trinity — critical match", critical_titles[0])
        else:
            notify_critical(
                conn, f"Trinity — {len(critical_titles)} critical matches",
                "; ".join(critical_titles[:3]) + (" …" if len(critical_titles) > 3 else ""),
            )

    new_suggestions = suggest_next_commands(conn, box_id)
    suggestion_strings: list[str] = []
    for s in new_suggestions:
        cursor = conn.execute(
            "INSERT INTO suggestions (box_id, phase, command, rationale, nudge, required_tool, finding_id) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (box_id, s.phase, s.command, s.rationale, s.nudge, s.required_tool, s.finding_id),
        )
        conn.commit()
        log_event(
            conn, box_id, "suggestion", f"suggested: {s.command}",
            phase=s.phase, detail=s.rationale, ref_id=cursor.lastrowid,
        )
        suggestion_strings.append(s.command)

    return ProcessResult(tool=tool, findings=results, suggestions=suggestion_strings)

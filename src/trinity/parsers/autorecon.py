"""Walk an AutoRecon (github.com/Tib3rius/AutoRecon) results directory for
ONE target and dispatch each recognized file to Trinity's EXISTING parser
for that tool -- this is a dispatcher/walker, not a reimplementation of
any parsing logic (docs/FEATURES_BACKLOG.md's AutoRecon section, piece 2).

Trinity never runs AutoRecon (docs/OPEN_DECISIONS.md's "Nuclei / AutoRecon
/ nmap-automator launchers" rail) -- the operator runs it themselves in
their own terminal pane, and this module only reads the files it leaves
behind afterward.

Real AutoRecon results-directory shape (verified against the project's
own README/wiki and real captured HTB writeups, not guessed):

    results/<target>/
    |-- exploit/
    |-- loot/
    |-- report/
    `-- scans/
        |-- _commands.log
        |-- _manual_commands.txt
        |-- _errors.log            (only if something failed)
        |-- _quick_tcp_nmap.txt / .xml   (initial top-ports pass)
        |-- _full_tcp_nmap.txt / .xml    (full -p- pass)
        |-- xml/                         (all XML output lives here too)
        |   `-- tcp_80_http_nmap.xml
        |-- tcp_80_http_nmap.txt
        |-- tcp_80_http_gobuster.txt
        |-- tcp_80_http_nikto.txt
        |-- tcp_80_https_whatweb.txt
        `-- tcp80/                       (older/default --no-port-dirs=False
              `-- ... same per-service files, just nested one level deeper)

Per-service files are named `<protocol>_<port>_<service>_<tool>.<ext>`
(e.g. `tcp_80_http_gobuster.txt`). Whether AutoRecon nests those under a
`tcp<port>/` subdirectory or drops them flat in `scans/` varies by
version/options, so this walker recurses the whole tree rather than
assuming a fixed depth.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from trinity.parsers.enum4linux_ng import parse_enum4linux_ng_json
from trinity.parsers.ffuf import parse_ffuf_json
from trinity.parsers.gobuster import parse_gobuster_text
from trinity.parsers.nikto import parse_nikto_json
from trinity.parsers.nmap import Finding, parse_nmap_xml
from trinity.parsers.rustscan import parse_rustscan_text
from trinity.parsers.whatweb import parse_whatweb_json

# Files named `_commands.log`, `_manual_commands.txt`, `_errors.log`,
# `_patterns.log` etc are AutoRecon's own bookkeeping, not tool output --
# never worth trying to parse as a scan.
_BOOKKEEPING_PREFIXES = ("_commands", "_manual_commands", "_errors", "_patterns")


@dataclass
class AutoReconWalkResult:
    """Everything found while walking one AutoRecon results directory."""

    findings_by_tool: dict[str, list[Finding]] = field(default_factory=dict)
    skipped: list[str] = field(default_factory=list)  # human-readable "path: reason"

    @property
    def all_findings(self) -> list[Finding]:
        out: list[Finding] = []
        for findings in self.findings_by_tool.values():
            out.extend(findings)
        return out


def _identify_tool(path: Path) -> str | None:
    """Best-effort tool guess from an AutoRecon-style filename, using the
    same 'sniff, don't require an exact scheme' spirit as
    process.py's detect_and_parse(). Returns a tool key or None."""
    name = path.name.lower()
    stem = path.stem.lower()

    if path.suffix.lower() == ".xml":
        return "nmap"  # every XML file AutoRecon writes is nmap's -oX output

    if stem.startswith(_BOOKKEEPING_PREFIXES):
        return None

    # AutoRecon service-scan filenames end in `_<tool>` before the
    # extension, e.g. tcp_80_http_gobuster.txt, tcp_80_http_nikto.txt.
    for tool in ("gobuster", "nikto", "whatweb", "ffuf", "enum4linux-ng", "enum4linux_ng", "rustscan"):
        if tool.replace("-", "_") in name or tool in name:
            if "enum4linux" in name:
                return "enum4linux-ng"
            return tool

    if name.endswith("_nmap.txt"):
        return None  # nmap's own -oN text; the -oX XML twin is what we parse

    return None


def _parse_one(tool: str, path: Path) -> list[Finding] | None:
    """Dispatch to Trinity's existing parser for `tool`. Returns None
    (rather than raising) for a tool Trinity has no parser for yet, or if
    the file doesn't actually match that parser's expected shape."""
    try:
        if tool == "nmap":
            text = path.read_text(errors="ignore")
            if "<nmaprun" not in text:
                return None
            return parse_nmap_xml(path)
        if tool == "gobuster":
            return parse_gobuster_text(path)
        if tool == "nikto":
            return parse_nikto_json(path)
        if tool == "whatweb":
            return parse_whatweb_json(path)
        if tool == "ffuf":
            return parse_ffuf_json(path)
        if tool == "enum4linux-ng":
            return parse_enum4linux_ng_json(path)
        if tool == "rustscan":
            return parse_rustscan_text(path)
    except Exception:  # noqa: BLE001 -- one bad file must never abort the walk
        return None
    return None


def walk_autorecon_results(results_dir: str | Path) -> AutoReconWalkResult:
    """Walk an AutoRecon results directory for one target (i.e. the
    `results/<target>/` directory itself, or any directory containing a
    `scans/` subdirectory) and parse every recognized file with Trinity's
    existing per-tool parsers.

    Never raises on an individual unrecognized/unparseable file -- those
    are collected in `.skipped` instead, so one AutoRecon plugin Trinity
    doesn't understand yet can't take down the whole directory walk.
    """
    results_dir = Path(results_dir)
    scans_dir = results_dir / "scans" if (results_dir / "scans").is_dir() else results_dir

    result = AutoReconWalkResult()

    if not scans_dir.is_dir():
        result.skipped.append(f"{scans_dir}: no such directory")
        return result

    for path in sorted(scans_dir.rglob("*")):
        if not path.is_file():
            continue

        tool = _identify_tool(path)
        if tool is None:
            result.skipped.append(f"{path.relative_to(results_dir)}: no known parser for this file")
            continue

        findings = _parse_one(tool, path)
        if findings is None:
            result.skipped.append(f"{path.relative_to(results_dir)}: recognized as {tool} but failed to parse")
            continue
        if not findings:
            continue  # recognized + parsed cleanly, just nothing in it

        result.findings_by_tool.setdefault(tool, []).extend(findings)

    return result

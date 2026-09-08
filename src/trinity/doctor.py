"""`trinity doctor`: one health check across everything that commonly
sabotages a student's first box silently -- missing recon tools, VPN
not actually up, DB not reachable/writable. Read-only: doctor never
installs anything or mutates state, same "operator does the fixing"
boundary as tools.py's install guidance. See docs/FEATURES_BACKLOG.md
-- this was Alexander's own idea, floated as "run automatically at the
moments that matter" rather than a manual-only command.

Cheap by design: no network calls beyond the existing local `ip link`
probe vpn.py already does, no subprocess spawns beyond `shutil.which`
checks and vpn.py's `ip link` probe. Safe to call from wizard/watch/shoulder
startup without noticeable latency.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

from pydantic import BaseModel

from trinity.db import DEFAULT_DB_PATH
from trinity.tools import _REGISTRY, is_tool_installed
from trinity.vpn import check_vpn


class DoctorCheck(BaseModel):
    name: str
    ok: bool
    detail: str


class DoctorReport(BaseModel):
    checks: list[DoctorCheck]

    @property
    def all_ok(self) -> bool:
        return all(c.ok for c in self.checks)

    @property
    def failures(self) -> list[DoctorCheck]:
        return [c for c in self.checks if not c.ok]


def _check_db(db_path: Path | None = None) -> DoctorCheck:
    path = db_path or DEFAULT_DB_PATH
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(path)
        conn.execute("SELECT 1")
        conn.close()
        return DoctorCheck(name="database", ok=True, detail=str(path))
    except (sqlite3.Error, OSError) as exc:
        return DoctorCheck(name="database", ok=False, detail=f"{path}: {exc}")


def _check_tools() -> list[DoctorCheck]:
    checks = []
    for name in _REGISTRY:
        installed = is_tool_installed(name)
        checks.append(DoctorCheck(
            name=f"tool:{name}", ok=installed,
            detail="installed" if installed else "not on PATH -- `trinity next` will show install guidance when recommended",
        ))
    return checks


def _check_vpn(timeout: float | None = None) -> DoctorCheck:
    status = check_vpn() if timeout is None else check_vpn(timeout)
    if status.connected:
        return DoctorCheck(
            name="vpn", ok=True,
            detail=f"connected ({status.kind or 'unknown kind'}, {status.interface})",
        )
    return DoctorCheck(
        name="vpn", ok=False,
        detail="no tun/tap/wg interface detected -- fine if you're not doing an HTB/THM box right now",
    )


def run_doctor(
    *,
    db_path: Path | None = None,
    include_vpn: bool = True,
    vpn_timeout: float | None = None,
) -> DoctorReport:
    """Runs every check. VPN is optional (include_vpn=False) for
    contexts where "no VPN" isn't actionable, e.g. before a box/target
    is even chosen -- avoids a scary red line on a fresh install.

    `vpn_timeout` (seconds) caps the VPN probe's subprocess. Leave it
    None for the normal generous default; pass something small when
    doctor runs as a startup pre-check for an interactive command, so
    a hung `ip` can't hold the operator's terminal hostage."""
    checks = [_check_db(db_path)]
    checks.extend(_check_tools())
    if include_vpn:
        checks.append(_check_vpn(vpn_timeout))
    return DoctorReport(checks=checks)


def render_doctor(report: DoctorReport) -> str:
    lines = ["Trinity doctor"]
    lines.append("=" * len(lines[0]))
    for c in report.checks:
        mark = "OK  " if c.ok else "WARN"
        lines.append(f"[{mark}] {c.name}: {c.detail}")
    lines.append("")
    if report.all_ok:
        lines.append("Everything checks out.")
    else:
        missing_tools = [c.name.removeprefix("tool:") for c in report.failures if c.name.startswith("tool:")]
        if missing_tools:
            lines.append(
                f"Missing tools: {', '.join(missing_tools)} -- "
                "not required until Trinity actually recommends one; "
                "run `trinity next` for install guidance when it does."
            )
        vpn_failure = next((c for c in report.failures if c.name == "vpn"), None)
        if vpn_failure:
            lines.append("VPN: " + vpn_failure.detail)
        db_failure = next((c for c in report.failures if c.name == "database"), None)
        if db_failure:
            lines.append(f"Database problem: {db_failure.detail} -- this one's worth fixing before continuing.")
    return "\n".join(lines)

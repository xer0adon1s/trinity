"""PROTOTYPE — draft remediation blurbs for professional findings.

Tester still has to verify. Better than a blank '[fill in]' so the
deliverable is a notebook, not a skeleton.
"""
from __future__ import annotations

_DEFAULT = (
    "Validate the finding independently. Restrict the affected service "
    "to the intended audience, patch or disable the vulnerable component, "
    "and rotate any credentials exposed during testing."
)

_RULES: list[tuple[tuple[str, ...], str]] = [
    (("backdoor", "cve-"), "Upgrade or replace the affected service. Do not expose known-vulnerable versions to any network. Treat the host as compromised until rebuilt from a known-good image."),
    (("anonymous", "ftp"), "Disable anonymous FTP unless there is an explicit business need. If required, make the share read-only and contain no sensitive files."),
    (("smb", "null session", "share"), "Disable null/anonymous SMB sessions. Restrict share ACLs to named accounts. Block 445/139 from untrusted networks."),
    (("directory brute", "gobuster"), "Do not treat hidden paths as security. Remove leftover admin/backup/debug routes from production-facing vhosts."),
    (("sudo",), "Remove unnecessary sudo grants. Prefer least-privilege groups over NOPASSWD all. Review GTFOBins-class binaries."),
    (("suid",), "Remove the SUID bit from non-essential binaries. Replace with a narrowly scoped capability or a sudo rule if needed."),
    (("cron",), "Ensure cron scripts are owned and writable only by the account that should run them. No world-writable paths in root jobs."),
]


def draft_remediation(summary: str, detail: str | None = None) -> str:
    hay = f"{summary} {detail or ''}".lower()
    for needles, text in _RULES:
        if any(n in hay for n in needles):
            return text
    return _DEFAULT

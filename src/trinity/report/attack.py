"""PROTOTYPE — coarse ATT&CK technique tags for professional reports.

Heuristic keyword map, labeled as a draft. Not a substitute for a
human mapping a real engagement. Educational reports do not use this
(mode is a lens; ATT&CK is presentation for the professional template).
"""
from __future__ import annotations

# (needles, technique_id, name)
_RULES: list[tuple[tuple[str, ...], str, str]] = [
    (("vsftpd", "backdoor", "cve-2011-2523"), "T1190", "Exploit Public-Facing Application"),
    (("samba", "username map", "cve-2007-2447"), "T1210", "Exploitation of Remote Services"),
    (("smb", "null session", "share"), "T1135", "Network Share Discovery"),
    (("anonymous ftp", "ftp"), "T1078.001", "Valid Accounts: Default Accounts"),
    (("gobuster", "directory brute", "ffuf", "wordlist"), "T1595.003", "Active Scanning: Wordlist Scanning"),
    (("sudo",), "T1548.003", "Abuse Elevation Control Mechanism: Sudo and Sudo Caching"),
    (("suid",), "T1548.001", "Abuse Elevation Control Mechanism: Setuid and Setgid"),
    (("cron", "crontab"), "T1053.003", "Scheduled Task/Job: Cron"),
    (("linpeas", "privesc"), "T1068", "Exploitation for Privilege Escalation"),
    (("ssh", "publickey"), "T1021.004", "Remote Services: SSH"),
    (("hash", "hashcat", "john"), "T1110.002", "Brute Force: Password Cracking"),
]


def map_attack(text: str) -> list[tuple[str, str]]:
    hay = (text or "").lower()
    hits: list[tuple[str, str]] = []
    seen: set[str] = set()
    for needles, tid, name in _RULES:
        if any(n in hay for n in needles) and tid not in seen:
            hits.append((tid, name))
            seen.add(tid)
    return hits

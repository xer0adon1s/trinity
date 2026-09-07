"""Pre-authored error patterns: common failures a beginner hits early,
with the cause and fix, front-loaded so `trinity error` is useful from
a fresh install rather than needing weeks of organic escalations first
-- same rationale as explain_seed/. Not exhaustive; a real starter set
covering the most common early stumbling blocks."""
from __future__ import annotations

# Each entry: (error_text, cause, fix)
ENTRIES: list[tuple[str, str, str]] = [
    (
        "Connection refused",
        "The port you tried to connect to isn't actually open/listening on the "
        "target right now -- either the service isn't running, a firewall is "
        "blocking it, or you're connecting to the wrong port/IP.",
        "Re-run an nmap scan to confirm the port is actually open and which "
        "service is on it before retrying. Double-check you're using the "
        "current target IP (it can change between VPN sessions).",
    ),
    (
        "Connection timed out",
        "The target isn't responding at all -- usually means you're not "
        "actually connected to the lab VPN, the target machine hasn't "
        "finished booting yet, or you're using a stale/wrong IP.",
        "Confirm your VPN is up (check for a tun0/wg interface), confirm the "
        "target is active on the platform's dashboard, and re-verify the "
        "target IP.",
    ),
    (
        "Permission denied (publickey)",
        "SSH is refusing password authentication and you don't have a "
        "matching private key -- either the box only allows key-based auth, "
        "or you're using the wrong username.",
        "Check whether the box's writeup/hints mention a specific key file or "
        "username. If password auth should work, try again with "
        "-o PreferredAuthentications=password.",
    ),
    (
        "No route to host",
        "There's no network path to that IP at all -- almost always a VPN "
        "connectivity problem, not a problem with the target machine itself.",
        "Check your VPN connection is actually up and assigned an IP on the "
        "lab's subnet (ip a, look for tun0/wg0). Reconnect if needed.",
    ),
    (
        "ModuleNotFoundError",
        "A Python script (an exploit PoC, a tool) needs a package that isn't "
        "installed in your current Python environment.",
        "Install the missing package with pip (pip install <module_name>), "
        "or check the tool's README for a requirements.txt to install from.",
    ),
    (
        "Address already in use",
        "Something is already listening on the port you're trying to bind to "
        "-- often a leftover listener from a previous nc/reverse-shell "
        "attempt that never got closed.",
        "Find and kill the process holding the port (lsof -i :<port>, then "
        "kill <pid>), or just pick a different listener port.",
    ),
    (
        "command not found",
        "The tool you're trying to run isn't installed, or isn't on your "
        "shell's PATH.",
        "Install the tool with your package manager (apt/pacman/etc), or "
        "confirm the binary name/path is spelled correctly.",
    ),
    (
        "403 Forbidden",
        "The web server is refusing that specific request -- the path might "
        "exist but be access-restricted, or a WAF/security rule is blocking "
        "the request pattern.",
        "Try common bypass techniques: a trailing slash, different casing, "
        "an alternate HTTP method, or check if the path is only reachable "
        "from a different vhost/Host header.",
    ),
    (
        "SSL certificate verify failed",
        "The tool is refusing to trust the target's (often self-signed) "
        "TLS certificate -- extremely common on lab boxes.",
        "For CTF/lab use (never against production systems), add the "
        "relevant insecure/no-verify flag for your tool (e.g. curl -k, "
        "or --no-check-certificate for wget).",
    ),
    (
        "syntax error near unexpected token",
        "A shell one-liner (often a reverse shell payload) got mangled by "
        "quoting/escaping issues when it was copy-pasted or passed through "
        "another layer of shell/URL encoding.",
        "Check for smart quotes from copy-pasting, and make sure any nested "
        "quotes match the shell you're actually running the payload in "
        "(bash vs sh vs a web app's backend shell can quote differently).",
    ),
    (
        "Could not resolve host",
        "The hostname in the URL/command doesn't resolve — typo, no DNS "
        "on the lab VPN, or you used a name that only exists on the box.",
        "Use the target IP (or $TARGET) instead of a hostname, or check "
        "/etc/hosts if the writeup/box page gave you a name to add.",
    ),
    (
        "No such file or directory",
        "A path in the command doesn't exist on THIS machine — very often "
        "a Kali wordlist path pasted onto Arch/Fedora, or a file you "
        "haven't downloaded yet.",
        "ls the path. If it's a wordlist, run the suggestion again after "
        "Trinity's resolver rewrites it, or point -w at a file you actually have.",
    ),
    (
        "401 Unauthorized",
        "The path exists and wants credentials. That's a lead, not a wall.",
        "Note the realm/login form. Try default creds for the software "
        "banner, or come back once you have a username from elsewhere.",
    ),
    (
        "Segmentation fault",
        "A local exploit or PoC crashed. Common with old kernel exploits "
        "or the wrong architecture.",
        "Check uname -a vs what the exploit claims. Prefer a "
        "misconfiguration path (sudo -l, SUID, cron) over a crashy exploit.",
    ),
    (
        "bind: cannot assign requested address",
        "Your reverse-shell listener/LHOST is set to an IP this machine "
        "doesn't have — usually a leftover HTB IP from last session.",
        "ip a on tun0/wg0 and use THAT address as LHOST, not the target's.",
    ),
    (
        "Host key verification failed",
        "SSH has a saved fingerprint for this IP that doesn't match — "
        "common when lab IPs get reused.",
        "ssh-keygen -R <ip> and reconnect. Confirm you're on the right VPN first.",
    ),
    (
        "Directory not empty",
        "A tool (or you) tried to rmdir/mv over a folder that still has files.",
        "ls it. You probably already have loot in there — don't blow it away.",
    ),
    (
        "TOO MANY REDIRECTS",
        "The web app is bouncing you in a loop — often a missing cookie, "
        "wrong Host header, or HTTP vs HTTPS mix.",
        "curl -vI the first URL and follow Set-Cookie / Location by hand once.",
    ),
    (
        "invalid ELF header",
        "You tried to run a binary built for a different architecture, "
        "or the download was actually an HTML error page.",
        "file the binary. If it says HTML, you downloaded a login page. "
        "If it says ARM/MIPS and you're on x86_64, get the right build.",
    ),
    (
        "Password: Authentication failed",
        "The service rejected the password. Could be wrong user, wrong "
        "pass, or a lockout policy.",
        "Confirm the username source. Don't spray blindly — one careful "
        "retry beats a lockout on an easy box.",
    ),
]


def seed_error_patterns(conn) -> int:
    """Bulk-insert pre-authored error patterns, skipping any that
    already exist (matched on exact error_text) so this never
    duplicates entries on repeated `trinity init` runs."""
    inserted = 0
    for error_text, cause, fix in ENTRIES:
        exists = conn.execute(
            "SELECT 1 FROM error_patterns WHERE error_text = ?", (error_text,)
        ).fetchone()
        if exists:
            continue
        conn.execute(
            "INSERT INTO error_patterns (error_text, cause, fix, source) VALUES (?, ?, ?, 'trinity_preseed')",
            (error_text, cause, fix),
        )
        inserted += 1
    conn.commit()
    return inserted

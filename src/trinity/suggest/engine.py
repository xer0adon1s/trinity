"""The suggestion engine: given what's been found on a box so far, propose
the next logical command to run. Pure rules, zero AI — deterministic
enumeration playbook knowledge, same as any experienced operator would
apply on autopilot for the first pass of a box.
"""
from __future__ import annotations

import re
import sqlite3

from pydantic import BaseModel


class Suggestion(BaseModel):
    phase: str
    command: str
    rationale: str
    nudge: str
    required_tool: str
    finding_id: int | None = None
    # `nudge` is a deliberately vaguer description of WHY this step matters,
    # with no tool name and no answer-shaped content -- used by the graduated
    # hint ladder's level 2 (hints.py). `rationale` is the full detail (may
    # name the tool/technique) and is only ever shown at hint level 3 or in
    # `trinity next`'s always-visible output. Keeping these separate is what
    # stops the hint ladder from just repeating the answer one level early.
    # `required_tool` names the binary this command needs (e.g. "gobuster")
    # so the coach layer can check whether it's actually installed before
    # recommending it -- see tools.py. `finding_id` is the specific finding
    # row this suggestion is tied to (when there is one), so coach.py can
    # rank by THIS suggestion's actual severity instead of parsing prose --
    # see docs/CLAUDE_CURSOR_DEBATE.md, Part B.3.


# Paths (from gobuster/ffuf) that are worth flagging as an immediate next
# move rather than "keep brute-forcing" -- these are the classic first
# places a beginner should actually look, not just enumerate further.
_INTERESTING_PATH_MARKERS = (
    "admin", "login", "backup", "upload", "wp-admin", ".git",
    "phpmyadmin", "config", "dashboard", "panel", "api",
)


# Rules are (predicate, builder) pairs, checked per-finding. Each rule
# looks at one finding and, if it applies, returns a Suggestion. Keeping
# these as small independent functions (rather than one giant branching
# mess) makes it cheap to add a new service/tool later without touching
# the ones that already work.


def _effective_host(finding: sqlite3.Row, fallback_host: str | None) -> str:
    """Host for a generated command. Gobuster (and some other parsers)
    often leave `finding.host` empty -- fall back to the box target, then
    `$TARGET`, never the unusable literal `<target>`."""
    return (finding["host"] or fallback_host or "$TARGET").strip() or "$TARGET"


def _curl_command(host: str | None, path: str | None, fallback_host: str | None) -> str:
    """Build a curl command that is actually runnable.

    Gobuster stores `/admin` with host often NULL. ffuf often stores a
    full URL in `path`. Blind `{host}{path}` concatenation produced
    `curl -i <target>/admin` or `curl -i targethttp://…/admin`."""
    raw = (path or "").strip()
    if raw.startswith(("http://", "https://")):
        return f"curl -i {raw}"

    h = (host or fallback_host or "$TARGET").strip().rstrip("/") or "$TARGET"
    suffix = raw if raw.startswith("/") else (f"/{raw}" if raw else "")
    if h.startswith(("http://", "https://")):
        return f"curl -i {h}{suffix}"
    return f"curl -i http://{h}{suffix}"


def _suggest_for_finding(
    finding: sqlite3.Row,
    already_suggested: set[str],
    fallback_host: str | None = None,
    known_domain: str | None = None,
) -> Suggestion | None:
    kind = finding["kind"]
    if kind == "port":
        return _suggest_for_port(finding, already_suggested, fallback_host, known_domain)
    if kind == "path":
        return _suggest_for_path(finding, already_suggested, fallback_host)
    if kind == "share":
        return _suggest_for_share(finding, already_suggested, fallback_host)
    if kind == "user":
        return _suggest_for_user(finding, already_suggested)
    if kind == "header":
        return _suggest_for_header(finding, already_suggested)
    if kind == "vuln":
        return _suggest_for_vuln(finding, already_suggested, fallback_host)
    if kind == "ad_domain_controller":
        return _suggest_for_ad_dc(finding, already_suggested, fallback_host)
    if kind == "ldap_anon":
        return _suggest_for_ldap_anon(finding, already_suggested, fallback_host)
    return None


def _suggest_for_port(
    finding: sqlite3.Row,
    already_suggested: set[str],
    fallback_host: str | None = None,
    known_domain: str | None = None,
) -> Suggestion | None:
    service = (finding["service"] or "").lower()
    product = (finding["product"] or "").lower()
    detail = (finding["detail"] or "").lower()
    port = finding["port"]
    host = _effective_host(finding, fallback_host)

    def fresh(command: str) -> str | None:
        """Return the command if it hasn't been suggested for this box
        yet, else None — avoids nagging with the same suggestion every
        time a new unrelated port is parsed."""
        return command if command not in already_suggested else None

    # HTTP/HTTPS: directory brute-force is always the next move.
    if service in ("http", "https", "http-proxy", "http-alt") or "apache" in product or "nginx" in product:
        scheme = "https" if service == "https" else "http"
        cmd = fresh(
            f"gobuster dir -u {scheme}://{host}:{port} "
            f"-w /usr/share/wordlists/dirb/common.txt -x php,txt,html"
        )
        if cmd:
            return Suggestion(
                phase="enum",
                command=cmd,
                rationale=(
                    f"Port {port} is serving HTTP — directory brute-forcing "
                    "is the standard next step to find hidden admin panels, "
                    "backups, or API routes before anything else."
                ),
                nudge=(
                    f"Port {port} is a web service. Web services usually have "
                    "more hiding on them than what's visible on the surface — "
                    "what kind of tool finds things that aren't linked anywhere?"
                ),
                required_tool="gobuster",
                finding_id=finding["id"],
            )

    # SMB: enumerate shares/users before anything else.
    if service in ("microsoft-ds", "netbios-ssn") or "samba" in product:
        cmd = fresh(f"enum4linux-ng -A {host}")
        if cmd:
            return Suggestion(
                phase="enum",
                command=cmd,
                rationale=(
                    f"Port {port} is SMB — enum4linux-ng pulls shares, users, "
                    "groups, and OS info in one pass, often without needing "
                    "credentials at all."
                ),
                nudge=(
                    f"Port {port} is a Windows file-sharing service. These "
                    "often leak information about shares and users to anyone "
                    "who asks, no login required — what would you check first?"
                ),
                required_tool="enum4linux-ng",
                finding_id=finding["id"],
            )

    # FTP: if nmap's own script output already confirmed anonymous
    # login works, don't insult the operator by suggesting they go
    # check for it -- suggest the actual next move (list/get) instead.
    # This is a "free win" per docs/CLAUDE_CURSOR_DEBATE.md Hole C: the
    # finding already has this fact in `detail`, ignoring it in favor of
    # a generic check is Trinity looking dumber than it actually is.
    if service == "ftp" and "anonymous ftp login allowed" in detail:
        cmd = fresh(f"ftp {host}  # login as anonymous, then: ls -la && get any interesting files")
        if cmd:
            return Suggestion(
                phase="enum",
                command=cmd,
                rationale=(
                    f"Port {port}'s nmap scripts already confirmed anonymous FTP "
                    "login works — don't re-check it, go straight to listing and "
                    "pulling whatever files are there."
                ),
                nudge=(
                    f"Port {port} already told you something useful in the scan "
                    "output itself, not just in what's open — what did the script "
                    "output say, and what's the obvious next action given that?"
                ),
                required_tool="ftp",
                finding_id=finding["id"],
            )

    # FTP: check anonymous login before anything else.
    if service == "ftp":
        cmd = fresh(f"ftp {host}")
        if cmd:
            return Suggestion(
                phase="enum",
                command=cmd,
                rationale=(
                    f"Port {port} is FTP — always worth a quick anonymous "
                    "login check (username 'anonymous', any password) "
                    "before assuming credentials are needed."
                ),
                nudge=(
                    f"Port {port} is a file-transfer service. Some file-"
                    "transfer servers let absolutely anyone log in without "
                    "a real account — is that worth ruling out first?"
                ),
                required_tool="ftp",
                finding_id=finding["id"],
            )

    # SSH: no active enum step (brute-forcing SSH isn't a sane default
    # suggestion), but flag it for version-based exploit research.
    if service == "ssh":
        cmd = fresh(f"searchsploit {product or 'openssh'} {finding['version'] or ''}".strip())
        if cmd:
            return Suggestion(
                phase="recon",
                command=cmd,
                rationale=(
                    f"Port {port} is SSH — checking the exact version against "
                    "the local exploit database is worth doing early, even "
                    "though SSH itself is rarely the first foothold."
                ),
                nudge=(
                    f"Port {port} is a remote-login service. Its exact "
                    "version number is visible in the scan — is that version "
                    "worth checking against anything?"
                ),
                required_tool="searchsploit",
                finding_id=finding["id"],
            )

    # Kerberos: AS-REP roast check. Needs a domain name (from ldap-rootdse
    # / the synthetic ad_domain_controller finding) — Impacket's
    # invocation is `GetNPUsers.py <domain>/ ...`. Verified against
    # Impacket examples/GetNPUsers.py and swisskyrepo Internal All The
    # Things: `GetNPUsers.py <domain>/ -usersfile ... -no-pass`.
    if (port == 88 or service in ("kerberos-sec", "kerberos")) and known_domain:
        cmd = fresh(
            f"GetNPUsers.py {known_domain}/ -usersfile users.txt -no-pass -dc-ip {host}"
        )
        if cmd:
            return Suggestion(
                phase="enum",
                command=cmd,
                rationale=(
                    f"Port {port} is Kerberos and the domain is {known_domain} — "
                    "check for accounts that don't require pre-authentication "
                    "(AS-REP roasting) before you have any credentials."
                ),
                nudge=(
                    f"Port {port} is how Windows domains handle login tickets. "
                    "Some accounts skip a safety check and will hand you a "
                    "crackable blob if you just know their name — worth trying "
                    "before you have a password."
                ),
                required_tool="",
                finding_id=finding["id"],
            )

    return None


def _suggest_for_path(
    finding: sqlite3.Row, already_suggested: set[str], fallback_host: str | None = None,
) -> Suggestion | None:
    """A gobuster/ffuf hit worth looking at directly, not just noting
    and continuing to brute-force. Hole C item: parsers already store
    these as kind='path'; before this rule existed, they were parsed
    and then never fed back into 'what next'."""
    path = (finding["path"] or "").lower()
    status = finding["status_code"]

    if status not in (200, 301, 302, 401, 403) and status is not None:
        return None
    if not any(marker in path for marker in _INTERESTING_PATH_MARKERS):
        return None

    cmd = _curl_command(finding["host"], finding["path"], fallback_host)
    if cmd in already_suggested:
        return None
    return Suggestion(
        phase="foothold",
        command=cmd,
        rationale=(
            f"'{finding['path']}' (status {status}) looks like an admin/login/"
            "backup-shaped path, not just a generic hit — open it, look at any "
            "forms, and try default credentials before brute-forcing more paths."
        ),
        nudge=(
            "One of the paths you found has a name that suggests it does "
            "something, not just serves a page — what would you normally "
            "check on a path like that?"
        ),
        required_tool="",
        finding_id=finding["id"],
    )


def _suggest_for_share(
    finding: sqlite3.Row, already_suggested: set[str], fallback_host: str | None = None,
) -> Suggestion | None:
    """An SMB share enum4linux-ng found -- list/mount it, don't just
    note its name and move on."""
    host = _effective_host(finding, fallback_host)
    share = finding["path"] or "?"
    cmd = f"smbclient //{host}/{share} -N"
    if cmd in already_suggested:
        return None
    return Suggestion(
        phase="enum",
        command=cmd,
        rationale=(
            f"You have a share name ('{share}') from enum4linux-ng — list its "
            "contents (and try a null/anonymous session first) rather than "
            "just noting it exists."
        ),
        nudge=(
            "You found a shared folder's name. Folders like that usually let "
            "you look inside without needing a password first — worth trying?"
        ),
        required_tool="",
        finding_id=finding["id"],
    )


def _suggest_for_user(finding: sqlite3.Row, already_suggested: set[str]) -> Suggestion | None:
    """Usernames enum4linux-ng found. Deliberately does NOT default to
    a brute-force tool (hydra etc.) as the suggested command -- per
    docs/CLAUDE_CURSOR_DEBATE.md's carried-over caution, that's a much
    bigger step than "note these down," and Trinity shouldn't nudge a
    beginner toward brute-forcing as a default move."""
    detail = finding["detail"] or "a username"
    cmd = f"# noted: {detail} — try it against SSH/FTP logins you find, or as an SMB null-session identity"
    if cmd in already_suggested:
        return None
    return Suggestion(
        phase="enum",
        command=cmd,
        rationale=(
            f"enum4linux-ng found {detail}. Keep a running list of usernames — "
            "they matter later for SSH/FTP login attempts or privilege "
            "escalation, even though there's no single command to run on one "
            "alone right now."
        ),
        nudge=(
            "You now know at least one real account name on this box. That's "
            "not immediately actionable by itself, but it's worth writing down "
            "— why might a username matter later?"
        ),
        required_tool="",
        finding_id=finding["id"],
    )


def _suggest_for_header(finding: sqlite3.Row, already_suggested: set[str]) -> Suggestion | None:
    """whatweb-detected product+version -- feed it to searchsploit, the
    same way the SSH port rule does, instead of letting it sit unused."""
    product = finding["product"]
    version = finding["version"] or ""
    if not product:
        return None
    cmd = f"searchsploit {product} {version}".strip()
    if cmd in already_suggested:
        return None
    label = f"{product} {version}".strip()
    return Suggestion(
        phase="recon",
        command=cmd,
        rationale=(
            f"whatweb identified '{label}' — "
            "checking the exact product/version against the local "
            "exploit database is a quick, free next step."
        ),
        nudge=(
            "whatweb told you exactly what software (and often the version) "
            "the site is running. That's the kind of specific detail worth "
            "checking against something — what?"
        ),
        required_tool="searchsploit",
        finding_id=finding["id"],
    )


def _suggest_for_vuln(
    finding: sqlite3.Row, already_suggested: set[str], fallback_host: str | None = None,
) -> Suggestion | None:
    """A nikto-flagged vuln (directory indexing, outdated software
    notice, etc.) -- go look at the specific path nikto flagged."""
    path = finding["path"]
    if not path:
        return None
    cmd = _curl_command(finding["host"], path, fallback_host)
    if cmd in already_suggested:
        return None
    return Suggestion(
        phase="enum",
        command=cmd,
        rationale=(
            f"nikto flagged '{path}': {finding['detail'] or 'see nikto output'}. "
            "Worth looking at directly rather than letting it sit in a scan log."
        ),
        nudge=(
            "One of your scanners already called out something specific and "
            "unusual about a path, not just a generic finding — go see it for "
            "yourself."
        ),
        required_tool="",
        finding_id=finding["id"],
    )


_DOMAIN_IN_DETAIL_RE = re.compile(r"domain:\s*([A-Za-z0-9.-]+)", re.IGNORECASE)


def _normalize_extracted_domain(name: str) -> str:
    """Strip nmap's LDAP version-probe suffix.

    nmap 7.80+ often prints `Domain: cicada.htb0.` (literal zero plus a
    trailing dot after the real DNS name) in LDAP service extrainfo.
    Verified against 0xdf Sauna / Cicada / Blackfield / Support banners
    (`EGOTISTICAL-BANK.LOCAL0.`, `cicada.htb0.`, `BLACKFIELD.local0.`,
    `support.htb0.`). A real `active.htb` banner is left alone.
    """
    cleaned = name.rstrip(".")
    if cleaned.endswith("0") and "." in cleaned[:-1]:
        return cleaned[:-1]
    return cleaned


def _domain_from_findings(findings: list[sqlite3.Row]) -> str | None:
    """Domain DNS name already recorded on this box (ad_domain_controller
    or ldap_anon detail). Needed so the Kerberos port rule can build a
    real GetNPUsers.py command without inventing a parallel data model."""
    for row in findings:
        detail = row["detail"] or ""
        match = _DOMAIN_IN_DETAIL_RE.search(detail)
        if match:
            return _normalize_extracted_domain(match.group(1))
    return None


def _dn_from_dns(domain: str) -> str:
    return ",".join(f"DC={p}" for p in domain.split("."))


def _suggest_for_ad_dc(
    finding: sqlite3.Row, already_suggested: set[str], fallback_host: str | None = None,
) -> Suggestion | None:
    """AD/DC signature detected → anonymous LDAP RootDSE check. Highest-
    value no-cred first step on a domain-flavored box."""
    host = _effective_host(finding, fallback_host)
    cmd = f"ldapsearch -x -H ldap://{host} -s base namingcontexts"
    if cmd in already_suggested:
        return None
    return Suggestion(
        phase="enum",
        command=cmd,
        rationale=(
            "This host looks like a domain controller — an anonymous LDAP "
            "bind against the RootDSE is the standard first AD enum step "
            "and often returns the domain name for free."
        ),
        nudge=(
            "This box is not a single machine sitting alone: it is answering "
            "like the phone book for a Windows network. The usual first "
            "question is whether that phone book talks to strangers."
        ),
        required_tool="ldapsearch",
        finding_id=finding["id"],
    )


def _suggest_for_ldap_anon(
    finding: sqlite3.Row, already_suggested: set[str], fallback_host: str | None = None,
) -> Suggestion | None:
    """Anonymous bind already succeeded — enumerate users next.
    ldapsearch kept (same tool family as the RootDSE check) rather than
    introducing netexec, which isn't in tools.py. Cite: yunolay.com LDAP
    enumeration; Forest writeups dump users with
    `(objectClass=user)` / sAMAccountName after the naming context is known.
    """
    host = _effective_host(finding, fallback_host)
    detail = finding["detail"] or ""
    match = _DOMAIN_IN_DETAIL_RE.search(detail)
    if not match:
        return None
    domain = match.group(1)
    base = _dn_from_dns(domain)
    if not base:
        return None
    cmd = (
        f"ldapsearch -x -H ldap://{host} -b '{base}' "
        "'(objectClass=user)' sAMAccountName"
    )
    if cmd in already_suggested:
        return None
    return Suggestion(
        phase="enum",
        command=cmd,
        rationale=(
            f"Anonymous LDAP already worked and the domain is {domain} — "
            "pull usernames next; they feed AS-REP roasting and later logins."
        ),
        nudge=(
            "The directory already answered without a login. The useful "
            "follow-up is a list of account names, not another port scan."
        ),
        required_tool="ldapsearch",
        finding_id=finding["id"],
    )


def suggest_next_commands(conn: sqlite3.Connection, box_id: int, limit: int = 10) -> list[Suggestion]:
    """Look at every finding recorded for a box and propose next commands,
    skipping anything already suggested for this box (checked against the
    suggestions table, not just this call) so repeated parses don't spam
    the same advice on every run.

    If the box has a target set (the wizard asks for one up front), any
    occurrence of that exact target string in a generated command is
    rewritten to `$TARGET` -- per docs/CLAUDE_CURSOR_DEBATE.md's 2.13:
    the wizard tells the operator to `export TARGET=<ip>` once, so
    printed commands stop baking a specific IP into every suggestion
    (which also means share-export stops leaking engagement IPs in
    command strings for free, since suggestions are stored post-rewrite)."""
    already = {
        row["command"]
        for row in conn.execute(
            "SELECT command FROM suggestions WHERE box_id = ?", (box_id,)
        ).fetchall()
    }

    box_row = conn.execute("SELECT target FROM boxes WHERE id = ?", (box_id,)).fetchone()
    target = box_row["target"] if box_row else None

    findings = conn.execute(
        "SELECT * FROM findings WHERE box_id = ?", (box_id,)
    ).fetchall()
    known_domain = _domain_from_findings(findings)

    suggestions: list[Suggestion] = []
    for finding in findings:
        suggestion = _suggest_for_finding(
            finding, already, fallback_host=target, known_domain=known_domain,
        )
        if suggestion:
            if target and target in suggestion.command:
                suggestion.command = suggestion.command.replace(target, "$TARGET")
            already.add(suggestion.command)  # don't suggest the same thing twice in one call either
            suggestions.append(suggestion)
        if len(suggestions) >= limit:
            break

    return suggestions

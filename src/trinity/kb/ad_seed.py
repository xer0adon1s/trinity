"""Hand-curated AD/domain KB entries. Sibling of kb/seed.py — not merged
into that file. Only misconfig-shaped items with no clean CVE /
searchsploit mapping (docs/AD_ENGINE_PROTOTYPE_PROJECT.md §5).

Wording deliberately avoids the token "domain" — nmap names port 53
`service=domain` (DNS), and FTS would otherwise cross-match these
entries onto a DNS port. Found live against the Forest fixture.
"""
from __future__ import annotations

import sqlite3

SEED_ENTRIES = [
    {
        "source": "user_curated",
        "title": "LDAP open on a domain controller — worth checking for anonymous bind",
        "summary": (
            "An open LDAP port on a DC does NOT by itself mean anonymous "
            "bind works — that has to actually be tested. When it does "
            "work, an unauthenticated query (RootDSE namingContexts, or "
            "a user dump with -x and no bind DN) is a misconfiguration, "
            "not a CVE, so searchsploit won't have a matching exploit. "
            "If the check below succeeds, dump users/groups/computers "
            "next and feed the names into AS-REP roasting."
        ),
        "detail": (
            "Check with: `ldapsearch -x -H ldap://<target> -s base namingcontexts` "
            "— if that returns real naming contexts (not an error), THEN try "
            "`ldapsearch -x -H ldap://<target> -b '<DC=...>' "
            "'(objectClass=user)' sAMAccountName` to dump users."
        ),
        "match_service": "ldap",
        "match_version": None,
        "tags": "ad,ldap,anonymous,misconfiguration",
        "severity": "medium",
    },
    {
        "source": "user_curated",
        "title": "Kerberos open — worth checking for AS-REP roastable accounts",
        "summary": (
            "An open Kerberos port does NOT by itself mean any account "
            "has 'Do not require Kerberos preauthentication' set — most "
            "domains have zero such accounts. This is worth checking, "
            "not something already confirmed. IF a roastable account "
            "exists, GetNPUsers.py will hand back a $krb5asrep$ blob "
            "encrypted to that account's password with no credentials "
            "needed first — a per-account misconfig, not a product CVE, "
            "so there's nothing for searchsploit to find either way."
        ),
        "detail": (
            "Check with: `GetNPUsers.py <realm>/ -usersfile <users.txt> -no-pass "
            "-dc-ip <target>`. An empty/error result means no roastable "
            "accounts exist on this domain — that's a normal, common "
            "outcome, not a sign the check failed. If it DOES return a "
            "hash, crack offline with hashcat -m 18200. No hash is "
            "stored by Trinity; run the cracker yourself."
        ),
        "match_service": "kerberos-sec",
        "match_version": None,
        "tags": "ad,kerberos,asrep,misconfiguration",
        "severity": "medium",
    },
]


def seed(conn: sqlite3.Connection) -> int:
    """Insert AD seed KB entries if not already present (idempotent by
    title). Same insert path as kb/seed.py, separate file so the
    Linux/Windows starter set stays untouched."""
    inserted = 0
    for entry in SEED_ENTRIES:
        exists = conn.execute(
            "SELECT 1 FROM kb_entries WHERE title = ?", (entry["title"],)
        ).fetchone()
        if exists:
            continue
        conn.execute(
            """
            INSERT INTO kb_entries
                (source, title, summary, detail, match_service, match_version, tags, severity)
            VALUES (:source, :title, :summary, :detail, :match_service, :match_version, :tags, :severity)
            """,
            entry,
        )
        inserted += 1
    conn.commit()
    return inserted

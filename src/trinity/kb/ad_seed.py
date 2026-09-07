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
        "title": "Anonymous LDAP bind on an Active Directory DC",
        "summary": (
            "The DC answered an unauthenticated LDAP query (RootDSE "
            "namingContexts or a user dump with -x and no bind DN). "
            "That is a misconfiguration, not a CVE — searchsploit will "
            "not have a matching exploit. Dump users/groups/computers "
            "next and feed the names into AS-REP roasting."
        ),
        "detail": (
            "Try: `ldapsearch -x -H ldap://<target> -s base namingcontexts` "
            "then `ldapsearch -x -H ldap://<target> -b '<DC=...>' "
            "'(objectClass=user)' sAMAccountName`."
        ),
        "match_service": "ldap",
        "match_version": None,
        "tags": "ad,ldap,anonymous,misconfiguration",
        "severity": "medium",
    },
    {
        "source": "user_curated",
        "title": "AS-REP roasting (Kerberos pre-auth disabled)",
        "summary": (
            "An account with 'Do not require Kerberos preauthentication' "
            "set will hand out an AS-REP encrypted to its password "
            "without proving you know that password first. Offline-crack "
            "the $krb5asrep$ blob. This is a per-account misconfig, not "
            "a product CVE."
        ),
        "detail": (
            "Try: `GetNPUsers.py <realm>/ -usersfile <users.txt> -no-pass "
            "-dc-ip <target>`. Crack with hashcat -m 18200. No hash is "
            "stored by Trinity; run the cracker yourself."
        ),
        "match_service": "kerberos-sec",
        "match_version": None,
        "tags": "ad,kerberos,asrep,misconfiguration",
        "severity": "high",
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

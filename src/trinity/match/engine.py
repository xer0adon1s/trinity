"""The match engine: given a Finding, check the local KB before ever
considering an LLM. This is the whole point of Trinity — most findings
should resolve instantly and for free, right here.
"""
from __future__ import annotations

import re
import sqlite3

from pydantic import BaseModel

from trinity.kb import searchsploit
from trinity.kb.severity import rate_severity
from trinity.parsers.nmap import Finding


class KBMatch(BaseModel):
    kb_id: int | None = None          # None for live searchsploit results
    title: str
    summary: str
    detail: str | None = None
    source: str
    score: float
    severity: str = "medium"          # heuristic unless the entry carries a
                                       # real CVSS score (see kb.severity)


def match_finding(conn: sqlite3.Connection, finding: Finding, limit: int = 5) -> list[KBMatch]:
    """Search the local KB for entries relevant to a finding.

    Two-stage: cheap exact filter on service/version first (near-free),
    then full-text search over title/summary/detail/tags for anything
    that survives or has no exact service match. FTS5's bm25() gives a
    relevance score — lower is better, so we invert it for a friendlier
    "higher is better" score.
    """
    matches: list[KBMatch] = []
    seen_ids: set[int] = set()

    # Stage 1: exact-ish service match — cheapest, most confident signal.
    if finding.service or finding.product:
        candidates = [finding.service, finding.product]
        candidates = [c for c in candidates if c]
        placeholders = ",".join("?" for _ in candidates)
        rows = conn.execute(
            f"""
            SELECT id, title, summary, detail, source, severity, tags
            FROM kb_entries
            WHERE match_service IN ({placeholders})
            """,
            candidates,
        ).fetchall()

        for row in rows:
            # Version match bumps confidence; a version-agnostic entry
            # still surfaces, just ranked lower. But when the KB entry
            # IS version-specific (match_version is set -- e.g. the
            # vsftpd 2.3.4 backdoor), it must not surface at all unless
            # the finding's version actually contains it -- found live
            # during the 2026-09-07 AD/Windows simulation exercise:
            # this entry was firing a false CRITICAL "vsftpd backdoor"
            # hit against Netmon's `Microsoft ftpd` (no version at all)
            # purely because both share match_service='ftp'. A
            # version-specific KB entry making a claim about an EXACT
            # version is fundamentally different from a
            # version-agnostic one describing a general service
            # behavior (anonymous login, null session) -- the latter
            # is correctly service-scoped only and must keep firing
            # unconditionally.
            score = 0.9
            entry_version = conn.execute(
                "SELECT match_version FROM kb_entries WHERE id = ?", (row["id"],)
            ).fetchone()
            required_version = entry_version["match_version"] if entry_version else None
            if required_version:
                if not (finding.version and required_version in finding.version):
                    continue
                score = 1.0

            matches.append(
                KBMatch(
                    kb_id=row["id"],
                    title=row["title"],
                    summary=row["summary"],
                    detail=row["detail"],
                    source=row["source"],
                    score=score,
                    severity=row["severity"] or rate_severity(row["title"], row["tags"]),
                )
            )
            seen_ids.add(row["id"])

    # Stage 2: full-text search as a fallback / supplement, using whatever
    # text is available on the finding (service, product, detail).
    query_terms = " ".join(
        filter(None, [finding.service, finding.product, finding.path, finding.detail])
    ).strip()

    if query_terms:
        try:
            rows = conn.execute(
                """
                SELECT kb_entries.id, kb_entries.title, kb_entries.summary,
                       kb_entries.detail, kb_entries.source, kb_entries.severity,
                       kb_entries.tags, kb_entries.match_service,
                       kb_entries.match_version, kb_fts.rank
                FROM kb_fts
                JOIN kb_entries ON kb_entries.id = kb_fts.rowid
                WHERE kb_fts MATCH ?
                ORDER BY rank
                LIMIT ?
                """,
                (_fts_query(query_terms), limit),
            ).fetchall()
        except sqlite3.OperationalError:
            # Malformed FTS query (rare, e.g. stray punctuation) — skip
            # full-text stage rather than blow up the whole match call.
            rows = []

        for row in rows:
            if row["id"] in seen_ids:
                continue
            # A service-scoped KB entry (match_service set) must not
            # FTS-attach to a finding from a DIFFERENT, known service --
            # e.g. an LDAP-scoped "anonymous bind" entry cross-matching
            # an Anonymous-FTP finding purely because both texts contain
            # the word "anonymous" (HTB Netmon, found during the AD
            # simulation exercise). Only gates when BOTH sides are known
            # and disagree; a finding with no service at all (e.g. a
            # synthetic ldap_anon/asrep_hash finding) still gets FTS.
            scoped_service = (row["match_service"] or "").lower()
            found_service = (finding.service or "").lower()
            if scoped_service and found_service and scoped_service != found_service:
                continue
            # Same version-required rule as stage 1, applied here too --
            # a version-specific entry (vsftpd 2.3.4) that correctly got
            # skipped by stage 1's exact-service filter for lacking a
            # version match must not sneak back in here via FTS just
            # because its own tags/title happen to contain its
            # service name as a token (e.g. tag "ftp" on the vsftpd
            # entry matching an unrelated "Microsoft ftpd" finding's
            # FTS query of "ftp"/"ftpd"). Same HTB Netmon bug, same
            # fix, second stage.
            required_version = row["match_version"]
            if required_version and not (finding.version and required_version in finding.version):
                continue
            matches.append(
                KBMatch(
                    kb_id=row["id"],
                    title=row["title"],
                    summary=row["summary"],
                    detail=row["detail"],
                    source=row["source"],
                    score=0.6,
                    severity=row["severity"] or rate_severity(row["title"], row["tags"]),
                )
            )
            seen_ids.add(row["id"])

    matches.sort(key=lambda m: m.score, reverse=True)

    # Stage 3: live searchsploit lookup. Always runs when there's a
    # product+version to query — a specific, version-matched exploit from
    # ExploitDB is more actionable than a generic KB entry, so this isn't
    # gated on "nothing found yet." searchsploit's mirror is much larger
    # than Trinity's own curated KB and needs no network call, so it's
    # cheap insurance either way, run before ever considering AI escalation.
    #
    # Also queries any MS-bulletin ID found in the finding's OWN detail
    # text (e.g. nmap's `smb-vuln-ms17-010`/`smb-vuln-ms08-067` NSE
    # scripts print "VULNERABLE... (ms17-010)" directly in their output)
    # -- found missing during a Linux/Windows box simulation exercise:
    # nmap had already confirmed EternalBlue/MS08-067 by name in its own
    # script output, searchsploit genuinely has the matching exploits
    # locally (`searchsploit ms17-010` returns real, verified results),
    # but the old code only ever queried product+version, so a
    # product-less/version-less SMB finding with the answer already
    # sitting in `detail` got nothing. A raw CVE id (e.g.
    # "CVE-2017-0143") is deliberately NOT queried here -- searchsploit's
    # own index is keyed off exploit titles/MS-bulletin references, not
    # CVE numbers, so a bare CVE query reliably returns nothing.
    seen_ss_keys: set[tuple[str, str]] = {(m.title, m.detail or "") for m in matches}
    search_calls: list[list[str]] = []
    if finding.product:
        search_calls.append(_searchsploit_query_terms(finding.product, finding.version))
    if finding.detail:
        # One searchsploit invocation per bulletin. searchsploit ANDs
        # its argv terms, so feeding [ms08-067, ms17-010] as a single
        # query (Legacy: nmap's smb-vuln-* scripts report BOTH on the
        # same port 445 finding) returns zero hits even though each
        # term alone has verified local exploits. Same "which queries
        # get asked" shape as the MS-bulletin extraction itself — do
        # not AND distinct bulletin IDs together.
        for bulletin in _ms_bulletin_terms(finding.detail):
            search_calls.append([bulletin])
    # Path findings (gobuster/ffuf) never populate .product — they're a
    # URL path, not a service banner — so a product-shaped last segment
    # like /nibbleblog/ used to never reach searchsploit even when
    # ExploitDB already had the matching exploit locally. Same shape as
    # the MS-bulletin extraction above: pull a real token out of the
    # finding and query it; do not guess. Generic web segments (admin,
    # login, images, ...) are skipped so this does not noise /admin/.
    if finding.kind == "path" and finding.path:
        path_terms = _path_product_terms(finding.path)
        if path_terms:
            search_calls.append(path_terms)

    for query_terms_ss in search_calls:
        for result in searchsploit.search(*query_terms_ss):
            key = (result.title, f"PoC: {result.path}" if result.path else "")
            if key in seen_ss_keys:
                continue
            seen_ss_keys.add(key)
            matches.append(
                KBMatch(
                    kb_id=None,
                    title=result.title,
                    summary=(
                        f"Found in local ExploitDB (EDB-ID {result.edb_id})"
                        + (f", {result.codes}" if result.codes else "")
                        + (". Verified working." if result.verified else ".")
                    ),
                    detail=f"PoC: {result.path}" if result.path else None,
                    source="searchsploit",
                    score=0.95 if result.verified else 0.8,
                    severity=rate_severity(result.title, result.codes),
                )
            )
    matches.sort(key=lambda m: m.score, reverse=True)

    return matches[:limit]


# Matches nmap NSE vuln-script naming (`smb-vuln-ms17-010`) as well as
# bare mentions in script output text ("...(ms17-010)", "(MS08-067)").
_MS_BULLETIN_RE = re.compile(r"ms(\d{2})-(\d{3})", re.IGNORECASE)


# Last path segment must look like a product/app name, not a generic
# web path: start with a letter, then letters/digits/hyphens, length >= 4.
_PRODUCT_SHAPED_SEGMENT = re.compile(r"^[A-Za-z][A-Za-z0-9-]{3,}$")

# Generic path segments that must never be sent to searchsploit. Starts
# from suggest/engine.py's _INTERESTING_PATH_MARKERS (those are "worth
# curling" for recon, not product names for ExploitDB) plus common web
# junk that a naive last-segment query would otherwise fire on.
_GENERIC_PATH_SEGMENTS = frozenset({
    # _INTERESTING_PATH_MARKERS in suggest/engine.py
    "admin", "login", "backup", "upload", "wp-admin", ".git",
    "phpmyadmin", "config", "dashboard", "panel", "api",
    # generic web junk
    "images", "css", "js", "static", "assets", "index", "files",
    "img", "includes", "fonts", "vendor", "public", "tmp", "www",
    "html", "php", "txt", "icons", "media",
    # obvious extra generic web paths — not product names
    "cgi-bin", "cgi",
    # seen live during coverage-sim: /themes/ on pfSense (Sense) became
    # `searchsploit themes` and returned unrelated WordPress theme
    # exploits. Same class as images/css/static.
    "themes", "javascript", "classes", "widgets",
    # coverage-sim: these last segments are product-shaped but are
    # common English / brand words. Live they became `searchsploit fuel`
    # → Franklin Fueling (THM Ignite Fuel CMS), `searchsploit simple` →
    # AnalogX SimpleServer (THM Simple CTF / CMS Made Simple),
    # `searchsploit internal` → antivirus noise (THM Vulnversity),
    # `searchsploit music`/`artwork` → music-store SQLi (HTB OpenAdmin),
    # `searchsploit askjeeves` → Ask.com toolbar (HTB Jeeves / Jenkins).
    # Same class as themes: skip the bad query; do not invent a better one.
    "fuel", "simple", "internal", "music", "artwork", "askjeeves",
})


def _path_product_terms(path: str) -> list[str]:
    """Extract a product-shaped last path segment for searchsploit.

    `/nibbleblog/` -> `['nibbleblog']`. `/admin/`, `/login/`, `/images/`,
    and short/punctuation-y segments return no terms. Same contract as
    `_ms_bulletin_terms`: extract a real token already present on the
    finding, or return empty — never invent a query.
    """
    last = ""
    for segment in reversed(path.split("/")):
        candidate = segment.split("?", 1)[0].strip()
        if candidate:
            last = candidate
            break
    if not last:
        return []
    if last.lower() in _GENERIC_PATH_SEGMENTS:
        return []
    if not _PRODUCT_SHAPED_SEGMENT.match(last):
        return []
    return [last]


def _ms_bulletin_terms(detail: str) -> list[str]:
    """Extract MS-bulletin IDs (e.g. 'ms17-010', 'MS08-067') from a
    finding's detail text -- this is what nmap's smb-vuln-* NSE scripts
    print directly in their output when they confirm a well-known SMB
    RCE, and it's also what searchsploit's own exploit titles are
    actually keyed against (unlike raw CVE numbers, which searchsploit
    rarely indexes on). Deduplicated, order-preserving."""
    seen: set[str] = set()
    terms: list[str] = []
    for match in _MS_BULLETIN_RE.finditer(detail):
        bulletin = f"ms{match.group(1)}-{match.group(2)}".lower()
        if bulletin not in seen:
            seen.add(bulletin)
            terms.append(bulletin)
    return terms


# Tokens that are too generic to mean anything on their own, so ORing
# them in would match almost any KB entry regardless of actual topic --
# found live during a Linux/Windows box simulation exercise: an nmap
# vuln-script hit for MS17-010 (whose own output naturally contains the
# words "CVE", "VULNERABLE", and "in") was cross-matching the unrelated
# vsftpd-backdoor KB entry purely because that entry's title/summary
# also happens to contain "CVE" and "VULNERABLE" -- neither finding has
# anything to do with the other's service. Two categories filtered:
# ordinary English stopwords, and generic security-report vocabulary
# that shows up in nearly every vuln-scan/KB-entry regardless of the
# actual vulnerability (CVE, VULNERABLE, remote, code execution, risk
# ratings, etc). Real distinguishing terms (service/product names, CVE
# NUMBERS, MS-bulletin IDs, port-specific keywords) are untouched.
_FTS_STOPWORDS = frozenset({
    # ordinary English stopwords that leak in from script/detail prose
    "a", "an", "the", "in", "on", "of", "to", "for", "and", "or", "is",
    "are", "be", "by", "with", "this", "that", "it", "as", "at", "via",
    "can", "not", "no", "may", "these", "was", "were", "has", "have",
    # generic security-report vocabulary -- present in almost every
    # vuln-scan/KB-entry regardless of the SPECIFIC vulnerability, so
    # matching on these alone is noise, not signal
    "cve", "vulnerable", "vulnerability", "vulnerabilities", "remote",
    "code", "execution", "risk", "factor", "high", "medium", "low",
    "critical", "state", "exists", "allows", "attacker", "attackers",
    "crafted", "server", "servers", "service", "system", "version",
    "windows", "microsoft",
})


def _fts_query(text: str) -> str:
    """Turn free text into a safe FTS5 MATCH query: OR together each
    alphanumeric token so partial term matches still surface results.
    Stopwords and generic security-report vocabulary are dropped first
    (see `_FTS_STOPWORDS`) so a finding's incidental prose (nmap script
    output, generic "VULNERABLE"/"CVE" language) can't cross-match a
    KB entry about a completely unrelated service/vulnerability."""
    raw_tokens = [t for t in "".join(c if c.isalnum() else " " for c in text).split() if t]
    tokens = [t for t in raw_tokens if len(t) >= 3 and t.lower() not in _FTS_STOPWORDS]
    if not tokens:
        return '""'
    return " OR ".join(f'"{t}"' for t in tokens)


# Service daemon suffixes that appear in nmap's product field but confuse
# searchsploit's fuzzy matching (e.g. "Samba smbd" finds nothing, "Samba"
# finds plenty). Stripped, not the whole product string, so genuine
# multi-word products (e.g. "Apache httpd") still search sensibly since
# only known noisy suffixes are removed.
#
# smtpd/pop3d/nntpd/listener found live during coverage-sim: nmap's
# "JAMES smtpd 2.3.2" and "Oracle TNS listener 11.2.0.2.0" AND those
# role words against searchsploit and return zero, while "JAMES 2.3.2"
# / "Oracle TNS" have verified local exploits. Same shape as smbd.
_NOISY_PRODUCT_SUFFIXES = re.compile(
    r"\b(smbd|httpd|daemon|smtpd|pop3d|nntpd|listener)\b",
    re.IGNORECASE,
)

# Multi-word nmap role phrases that are not the product name.
# Found live: "Icecast streaming media server" and
# "Redis key-value store" AND the whole phrase and return zero,
# while `searchsploit Icecast` / `searchsploit Redis` have hits.
_NOISY_PRODUCT_PHRASES = re.compile(
    r"\b(streaming media server|key-value store|remote admin)\b",
    re.IGNORECASE,
)

# Distro/packaging suffixes nmap tacks onto version strings (e.g.
# "3.0.20-Debian", "4.7p1 Debian 8ubuntu1") that searchsploit's search
# doesn't expect — only the leading version number is useful to it.
_VERSION_LEADING_NUMBER = re.compile(r"^[\d.]+[a-z]?\d*")


def _searchsploit_query_terms(product: str, version: str | None) -> list[str]:
    """Clean nmap's product/version strings into terms searchsploit can
    actually match against. nmap's fingerprints are written for humans
    (e.g. "Samba smbd" / "3.0.20-Debian"), not for exact-ish search tools."""
    clean_product = _NOISY_PRODUCT_PHRASES.sub("", product)
    clean_product = _NOISY_PRODUCT_SUFFIXES.sub("", clean_product).strip()
    clean_product = re.sub(r"\s+", " ", clean_product)

    terms = [clean_product] if clean_product else [product]

    if version:
        match = _VERSION_LEADING_NUMBER.match(version.strip())
        if match:
            terms.append(match.group(0))

    return terms

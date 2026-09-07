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
            # still surfaces, just ranked lower.
            score = 0.9
            entry_version = conn.execute(
                "SELECT match_version FROM kb_entries WHERE id = ?", (row["id"],)
            ).fetchone()
            if (
                finding.version
                and entry_version
                and entry_version["match_version"]
                and entry_version["match_version"] in finding.version
            ):
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
                       kb_entries.tags, kb_fts.rank
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
        bulletin_terms = _ms_bulletin_terms(finding.detail)
        if bulletin_terms:
            search_calls.append(bulletin_terms)
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
_NOISY_PRODUCT_SUFFIXES = re.compile(r"\b(smbd|httpd|daemon)\b", re.IGNORECASE)

# Distro/packaging suffixes nmap tacks onto version strings (e.g.
# "3.0.20-Debian", "4.7p1 Debian 8ubuntu1") that searchsploit's search
# doesn't expect — only the leading version number is useful to it.
_VERSION_LEADING_NUMBER = re.compile(r"^[\d.]+[a-z]?\d*")


def _searchsploit_query_terms(product: str, version: str | None) -> list[str]:
    """Clean nmap's product/version strings into terms searchsploit can
    actually match against. nmap's fingerprints are written for humans
    (e.g. "Samba smbd" / "3.0.20-Debian"), not for exact-ish search tools."""
    clean_product = _NOISY_PRODUCT_SUFFIXES.sub("", product).strip()
    clean_product = re.sub(r"\s+", " ", clean_product)

    terms = [clean_product] if clean_product else [product]

    if version:
        match = _VERSION_LEADING_NUMBER.match(version.strip())
        if match:
            terms.append(match.group(0))

    return terms

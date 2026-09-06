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
    if finding.product:
        query_terms_ss = _searchsploit_query_terms(finding.product, finding.version)
        for result in searchsploit.search(*query_terms_ss):
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


def _fts_query(text: str) -> str:
    """Turn free text into a safe FTS5 MATCH query: OR together each
    alphanumeric token so partial term matches still surface results."""
    tokens = [t for t in "".join(c if c.isalnum() else " " for c in text).split() if t]
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

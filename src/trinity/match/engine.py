"""The match engine: given a Finding, check the local KB before ever
considering an LLM. This is the whole point of Trinity — most findings
should resolve instantly and for free, right here.
"""
from __future__ import annotations

import sqlite3

from pydantic import BaseModel

from trinity.parsers.nmap import Finding


class KBMatch(BaseModel):
    kb_id: int
    title: str
    summary: str
    detail: str | None = None
    source: str
    score: float


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
            SELECT id, title, summary, detail, source
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
                       kb_entries.detail, kb_entries.source, kb_fts.rank
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
                )
            )
            seen_ids.add(row["id"])

    matches.sort(key=lambda m: m.score, reverse=True)
    return matches[:limit]


def _fts_query(text: str) -> str:
    """Turn free text into a safe FTS5 MATCH query: OR together each
    alphanumeric token so partial term matches still surface results."""
    tokens = [t for t in "".join(c if c.isalnum() else " " for c in text).split() if t]
    if not tokens:
        return '""'
    return " OR ".join(f'"{t}"' for t in tokens)

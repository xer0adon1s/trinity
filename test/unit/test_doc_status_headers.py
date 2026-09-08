"""Invariant: docs/*.md `Status:` headers use a fixed vocabulary.

The vocabulary describes BUILD state only. Docs that track something
else -- who a work item is assigned to, whether a decision has been
made -- deliberately do not carry a `Status:` line at all (see
`Assignment:` in the project briefs and `Decision status:` in
docs/OPEN_DECISIONS.md); forcing those into DESIGN ONLY/PARTIAL made
them contradict their own body text. This test only constrains
`Status:` lines that exist; it does not require every doc to have one,
and that is on purpose."""
from __future__ import annotations

from pathlib import Path

ALLOWED = {"DESIGN ONLY", "BUILT", "QUARANTINED", "PARTIAL"}
DOCS = Path(__file__).resolve().parents[2] / "docs"


def test_doc_status_headers_use_fixed_vocabulary():
    for path in sorted(DOCS.glob("*.md")):
        for line in path.read_text(encoding="utf-8").splitlines():
            stripped = line.lstrip()
            if not (stripped.startswith("Status:") or stripped.startswith("**Status:**")):
                continue
            raw = stripped.split(":", 1)[1].strip().replace("**", "").strip()
            value = raw.split(".", 1)[0].strip()
            assert value in ALLOWED, f"{path.name}: Status value {value!r} not in {sorted(ALLOWED)}"

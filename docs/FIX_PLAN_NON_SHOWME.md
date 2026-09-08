# Fix plan — everything except Show Me Mode (which is quarantined,
# see docs/SHOW_ME_MODE_QUARANTINE.md)

Status: DRAFT, for Cursor + Claude Code CLI peer review before any
code is assigned or written. Source: the two independent full-program
reviews from 2026-09-07 (`findings/full_review_cursor.md`,
`findings/full_review_claude.md`), items 15-17 plus the "high/medium
priority" items that are NOT Show-Me-specific.

Reviewers: critique this plan. Do NOT write code against it yet. Flag
anything under-scoped, anything that conflicts with a design doc,
anything you'd sequence differently, and anything you think is missing
from the two source reviews that should be folded in here.

## Ground rules for whoever ends up implementing these

- Every fix needs a regression test that would have caught the
  original bug — not just a test that the fix works, but one shaped
  like the actual failure mode found in review (e.g. going through the
  real `approve_candidate` → `build_share_bundle` path, not inserting
  rows directly).
- Full test suite must stay green (currently 463 passing).
- No new dependencies without checking they're actually needed first
  (e.g. for CI/lint, prefer widely-used, low-config tools).
- Small, reviewable commits — one fix per commit where practical, not
  one giant "review fixes" commit.

## Fix 1 — `sharing.py` source-filter regression (P0, small, isolated)

**Problem:** `intake.py`'s `approve_candidate()` was fixed this
session to preserve real provenance (`candidate.source`) instead of
hardcoding `source="ai_escalation"` on every approval. Correct fix —
but `src/trinity/sharing.py:80` and `:104` still hardcode `WHERE
source = 'ai_escalation'` when building share-export bundles. Since
approved Agent Harness/Assimilator/Methods-live-draft entries now
carry their real source, they no longer match this filter and silently
drop out of every share-export — the exact class of entry
`sharing.py`'s own module docstring says it collects.

**Why it wasn't caught:** `test_box_status_and_sharing.py` inserts
rows with `source='ai_escalation'` directly into the DB rather than
going through `submit_candidate()` → `approve_candidate()` →
`build_share_bundle()`, so the test never exercises the real
provenance-preserving path.

**Proposed fix:**
1. Add a shared constant (e.g. `AI_SOURCED = {"ai_escalation",
   "agent_harness", "methods_live_draft", "assimilator"}`) — probably
   lives in `intake.py` next to `VALID_SOURCES` since that's the
   authoritative list of what an AI-sourced entry can be tagged.
2. Change both `sharing.py` filters to `WHERE source IN (...)` using
   that constant (parameterized, not string-interpolated).
3. Add a new test that goes through the REAL path: submit a candidate
   with `source="agent_harness"`, approve it, build a share bundle,
   assert the entry is present. This is the regression test that would
   have caught the original bug.

**Estimated scope:** small, one file + one constant + one new test.

## Fix 2 — CI, linter, type checker (P1, mechanical, no logic changes)

**Problem:** no `.github/` workflow exists — 463 tests run only when
someone remembers to run them locally. No linter (`ruff`) or type
checker (`mypy`) is installed, despite source code already carrying
`# noqa: BLE001`, `# noqa: ANN001`, `# type: ignore[attr-defined]`
annotations for tools that aren't present — those annotations are
currently decorative.

**Proposed fix:**
1. Add `ruff` and `mypy` to `[dependency-groups].dev` in
   `pyproject.toml` (pytest-asyncio is already there from this
   session's TUI test work).
2. Add a `[tool.ruff]` config block. Line length should match the
   house style already in the codebase (most files wrap well under
   100 chars; a few new files run 100-110 — pick a real number by
   sampling the codebase, don't guess).
3. Add a minimal `[tool.mypy]` config. Given the codebase's existing
   annotation discipline (from __future__ import annotations, X | None
   unions everywhere), this should surface real issues, not just noise
   — but expect an initial pass to find some. Scope initial mypy
   strictness conservatively (don't turn on `--strict` day one) so the
   first PR isn't "fix 200 pre-existing type errors."
4. Add a GitHub Actions workflow (`.github/workflows/ci.yml`) running,
   on push/PR: `uv run pytest`, `uv run ruff check`, `uv run mypy src/`.
   Keep it to ~20-30 lines, matching how lean the rest of this
   project's tooling is.
5. Do NOT try to fix every lint/type finding in the same PR that adds
   the tooling — land the tooling first (possibly with a baseline
   ignore file / `# noqa` sweep if ruff finds a lot immediately), then
   fix findings incrementally in follow-up commits so this doesn't
   become an unreviewable mega-diff.

**Open question for reviewers:** should ruff's config be stricter
(catching more categories) or looser (just the basics — unused
imports, undefined names) for a first pass? Recommend starting loose
and tightening once the baseline is clean, but want a second opinion.

## Fix 3 — Docstring drift cleanup (P2, mechanical, no logic changes)

**Problem:** several docstrings/comments describe behavior the code
doesn't actually have, found during the two reviews:

1. `docs/SHOW_ME_MODE.md:3` and `docs/ASSIMILATOR_PROJECT.md:3` still
   say "Status: DESIGN ONLY. Nothing in this document is built yet."
   Both are substantially built (and quarantined, not unbuilt — the
   status line needs a THIRD state now, not just built/unbuilt: see
   `docs/SHOW_ME_MODE_QUARANTINE.md`).
2. `src/trinity/doctor.py`'s module docstring claims "no subprocess
   spawns beyond `shutil.which` checks" — but `run_doctor(include_vpn=True)`
   calls `check_vpp()` which calls `subprocess.run(["ip", "-o", "link",
   "show"], ...)` in `vpn.py`. The docstring even names this probe two
   clauses earlier then denies it in the next sentence.
3. `src/trinity/milestones.py`'s `record_shell()` timeline text is
   hardcoded to say "Declared by the operator. Trinity did not inspect
   any shell history." — this is TRUE for the CLI's `trinity shell
   --as` command (its only caller before this session), but Show Me
   Mode's now-quarantined call into the same function made this text
   false for that caller. Since Show Me Mode is quarantined, this
   isn't urgent, but the underlying function should probably accept an
   optional `source`/`detail` override so it can't silently become
   false again for a future caller.
4. `src/trinity/db.py:27-29`'s comment on `boxes.shell_level` says
   "Never inferred from shell history" — same issue as #3, currently
   true again post-quarantine, but worth strengthening with an
   explicit note about why (points at the quarantine doc) so a future
   session doesn't reintroduce the same violation without reading it.

**Proposed fix:** straightforward text corrections, no logic changes.
Fix #1 and #2 immediately (they're just wrong). For #3/#4, add a code
comment pointing at `docs/SHOW_ME_MODE_QUARANTINE.md` explaining why
`record_shell()`'s hardcoded text is a real invariant to protect, not
just current-callers-happen-to-satisfy-it.

**Estimated scope:** small, several files, no tests needed beyond
maybe asserting the doc status headers use one of a fixed enum of
values (DESIGN ONLY / BUILT / QUARANTINED) if reviewers think that's
worth a lint rule rather than just fixing the text.

## Fix 4 — `assimilator_runs` / `show_me_runs` additive-column safety net (P1, schema-only, no behavior change)

**Problem:** `db.py` documents a real trap: `CREATE TABLE IF NOT
EXISTS` does NOT retroactively add columns to an existing table file,
and the project maintains explicit `_SUGGESTIONS_ADDITIVE_COLUMNS` /
`_BOXES_ADDITIVE_COLUMNS` / `_ENGAGEMENT_ADDITIVE_COLUMNS` lists (wired
into an `_ensure_additive_columns` mechanism) specifically to avoid
this. Neither `assimilator_runs` nor `show_me_runs` has an entry in
that mechanism. They're new tables so they create fine on a fresh
install today — but the Assimilator design doc (`docs/
ASSIMILATOR_PROJECT.md` §7) already specifies 6 more fields
(`fixture_sha`, `precision_check_passed`, `reviewer`, `reviewed_at`,
`fix_commit`, `agent_calls`, `wall_clock_seconds`) that don't exist
yet as columns. The FIRST time one of those is added to the `SCHEMA`
string, it will silently no-op on every existing `~/.trinity/
trinity.db` and the first INSERT naming the new column will fail at
runtime — for exactly the users who've been testing longest.

**Proposed fix:** this is schema/migration hygiene, separate from
actually adding those 6 fields (which is Assimilator feature work, out
of scope here per Alexander's "3-5 later" call from earlier in this
session — the offline batch sweep work). Scope THIS fix narrowly:
1. Add `_ASSIMILATOR_RUNS_ADDITIVE_COLUMNS = []` and
   `_SHOW_ME_RUNS_ADDITIVE_COLUMNS = []` (empty lists — no new columns
   yet) wired into the existing `_ensure_additive_columns` mechanism,
   so the NEXT time a column is added to either table, it's a one-line
   addition to an existing pattern instead of a new bug.
2. Add a test confirming a column added to one of these lists actually
   gets added to an existing DB file (probably already covered by an
   existing parametrized test for the other three additive-column
   lists — check before writing a new one).

**Do NOT** add the 6 missing Assimilator fields themselves in this
pass — that's real feature scope tied to the (deferred) offline batch
sweep, not a bug fix.

## Fix 5 — `check_already_known()` and `assimilator_runs` failure-bucket mapping (P2 — SCOPED OUT for now)

Both of these are Show-Me-Mode-coupled (the only production call site
for `check_already_known` is inside the quarantined `run_show_me()`;
the failure-bucket mapping issue is `show_me.py`'s own logic). **Do
not fix these independently of the Show Me Mode rebuild** — fixing
`check_already_known`'s call site only matters once Show Me Mode's
architecture question is resolved (see quarantine doc). Listed here
only so reviewers don't think they were forgotten; they're correctly
scoped into the Show Me Mode rebuild, not this fix plan.

## What reviewers should NOT scope into this plan

- Anything inside `src/trinity/show_me.py`,
  `src/trinity/tui/show_me_screens.py`, or the Assimilator offline
  batch sweep — all covered by the quarantine doc and Alexander's
  explicit "later" call on items 3-5 from earlier this session.
- New features. This is a bug-fix/hygiene pass only.

## What we want from this review

1. Is the fix-1 (`sharing.py`) plan correct and complete, or is there
   a similar hardcoded-source-filter bug elsewhere in the codebase we
   should catch in the same pass? (Search for other `source =
   'ai_escalation'` or similar hardcoded source-string comparisons.)
2. CI/lint/type-checker scope (Fix 2) — right starting point, or
   would you sequence/scope it differently? Answer the open question
   about ruff strictness.
3. Anything in Fix 3/4 you'd add, remove, or re-prioritize?
4. Any additional non-Show-Me findings from your own original review
   that aren't captured in Fixes 1-4 and should be added here?
5. Given these 4 fixes, how would you split the work across two
   parallel implementers (you and the other reviewer) to minimize
   merge conflicts and review overhead? Propose a split.

Deliverable: a markdown file with your answers, committed to your own
review branch, not merged. Same discipline as the prior review passes
this session.

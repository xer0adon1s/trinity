# Implementation brief — Fix 1 + Fix 4 (Claude Code CLI's half)

This is the CODE-WRITING pass following four rounds of review (two
independent full-program reviews, a peer review of the fix plan, and a
cross-talk round between Cursor and Claude Code CLI). The plan below
is the agreed conclusion of all four rounds -- implement it, don't
re-derive it. Full suite is 463 passing before you start; keep it
green throughout, one commit per logical fix, and follow the ground
rules below exactly.

You own: `src/trinity/sharing.py`, `src/trinity/intake.py`,
`src/trinity/db.py` (ALL of it -- do not let Cursor's branch touch
this file, there is no need since their fixes don't require it),
`test/unit/test_box_status_and_sharing.py`,
`test/unit/test_db_migration.py`.
Do NOT touch: `.github/`, `pyproject.toml`, `docs/*.md`,
`src/trinity/doctor.py`, `src/trinity/assimilator.py`,
`src/trinity/milestones.py`, `src/trinity/tui/` -- Cursor owns those
in a parallel worktree; touching them creates a merge conflict for no
reason.

## Ground rules (from the review, non-negotiable)

1. Every regression test must be OBSERVED FAILING against the
   pre-fix code, and the failure output pasted into the commit
   message. Don't just claim the test "would have caught it" --
   actually run it red first, then make it green.
2. Every commit must pass `uv run pytest -q` standalone (the repo now
   has CI -- `.github/workflows/ci.yml` -- so this will be checked).
3. No new runtime dependencies.
4. Small, reviewable commits, one fix per commit.

## Fix 1 — sharing.py provenance filter (P0)

### The bug
`src/trinity/intake.py`'s `approve_candidate()` was fixed in an
earlier session to preserve real provenance (`candidate.source` --
`agent_harness`, `methods_live_draft`, or `assimilator`) instead of
hardcoding `source="ai_escalation"` on every approval. Correct fix --
but `src/trinity/sharing.py:80` and `:104` still hardcode
`WHERE source = 'ai_escalation'` when building share-export bundles.
Approved Agent Harness / Assimilator / Methods-live-draft entries now
carry their real source and no longer match this filter -- they
silently drop out of every share-export.

### The fix, exactly as agreed
1. Define, in `db.py`, next to the existing schema comments at
   `db.py:120-125`, `:130`, `:226` that already (wrongly) enumerate
   the source vocabulary:
   ```python
   # Sources a command_explanations/error_patterns row can carry.
   # 'ai_escalation' is the direct-write-path default (see
   # explain.py's save_explanation, errors.py's save_error_fix);
   # the other three arrive via intake.py's approve_candidate().
   INTAKE_SOURCES = {"agent_harness", "methods_live_draft", "assimilator"}
   AI_SOURCED = INTAKE_SOURCES | {"ai_escalation"}
   ```
   Fix the three stale comments in the same commit -- they currently
   describe an old 3-value vocabulary (`trinity_preseed`,
   `ai_escalation`, `user_curated`) that doesn't match what
   `command_explanations.source`/`error_patterns.source` can actually
   hold post-intake-fix.
2. In `intake.py`, change `VALID_SOURCES = {...}` to
   `VALID_SOURCES = db.INTAKE_SOURCES` (import `db`, don't duplicate
   the literal) so there's exactly one definition.
3. In `sharing.py`, change both hardcoded filters
   (`WHERE source = 'ai_escalation'`) to parameterized
   `WHERE source IN (?, ?, ?, ?)` (or equivalent) against `db.AI_SOURCED`.
   Use a placeholder-generation helper if one doesn't already exist in
   the file, matching existing style.
4. Also check and fix `docs/AGENT_HARNESS.md:123` if you find it still
   claims approved harness entries land as `ai_escalation` -- actually,
   leave `docs/` alone per the ownership split above; if you spot this,
   just note it in your final summary for Cursor/Doc to fix, don't edit
   `docs/`.
5. Add TWO pinning tests (this is the part that would have caught the
   ORIGINAL bug, not just today's regression):
   ```python
   def test_valid_sources_subset_of_ai_sourced():
       assert intake.VALID_SOURCES <= db.AI_SOURCED

   def test_direct_write_path_defaults_are_ai_sourced():
       import inspect
       from trinity.explain import save_explanation
       from trinity.errors import save_error_fix
       assert inspect.signature(save_explanation).parameters["source"].default in db.AI_SOURCED
       assert inspect.signature(save_error_fix).parameters["source"].default in db.AI_SOURCED
   ```
   (Adjust import paths/signatures to match actual code -- verify
   `save_explanation`/`save_error_fix` really have a `source` kwarg
   with a default; if the real signature differs, adapt the test to
   the same intent: assert the default value is share-exportable.)
6. Add the REAL regression test, going through the actual path (not
   inserting rows directly, which is why the original bug wasn't
   caught): `submit_candidate()` with `source="agent_harness"` →
   `approve_candidate()` → `build_share_bundle()` → assert the entry
   IS present in the bundle. Also assert box-scoping still works (an
   entry from a different box_id must NOT appear), since you're
   touching the WHERE clause.
7. On `kb_entries`: `approve_candidate()` writes `kb_entry` candidates
   into the `kb_entries` table, but `sharing.py`'s `kb_candidates` are
   built from `findings WHERE matched = 0`, never from `kb_entries` --
   so approved `kb_entry` candidates are structurally unreachable by
   share-export regardless of source. This is being treated as
   DELIBERATE ("share the gap, not the answer") per Doc's call --
   add a one-line comment at the `kb_candidates` query in `sharing.py`
   explaining this is intentional, so a future reviewer doesn't
   re-open it. Do NOT change this behavior.

## Fix 4 — additive-column migration safety net (P1 value / P2 urgency)

### The problem
`db.py` documents a real trap: `CREATE TABLE IF NOT EXISTS` does not
retroactively add columns to an existing table file. The project has
`_ensure_additive_columns` (`db.py:416-438`) to guard against this for
`suggestions`/`boxes`/`engagement_meta` -- but it's three HAND-COPIED
blocks (PRAGMA table_info + set comprehension + for loop), not a real
generic mechanism, and the `sqlite_master` existence guard is only
applied to `engagement_meta`. The three tables added by this session's
work (`assimilator_runs` at `db.py:324`, `show_me_runs` at `:363`,
`show_me_attestation` at `:384`) have NO entry in this mechanism.
Since Show Me Mode is quarantined, nothing writes to these tables
right now, so the trap is dormant -- but the first time a column is
added to any of the three (which WILL happen when Show Me Mode is
rebuilt), it will silently no-op on every existing installed DB.

### The fix, exactly as agreed (registry refactor, NOT more copy-paste)
Replace the three hand-copied blocks with one data-driven registry:
```python
_ADDITIVE_COLUMNS: dict[str, list[tuple[str, str]]] = {
    "suggestions": [...],       # move the existing entries here verbatim
    "boxes": [...],             # move the existing entries here verbatim
    "engagement_meta": [...],   # move the existing entries here verbatim
    "assimilator_runs": [],
    "show_me_runs": [],
    "show_me_attestation": [],
}

def _ensure_additive_columns(conn: sqlite3.Connection) -> None:
    for table, columns in _ADDITIVE_COLUMNS.items():
        # uniform sqlite_master existence guard for ALL tables
        # (currently only engagement_meta has this -- apply it to all six)
        exists = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
        ).fetchone()
        if not exists:
            continue
        existing = {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
        for col_name, col_def in columns:
            if col_name not in existing:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {col_name} {col_def}")
```
(Adapt exact syntax to match the real existing code -- read
`db.py:396-438` first and preserve its actual column-list contents for
the three existing tables verbatim; only the MECHANISM changes, not
the data for `suggestions`/`boxes`/`engagement_meta`.)

Critical constraint: `test_db_migration.py`'s existing
`test_connect_adds_missing_suggestion_columns` (`:29-55`) MUST pass
UNCHANGED after this refactor -- if it does, the registry mechanism is
provably equivalent to the old one for the cases it already covered.

Then add a NEW test (the existing test doesn't cover `engagement_meta`
at all, let alone the three new tables) -- ideally parametrized over
`_ADDITIVE_COLUMNS` so it covers all six tables from one test body:
build an old-schema DB missing a column that's in the registry,
`connect()` to it, assert the column now exists.

Do NOT add the 6 additional Assimilator fields
(`fixture_sha`, `precision_check_passed`, etc. from
`docs/ASSIMILATOR_PROJECT.md` §7) as actual columns in this pass --
that's real feature scope tied to Show Me Mode's rebuild, explicitly
out of scope here. The empty lists for the three new tables are
correct AS WRITTEN (empty) for this pass.

## When done

Run `uv run pytest -q` (must show all passing, likely ~465+ with your
2 new tests), commit each fix separately with the pre-fix-failure
evidence in the commit message, and write a short summary of what you
did to `findings/fix1_fix4_implementation_summary.md` on your branch
(`fix1-fix4-claude`). Do NOT merge or push -- Doc will review and merge.

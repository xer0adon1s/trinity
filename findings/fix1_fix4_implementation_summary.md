# Fix 1 + Fix 4 — implementation summary (Claude Code CLI's half)

Branch: `fix1-fix4-claude`. Two commits, one per fix. Not merged, not
pushed. Full suite: **463 passing before → 479 passing after** (+16
test cases, all new; no existing test modified).

| | |
|---|---|
| `64e52ad` | Fix 1 — sharing.py provenance filter (P0) |
| `f42dad5` | Fix 4 — additive-column registry (P1) |

Files touched, all within the assigned ownership split:
`src/trinity/db.py`, `src/trinity/intake.py`, `src/trinity/sharing.py`,
`test/unit/test_box_status_and_sharing.py`,
`test/unit/test_db_migration.py`. Nothing under `.github/`,
`pyproject.toml`, `docs/`, `doctor.py`, `assimilator.py`,
`milestones.py`, or `tui/` was touched. No new runtime dependencies.

## Fix 1 — share-export dropped every approved intake candidate

`intake.approve_candidate()` preserves a candidate's real provenance
(`agent_harness` / `methods_live_draft` / `assimilator`), but
`sharing.py`'s two export queries still filtered
`WHERE source = 'ai_escalation'`, so approved Agent Harness /
Methods-live-draft / Assimilator explanations and error-fixes silently
never reached a share bundle.

The source vocabulary now has exactly one definition, in `db.py`:

```python
INTAKE_SOURCES = {"agent_harness", "methods_live_draft", "assimilator"}
AI_SOURCED = INTAKE_SOURCES | {"ai_escalation"}
```

- `intake.VALID_SOURCES` is now `db.INTAKE_SOURCES` (no duplicated
  literal; `intake.py` imports `db`).
- Both `sharing.py` filters are parameterized `source IN (?, ?, ?, ?)`
  built from `sorted(db.AI_SOURCED)` via a new `_placeholders()` helper
  (the file already used the same inline `",".join("?" for _ in ...)`
  idiom for its `command IN (...)` clause; that call site now uses the
  helper too).
- The three stale schema comments (`db.py:120-125`, `:130`, `:226`)
  that still described the old three-value
  `trinity_preseed`/`ai_escalation`/`user_curated` vocabulary now
  describe what those columns can actually hold and point at
  `AI_SOURCED`.
- Per §7 of the brief, `kb_candidates` behaviour is UNCHANGED. A
  comment at that query in `sharing.py` records that sourcing it from
  unmatched `findings` rather than `kb_entries` is deliberate — "share
  the gap, not the answer" — so a future reviewer doesn't re-open it.

Five tests added to `test_box_status_and_sharing.py`:

- `test_valid_sources_subset_of_ai_sourced` and
  `test_direct_write_path_defaults_are_ai_sourced` — the pinning pair.
  These are the ones that would have caught the ORIGINAL divergence at
  definition time, not just today's regression. Both `save_explanation`
  and `save_error_fix` were verified to really have a `source` kwarg
  defaulting to `"ai_escalation"`, so the brief's test bodies applied
  as written.
- `test_approved_intake_explanation_is_share_exportable` and
  `test_approved_intake_error_pattern_is_share_exportable` — the real
  regression tests, going through `submit_candidate()` →
  `approve_candidate()` → `build_share_bundle()`. The existing tests
  all insert rows directly with a hardcoded `source='ai_escalation'`,
  which is exactly why the bug survived them.
- `test_approved_intake_explanation_stays_box_scoped` — widening the
  source filter must not widen box scope.

All five were observed failing against the pre-fix code (2 ×
`AttributeError: module 'trinity.db' has no attribute 'AI_SOURCED'`, 3 ×
empty-bundle assertion failures); the output is pasted in the commit
message.

One incidental finding while writing these: `scrub_identifying()`
rewrites IPv4 literals to `$TARGET` in the exported `command`, so a
bundle's command text is not byte-identical to what was cached. That is
correct, intended behaviour — noting it only because it makes
"assert the exported command equals the submitted command" a trap for
whoever writes the next sharing test. The tests use IP-free commands.

## Fix 4 — additive-column migration registry

`_ensure_additive_columns` was three hand-copied PRAGMA blocks with the
`sqlite_master` existence guard on `engagement_meta` only, and the three
tables added by this session's work (`assimilator_runs`,
`show_me_runs`, `show_me_attestation`) had no entry at all. Replaced
with one `_ADDITIVE_COLUMNS: dict[str, list[tuple[str, str]]]` registry
and a single loop that applies the existence guard uniformly to all six
tables.

- Column data for `suggestions` / `boxes` / `engagement_meta` is
  carried over verbatim; only the mechanism changed. The old
  `_SUGGESTIONS_ADDITIVE_COLUMNS` / `_BOXES_ADDITIVE_COLUMNS` /
  `_ENGAGEMENT_ADDITIVE_COLUMNS` names are gone; nothing in `src/` or
  `test/` referenced them outside `db.py` (checked).
- The three new tables are registered with empty lists, as specified.
  The 6 extra Assimilator fields from `docs/ASSIMILATOR_PROJECT.md` §7
  were deliberately NOT added.
- The PRAGMA row access changed from `row["name"]` to `row[1]` so the
  function also works on a connection without `row_factory` set — the
  registry test exercises that path.

**Equivalence check demanded by the brief:**
`test_connect_adds_missing_suggestion_columns` passes completely
UNCHANGED after the refactor, so the registry is provably equivalent to
the old mechanism for everything it already covered.

Four new tests (11 parametrized cases) in `test_db_migration.py`:

- `test_registry_migrates_every_registered_table` — parametrized over
  all six registered tables. Since the three new tables have (correctly)
  empty column lists, it injects a probe column into the registry via
  `monkeypatch.setitem` and asserts `connect()` back-fills it. This
  asserts the MECHANISM reaches each table, which is the actual thing
  Fix 4 changes.
- `test_registry_restores_real_columns_dropped_from_an_old_db` — the
  same check against the registry's real data, for the three tables that
  have entries. Skipped below SQLite 3.35 (`ALTER TABLE DROP COLUMN`).
- `test_connect_adds_missing_engagement_meta_columns` — `engagement_meta`
  had a guard but no test.
- `test_migration_skips_tables_absent_from_an_old_db` — the uniform
  existence guard: a DB predating whole tables must migrate cleanly.

Red observation: pre-fix there is no registry to parametrize over, so
the module doesn't import (`ImportError: cannot import name
'_ADDITIVE_COLUMNS'`, collection error). Because that is a weak signal
on its own, the commit message also pastes a direct demonstration of
the dormant trap against pre-fix `db.py` — an old DB whose
`assimilator_runs` is missing a column stays missing it across
`connect()` (`fix_shape present after connect(): False`).

## Handoff notes for Cursor / Doc (docs are not mine to edit)

1. **`docs/AGENT_HARNESS.md:123`** — confirmed stale, as the brief
   suspected. It says an approved harness entry is "cached forever,
   same trust model (`source='ai_escalation'`)". That has not been true
   since `approve_candidate()` was fixed; approved harness entries carry
   `source='agent_harness'`. The trust *claim* is still right — the
   source string is not.
2. **`docs/INSTRUCTOR_MODE.md:135`** — enumerates the `source`
   vocabulary as `trinity_preseed` / `user_curated` / `ai_escalation`,
   the same stale three-value list I just fixed in `db.py`'s comments.
   Line 151 ("`ai_escalation`-sourced error fixes become …") reads as
   over-narrow for the same reason.
3. **`docs/FIX_PLAN_NON_SHOWME.md:143-144`** and
   **`docs/CURSOR_HANDOFF_CONTINUE.md:783`** name the now-deleted
   `_SUGGESTIONS_ADDITIVE_COLUMNS` / `_BOXES_ADDITIVE_COLUMNS` /
   `_ENGAGEMENT_ADDITIVE_COLUMNS` constants; they should point at
   `_ADDITIVE_COLUMNS` instead.
4. **`src/trinity/explain.py`'s `save_explanation` docstring** mentions
   only `trinity_preseed` / `user_curated` as alternatives to the
   default. Not wrong, just incomplete now — `explain.py` is outside my
   ownership split, so I left it. Low priority.

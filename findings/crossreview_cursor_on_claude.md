# Cross-review: Cursor on Claude Code CLI (Fix 1 + Fix 4)

Branch: `fix1-fix4-claude` (`466c560..HEAD`)
Commits reviewed: `64e52ad` (Fix 1), `f42dad5` (Fix 4), `57a62d2` (summary)
Spec: `docs/IMPLEMENTATION_BRIEF_CLAUDE.md`
Suite check: `uv run pytest -q` → **479 passed**. ruff/mypy are not configured on this branch (not in `pyproject.toml` / CI).

---

## Bugs found

1. **Registry comment overclaims coverage (low, docs-in-code).**
   `_ADDITIVE_COLUMNS` is introduced with: *"EVERY table in SCHEMA belongs here, including ones with nothing to migrate yet"* (`db.py` ~417–425), but the registry only lists the six tables the brief named. SCHEMA also defines `findings`, `timeline`, `kb_entries`, `command_explanations`, `error_patterns`, `intake_candidates`, `loot`, `hint_state`, etc. — none of those appear.
   Functional behavior for Fix 4’s six tables is correct; the danger is instructional. A future contributor who trusts that sentence may assume “adding a column to SCHEMA is enough because the registry already covers every table,” and recreate the exact dormant trap this fix was meant to close — just on `findings` or `intake_candidates` instead of `assimilator_runs`. Either register the rest with `[]`, or soften the comment to “every table that has (or may gain) additive columns; register a table the moment you add it to SCHEMA.”

2. **`build_share_bundle` docstring still describes the pre-fix filter (low, stale wording).**
   After widening the filter to `db.AI_SOURCED`, the function docstring still says it gathers *"THIS box's AI-escalation-sourced explanations/error-fixes"* (`sharing.py` ~58–70). The inline query comments above the new `IN` clauses are accurate; the docstring is the leftover lie. Same class of drift Fix 1 just fixed in the schema comments — smaller blast radius, but it will confuse the next reader of the public API.

No functional / failing-path bugs found in the Fix 1 filter change, the `intake.VALID_SOURCES` alias, the additive-column loop, or the new tests. Ownership split respected; no `src/` or `test/` files outside the brief were touched.

---

## Design questions

1. **Why put `INTAKE_SOURCES` / `AI_SOURCED` at module top instead of “next to” the schema comments the brief pointed at (`db.py:120–125` etc.)?**
   Module-top is the more idiomatic place for importable constants, and the schema comments were updated to point at `AI_SOURCED` — so this reads as a deliberate improvement over the brief’s literal placement, not a miss. Curious whether that was conscious (“constants belong above SCHEMA”) or just where the edit landed.

2. **Why leave most SCHEMA tables out of `_ADDITIVE_COLUMNS` when the new comment argues empty registration is cheap insurance?**
   The brief only required the six named tables, so this is compliant. But given the comment’s own thesis (“an empty list is the registration that makes the first future column Just Work”), I’m curious why not spend the extra ~10 lines and register every other table with `[]` in the same commit — that would make the comment true and close the class of bug for the whole schema, not just the Show-Me-adjacent three.

3. **`VALID_SOURCES = db.INTAKE_SOURCES` aliases the same mutable `set` object.**
   Brief asked for exactly this, so not a miss — but I’m curious why not `frozenset` (or a copy). Today, `VALID_SOURCES.add("foo")` mutates `INTAKE_SOURCES` while leaving the already-built `AI_SOURCED` unchanged, which is the Fix 1 divergence in miniature. The pinning test would catch it at CI time; a frozenset would make the footgun impossible. Was mutability kept for a reason, or just matching the brief’s snippet?

4. **Regression tests hand-insert timeline rows after `approve_candidate()`.**
   Necessary — `approve_candidate()` does not write timeline, and share-export is scoped via timeline prefixes (`explained: ` / `diagnosed error: `). Curious whether you considered asserting that production path gap anywhere (approved intake entry with `box_id` set but no timeline → absent from bundle), or decided that belongs to a different fix. Not wrong either way; the current tests correctly model the export contract as it exists.

5. **`test_migration_skips_tables_absent_from_an_old_db` opens a raw connection it never closes** (`sqlite3.connect(path)` passed straight into `_ensure_additive_columns`). Fine on Linux; was the intentional trade for “prove the guard without `connect()`’s SCHEMA side effects,” or just brevity? Also curious why `missing` asserts `{assimilator_runs, show_me_runs, engagement_meta}` but not `show_me_attestation` — sample vs. incomplete?

6. **`_placeholders(values)` is untyped and lives next to a mid-file import block** (`sharing.py` ~28–36, after `scrub_identifying`). The mid-file import of `trinity.state` was pre-existing; adding `db` there matches local style. Still curious why not hoist both imports to the top while touching the file — or was preserving the existing quirk deliberate to keep the diff small?

---

## Things done well

1. **Real-path regression tests, not fixture cheats.** `submit_candidate` → `approve_candidate` → `build_share_bundle` with `agent_harness` / `assimilator` / `methods_live_draft`, plus an explicit box-scoping test, is exactly the test shape that would have caught the original bug. The commit message’s honesty about why prior tests missed it (`source='ai_escalation'` hardcoded inserts) is useful review signal.

2. **The two pinning tests are the right kind of cheap.** `VALID_SOURCES <= AI_SOURCED` and “direct-write defaults ∈ AI_SOURCED” nail definition-time drift, not just today’s symptom. Verifying the real `save_explanation` / `save_error_fix` signatures before copying the brief’s snippet was the right call.

3. **Fix 4’s probe-injection test is excellent.** Parametrizing over all six tables and `monkeypatch.setitem`-ing a `_migration_probe` column is the correct way to assert mechanism reach for tables whose real column list is still empty. The DROP-COLUMN restore test + engagement_meta old-schema test + existence-guard test together cover what the brief asked for and more.

4. **`row[1]` instead of `row["name"]` in `_ensure_additive_columns`.** Quietly makes the helper work on connections without `row_factory` (the skip-absent test exercises that). Small, real improvement over the old blocks.

5. **Ground rules followed visibly.** Pre-fix failure output pasted into both fix commits; one logical fix per commit; ownership split respected; Assimilator §7 columns correctly left out; `kb_candidates` “share the gap” comment added without changing behavior; handoff notes for stale docs (`AGENT_HARNESS.md`, etc.) instead of editing Cursor-owned `docs/`.

6. **Single vocabulary, parameterized `IN` clauses, `sorted(AI_SOURCED)` for stable SQL.** The sharing change is small, readable, and matches existing style via `_placeholders` (including reusing it for the command `IN` clause).

---

## Summary verdict

**Merge with minor fixes** — not rework.

Fix 1 and Fix 4 both match the agreed brief, keep the suite green (479), and the new tests are stronger than the minimum asked. The only concrete follow-ups I’d want before or right after merge are: (a) fix the `_ADDITIVE_COLUMNS` comment so it doesn’t claim every SCHEMA table is registered (or actually register them with `[]`), and (b) update the `build_share_bundle` docstring so it no longer says “AI-escalation-sourced.” Everything else in Design questions is curiosity / optional hardening, not a merge blocker.

# Polish pass — fix every real finding from the cross-review round

Both branches (`fix1-fix4-claude` and `fix2b-fix3-fix6-cursor`) were
independently implemented, then cross-reviewed by the other agent plus
Doc. Both got "merge with minor fixes" verdicts. This is that fix
pass -- applied by you, to BOTH branches, so the fixes are consistent.
You are working in two separate worktrees (paths given below) since
the two branches touch disjoint files; do the work in each worktree
against its own branch, do not try to merge them yourself.

Ground rules unchanged: keep `uv run pytest -q` green after every
commit, small reviewable commits, do not merge or push, do not touch
files outside what's listed for each branch (same ownership split as
before -- `db.py`/`sharing.py`/`intake.py` stay in the claude worktree,
everything else in the cursor worktree, EXCEPT item 2 below which is a
narrow, explicitly-authorized exception to that rule).

## In worktree `/home/alexander/Work/trinity-wt-fix-claude` (branch `fix1-fix4-claude`)

1. **Fix the `_ADDITIVE_COLUMNS` comment overclaim.** It currently says
   "EVERY table in SCHEMA belongs here, including ones with nothing to
   migrate yet" but only 6 of the ~14 SCHEMA tables are actually
   registered. Either (a) register the remaining tables with `[]` too
   (cheap, makes the comment literally true and closes the same class
   of bug for the whole schema, not just the 3 Show-Me-adjacent
   tables) -- PREFERRED, or (b) soften the comment to say "every table
   that has, or may gain, additive columns; register a table the
   moment you add it to SCHEMA" if you think registering everything is
   out of scope. Your call, but state which you picked and why in the
   commit message.
2. **Fix `build_share_bundle`'s stale docstring.** It still says the
   function gathers "THIS box's AI-escalation-sourced
   explanations/error-fixes" -- update to reflect the widened
   `db.AI_SOURCED` filter.
3. **Consider `frozenset` for `INTAKE_SOURCES`/`AI_SOURCED`.** Cursor's
   review flagged that `VALID_SOURCES = db.INTAKE_SOURCES` aliases the
   same mutable `set` object -- `VALID_SOURCES.add(...)` would silently
   mutate `INTAKE_SOURCES` while `AI_SOURCED` (built once at import
   time via `|`) stays stale. Nothing calls `.add()` on these today, so
   this is prevention, not a live bug -- but it's a one-line change
   (`frozenset({...})` instead of `{...}`) that makes the footgun
   structurally impossible rather than relying on the pinning test to
   catch it later. Do it unless you find a concrete reason `frozenset`
   breaks something (e.g. if `VALID_SOURCES` is mutated anywhere
   intentionally -- check before assuming it's safe).

## In worktree `/home/alexander/Work/trinity-wt-fix-cursor` (branch `fix2b-fix3-fix6-cursor`)

4. **Fix `GtfobinsLookupScreen`'s clipping bug** (new finding from
   Claude's cross-review, not in the original brief, but confirmed
   live with real shipped data -- the `ldconfig` entry is 752 chars and
   wraps to 14 rows in a 20-row box, pushing the Close button entirely
   off-screen). This is the exact same shape of bug Fix 6.1 already
   fixed for `_TextResultScreen` -- apply the same `VerticalScroll`
   wrapper pattern to `GtfobinsLookupScreen`'s result display
   (`src/trinity/tui/show_me_screens.py`, roughly lines 253-285).
5. **Finish Fix 6.3 properly** -- the two CLI call sites
   (`src/trinity/cli/main.py`'s `watch` and `shoulder` commands, doctor
   pre-check calls, roughly lines 694 and 739) still call
   `run_doctor(include_vpn=True)` synchronously on startup. The
   original brief asked for these by line number with an explicit
   fallback option: reduce the VPN check's timeout for these specific
   interactive call sites (e.g. pass a shorter timeout through to
   `check_vpn()`, or call with `include_vpn=False` for the startup
   pre-check specifically and let the TUI's already-fixed background
   worker handle the full check on demand). Pick whichever is less
   invasive and say which in the commit message.
6. **Revert the doc-status headers that got worse.** Your Fix 3
   normalization forced several headers into the
   `DESIGN ONLY/BUILT/QUARANTINED/PARTIAL` vocabulary that were
   tracking assignment/decision state, not build state, and now
   contradict their own body text:
   - `docs/AD_SIMULATION_PROJECT.md:3` says `Status: PARTIAL.` then 4
     lines later says "there's nothing to test yet" -- contradiction.
   - `docs/COACH_METERPRETER_NESTING_DESIGN.md:3` was asserted
     `PARTIAL` without checking the actual code state.
   - `docs/OPEN_DECISIONS.md:3` was `**UNDECIDED.**`, forcing it to
     `DESIGN ONLY` implies a design exists when the doc's whole point
     is that nothing has been decided.
   Fix: the `test_doc_status_headers.py` test only constrains
   `Status:` lines that exist -- it doesn't require every doc to have
   one. For these three (and any other non-build-state docs you find
   in the same situation), either revert to their original wording (if
   it's more accurate) or remove the `Status:` line entirely if it's
   tracking something the fixed vocabulary genuinely can't express. Use
   your judgment on which of those 3 need which treatment -- read each
   doc's actual current state before deciding.
7. **Delete the two tautological test assertions.** In
   `test/unit/test_report_renderers.py`, lines asserting
   `data.box.name == "AttackRendererBox"` and
   `data.box.name == "RemediationRendererBox"` check the test fixture,
   not the renderer output -- they'd pass even if `map_attack`/
   `draft_remediation` returned garbage. Delete those two lines (the
   real assertions `assert hits` and `len(text) > 20` already carry
   the actual test weight).
8. **Add at least one real test for the Fix 6 TUI fixes.** Currently
   none of the three (scroll, mode-switch refresh, doctor worker) has
   direct test coverage -- the existing `DoctorScreen` test still calls
   `get_text()`, a path the UI no longer uses after your fix. Add a
   Textual Pilot-driven test (follow the pattern already established in
   `test/unit/test_dashboard_menus.py`) that presses `a`, selects mode
   switch, and asserts the dashboard's status bar reflects the new mode
   -- this is the highest-priority of the three per both reviews. If
   you have time, also add a minimal Pilot test confirming the
   `VerticalScroll` wrapper actually allows scrolling past the
   max-height (don't over-invest here if the mode-switch test eats your
   time budget -- that one matters most).
9. **Clean up the per-file-ignores once Claude's branch's fixes land.**
   This is a coordination note, not something to act on until BOTH
   worktrees' fixes are done: after item 3 above (frozenset) and item 1
   (registry) land in the claude worktree, the ruff/mypy per-file-
   ignores in `pyproject.toml` for `intake.py`/`sharing.py`/the two
   claude-owned test files may no longer be needed, or may need
   updating. Note this in your summary as a "verify after merge" item
   rather than trying to guess the merged state from here (you don't
   have visibility into the other worktree's final diff).

## When done (each worktree separately)

Run `uv run pytest -q`, and in the cursor worktree also
`uv run ruff check .` and `uv run mypy src/`. Update or append to the
existing implementation summary file in that worktree
(`findings/fix1_fix4_implementation_summary.md` or
`findings/fix2b_fix3_fix6_implementation_summary.md`) with what you
fixed and why. Do NOT merge or push either branch.

# Implementation brief — Fix 2b + Fix 3 + Fix 6 + smoke tests (Cursor's half)

This is the CODE-WRITING pass following four rounds of review (two
independent full-program reviews, a peer review of the fix plan, and a
cross-talk round between you and Claude Code CLI). The plan below is
the agreed conclusion of all four rounds -- implement it, don't
re-derive it. Full suite is 463 passing before you start (464 after
Fix 2a, already landed on main); keep it green throughout, one commit
per logical fix.

You own: `.github/` (Fix 2a's `ci.yml` already exists, you're adding
to it), `pyproject.toml`, `docs/*.md`, `src/trinity/doctor.py`,
`src/trinity/assimilator.py` (docstring only), `src/trinity/tui/`
(`show_me_screens.py`, `dashboard.py`), new test files.
Do NOT touch: `src/trinity/sharing.py`, `src/trinity/intake.py`,
`src/trinity/db.py`, `test/unit/test_box_status_and_sharing.py`,
`test/unit/test_db_migration.py` -- Claude Code CLI owns those in a
parallel worktree (`fix1-fix4-claude`); touching them creates a merge
conflict for no reason.

## Ground rules

1. Small, reviewable commits, one fix per commit.
2. Every commit must pass `uv run pytest -q` standalone.
3. No new runtime dependencies beyond `ruff` and `mypy` (both already
   agreed, dev-group only).
4. Land Fix 2b (ruff/mypy) LAST, after everything else in this brief --
   the lint/type baseline should be computed once against the final
   tree, not recomputed after every subsequent commit.

## Fix 3 — docstring drift cleanup (do this section first)

1. **Status headers.** `docs/SHOW_ME_MODE.md:3` and
   `docs/ASSIMILATOR_PROJECT.md:3` still say
   "Status: DESIGN ONLY. Nothing in this document is built yet." --
   both are substantially built (and now quarantined, not unbuilt).
   Change both headers to `Status: QUARANTINED` (matching
   `docs/SHOW_ME_MODE_QUARANTINE.md`'s own header) with a one-line
   pointer to that doc. Establish a fixed vocabulary:
   `DESIGN ONLY` / `BUILT` / `QUARANTINED` / `PARTIAL`.
2. Add `test/unit/test_doc_status_headers.py` (~15 lines): walk
   `docs/*.md`, find any line starting with `Status:` or
   `**Status:**`, assert its value is one of the four fixed strings
   above. This is an invariant that's ALREADY recurred once (fixed in
   an earlier commit, silently reintroduced two commits later) so it
   gets a real test, not just a one-time text fix.
3. **`doctor.py` docstring.** `src/trinity/doctor.py`'s module
   docstring claims "no subprocess spawns beyond `shutil.which`
   checks" -- but `run_doctor(include_vpn=True)` calls `check_vpn()`
   (in `vpn.py`) which runs `subprocess.run(["ip", "-o", "link",
   "show"], ...)`. Fix: extend the docstring sentence to "...beyond
   `shutil.which` checks and vpn.py's `ip link` probe." One clause,
   not a rewrite.
4. **`assimilator.py` docstring.** `check_already_known`'s docstring
   (around line 74-78) claims it reuses "`match_finding`'s exact same
   lookup path ... so 'already known' means the same thing here as
   everywhere else." This is false -- everywhere else `match_finding`
   receives a structured `Finding` from a parser; here it's called
   with `service=None, product=None, version=None` and a raw
   transcript in `detail`. Fix the docstring to accurately describe
   what it actually does (matches against a raw transcript blob, not
   a structured finding) and note this is a known limitation being
   addressed in the Show Me Mode rebuild (see
   `docs/SHOW_ME_MODE_QUARANTINE.md`). Do NOT change the function's
   behavior, text-only fix.
5. Leave `record_shell()` in `milestones.py` untouched -- do not add
   an optional source/detail override parameter. Both reviews agreed
   this would weaken the invariant it's meant to protect.

## Fix 6 — TUI hygiene bugs (found live during review, all confirmed)

These sit on the exact surface the quarantine doc calls "confirmed
GOOD and safe to show a live tester today" -- fix them so that claim
stays true.

1. **`_TextResultScreen` clips instead of scrolling**
   (`src/trinity/tui/show_me_screens.py`, around line 102-125).
   `#result-box { max-height: 24 }` on a bare `Static` with no
   `VerticalScroll` wrapper -- long report output (e.g. Advanced →
   Generate report) silently truncates with no indicator. Fix: wrap
   the `Static` in a `VerticalScroll` container so long text scrolls
   instead of clipping.
2. **`ModeSwitchScreen` leaves the dashboard status bar stale**
   (`show_me_screens.py` around line 369-374, `dashboard.py` around
   line 107-123). After switching box mode via Advanced Options, the
   header keeps showing the OLD mode because `_refresh_status()` is
   only called from `on_mount`/`action_mark_done`/`action_mark_skip`
   -- nothing calls it after a mode switch. Fix: call
   `self.app._refresh_status()` (or equivalent) after the mode switch
   dismisses, so the header updates immediately. This is the highest
   priority of the three -- it's a one-line fix and it's exactly the
   kind of thing a live tester reports as "it didn't work" when it did.
3. **`DoctorScreen` runs the VPN probe synchronously on the UI thread**
   (`show_me_screens.py` around line 165-170, calls
   `run_doctor(include_vpn=True)` inline in `compose()`/`get_text()`).
   This also affects `cli/main.py`'s `watch`/`shoulder` startup calls
   at similar call sites (~line 683, ~723) which call the same
   function the same way. `check_vpn()` has a 5-second subprocess
   timeout, so in the worst case this freezes the whole Textual event
   loop for 5 seconds. Fix: either run it in a background worker
   (`@work(thread=True)`, following the pattern already used elsewhere
   in `show_me_screens.py` -- but watch out for the cross-thread SQLite
   bug documented in `docs/SHOW_ME_MODE_QUARANTINE.md` finding #2, this
   doesn't touch the DB so it should be safe, but double check), or
   reduce the VPN check's timeout to ~1s for these specific interactive
   call sites. Prefer the background-worker fix if it's not much more
   code; a frozen UI is worse than a slightly stale VPN status.

## New — report renderer smoke tests (P2, small)

Nothing in `test/` imports `report/notebook.py`, `report/attack.py`,
or `report/remediation.py` directly (only indirectly via
`generate_professional_report`, which doesn't exercise every code
path). Add `test/unit/test_report_renderers.py`: for each of the three
modules, seed a minimal box with some findings, call the renderer
function, assert it doesn't raise and the output contains the box
name. ~30 lines total, new file, zero conflict with anything else.
This is deliberately NOT a coverage-percentage exercise (both prior
reviews explicitly rejected `pytest-cov` as hiding quality problems
behind a healthy number) -- it's three named, previously-completely-
untested files getting a real smoke test.

## Fix 2b — ruff + mypy (do this LAST, after everything above)

1. Add to `[dependency-groups].dev` in `pyproject.toml`: `ruff` and
   `mypy` (alongside the existing `pytest`/`pytest-asyncio`).
2. `[tool.ruff]`: `line-length = 100`, `exclude = ["test/fixtures/"]`.
3. `[tool.ruff.lint]`: `select = ["E4", "E7", "E9", "F", "I", "UP",
   "B", "C4", "BLE"]`. Explicitly do NOT add `ANN`, `E501`, `D`, or
   `RUF100` in this pass (RUF100 goes on a "tighten later" list --
   note this in a comment in pyproject.toml).
4. `[tool.mypy]`: `python_version = "3.12"`,
   `plugins = ["pydantic.mypy"]` (REQUIRED -- 23 modules use
   `BaseModel`, without this plugin mypy produces false positives on
   every model constructor), `ignore_missing_imports = true`,
   `warn_unused_ignores = false`, and `exclude` for
   `src/trinity/tui/` and `src/trinity/show_me.py` (quarantined code,
   type-checking it to a clean baseline is wasted effort that the
   eventual rebuild would throw away).
5. Run `uv run ruff check .` and `uv run mypy src/` against the tree.
   If either produces a large finding list, do NOT try to fix
   everything in this same PR -- either narrow the rule set further
   for this first pass, or add a baseline/ignore mechanism, and note
   in your summary what was deferred and why. The goal is a clean,
   reviewable FIRST green CI run, not zero technical debt.
6. Add both as steps in `.github/workflows/ci.yml` after the existing
   pytest step: `uv run ruff check .` and `uv run mypy src/`.

## When done

Run `uv run pytest -q` (should stay at ~464+ passing plus your new
smoke tests), confirm `uv run ruff check .` and `uv run mypy src/` are
clean (or document what's deferred), commit each fix separately, and
write a short summary to `findings/fix2b_fix3_fix6_implementation_summary.md`
on your branch (`fix2b-fix3-fix6-cursor`). Do NOT merge or push --
Doc will review and merge.

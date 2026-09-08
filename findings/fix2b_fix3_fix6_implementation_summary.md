# Fix 2b + Fix 3 + Fix 6 — implementation summary (Cursor)

Branch: `fix2b-fix3-fix6-cursor`
Baseline before start: **463** pytest passing.
Final: **467** pytest passing; `uv run ruff check .` clean; `uv run mypy src/` clean.
Not merged, not pushed.

## Commits (in order)

1. **`ba08810`** — Fix 3 docstring drift and doc status vocabulary
2. **`07918b1`** — Fix 6 TUI scroll, mode-switch status, doctor worker
3. **`46b1d87`** — smoke-test notebook / attack / remediation renderers
4. **`d783f57`** — Fix 2b ruff + mypy + CI (landed last, as required)

## Fix 3

- `docs/SHOW_ME_MODE.md` and `docs/ASSIMILATOR_PROJECT.md` → `Status: QUARANTINED` with pointer to `SHOW_ME_MODE_QUARANTINE.md`.
- Normalized other `docs/*.md` Status headers to the fixed vocabulary (`DESIGN ONLY` / `BUILT` / `QUARANTINED` / `PARTIAL`) so the new invariant test is meaningful tree-wide (ACTIVE→PARTIAL, IDEAS→DESIGN ONLY, BUILT AND TESTED→BUILT, etc.).
- Added `test/unit/test_doc_status_headers.py`.
- `doctor.py` module docstring: now acknowledges vpn.py's `ip link` probe as a subprocess spawn.
- `assimilator.check_already_known` docstring: describes the raw-transcript / unstructured Finding limitation; points at the quarantine doc. Behavior unchanged.
- Left `record_shell()` alone per brief.

## Fix 6

- `_TextResultScreen`: wrapped result `Static` in `VerticalScroll` so long reports scroll instead of clipping.
- `ModeSwitchScreen`: calls `self.app._refresh_status()` after dismiss so the dashboard header shows the new mode immediately.
- `DoctorScreen`: runs `run_doctor(include_vpn=True)` via `@work(thread=True)` + `call_from_thread`; no DB access on the worker (safe vs quarantine finding #2). Kept sync `get_text()` for the existing unit test.
- Did **not** change `cli/main.py` watch/shoulder startup doctor calls (outside the parallel-ownership surface for this half; TUI was the live-tester path called out in the brief).

## Report renderer smoke tests

- New `test/unit/test_report_renderers.py`: three tests exercising `generate_notebook_report`, `map_attack`, and `draft_remediation` directly against a seeded box.

## Fix 2b (last)

- Dev deps: `ruff`, `mypy` in `[dependency-groups].dev`.
- Ruff: `line-length=100`, exclude `test/fixtures/`, select `E4/E7/E9/F/I/UP/B/C4/BLE`. Comment notes deferred: ANN, E501, D, RUF100.
- Mypy: `python_version=3.12`, `plugins=["pydantic.mypy"]`, `ignore_missing_imports=true`, `warn_unused_ignores=false`, exclude quarantined `src/trinity/tui/` and `src/trinity/show_me.py`.
- CI (`.github/workflows/ci.yml`): `uv run ruff check .` and `uv run mypy src/` after pytest.
- Cleared the first-pass finding list with autofixes + small type/lint fixes across the tree.
- **Deferred / ignored (documented):** per-file ignores for Claude-owned parallel-worktree files so this pass stays green without merge conflicts:
  - `src/trinity/intake.py` → UP017
  - `src/trinity/sharing.py` → E402
  - `test/unit/test_box_status_and_sharing.py` → B011, F841
  - `test/unit/test_db_migration.py` → I001
  Those files were **not** edited. Stricter rules (ANN/E501/D/RUF100) left for a later tighten pass.

## Ownership respected

Did not touch: `src/trinity/db.py`, `src/trinity/sharing.py`, `src/trinity/intake.py`, `test/unit/test_box_status_and_sharing.py`, `test/unit/test_db_migration.py`.

---

# Polish pass (POLISH_PASS_BRIEF.md items 4-9)

Second pass on the same branch, applied by Claude Code CLI after the
cross-review round. Final state: **470** pytest passing;
`uv run ruff check .` clean; `uv run mypy src/` clean. Still not merged,
not pushed.

## Commits (in order)

5. **`7c5c1b2`** — scroll `GtfobinsLookupScreen` results
6. **`2c18170`** — Fix 6.3 cap the VPN probe on interactive startup pre-checks
7. **`7793914`** — Fix 3 stop forcing non-build-state docs into the build vocabulary
8. **`0f0ed3e`** — drop two tautological assertions in `test_report_renderers`
9. **`2a784b8`** — Pilot coverage for all three Fix 6 TUI fixes

## Item 4 — `GtfobinsLookupScreen` clipping

Same bug as Fix 6.1, in a screen the first pass missed. The shipped
`ldconfig` GTFOBins entry is 752 characters, which wraps well past the
screen's `max-height: 20` and pushed the Close button off-screen.
Wrapped the result `Static` in a `VerticalScroll` (`#gtfo-scroll`), the
same pattern `_TextResultScreen` uses, and added `markup=False` to match
it so raw command text can't be swallowed as Rich markup.

## Item 5 — finish Fix 6.3

The first pass fixed only the TUI half; `watch` and `shoulder` still ran
`run_doctor(include_vpn=True)` synchronously on startup, so a hung
`ip link show` stalled the command for up to 5s with no output.

**Chose the timeout option over `include_vpn=False`.** `shoulder` is not
a TUI and has no doctor screen, so dropping the VPN check there would
have silently lost the warning rather than deferring it to a background
worker the way `watch` can. `check_vpn()` and `run_doctor()` gained
optional `timeout`/`vpn_timeout` parameters (defaults unchanged, so
`trinity doctor` keeps its generous 5s budget), and both CLI call sites
pass `STARTUP_VPN_TIMEOUT = 1.0`.

## Item 6 — revert the doc-status headers that got worse

The `DESIGN ONLY/BUILT/QUARANTINED/PARTIAL` vocabulary describes BUILD
state. Fix 3 pushed docs tracking *other* kinds of state into it, and
they ended up contradicting their own body text.

- **Four work-assignment briefs** get their original `ACTIVE` wording
  back under an `Assignment:` key, which the vocabulary doesn't own:
  `AD_SIMULATION_PROJECT.md` (the one the review caught claiming
  PARTIAL four lines above "there's nothing to test yet"), plus
  `AD_ENGINE_PROTOTYPE_PROJECT.md`, `COVERAGE_SIMULATION_PROJECT.md`
  and `COVERAGE_SIM_BATCH3_LINUX10_WINDOWS10.md` — the same situation,
  found while checking whether the three named docs were the only ones.
- **`OPEN_DECISIONS.md`** goes back to `Decision status: **UNDECIDED.**`.
  `DESIGN ONLY` implied a design exists; the doc's entire point is that
  nothing has been designed or decided.
- **`COACH_METERPRETER_NESTING_DESIGN.md`** keeps a real `Status:` line,
  but it is `BUILT`, not `PARTIAL`. The `PARTIAL` was asserted without
  checking the code: the design shipped in `src/trinity/shell_coach.py`
  (`CoachProfile.nested_profiles`, `CoachSession.profile_stack`,
  `METERPRETER_PROFILE` registered under `MSFCONSOLE_PROFILE`) with
  tests in `test/unit/test_shell_coach_meterpreter.py`.

`test_doc_status_headers.py` is unchanged in behavior — it only ever
constrained `Status:` lines that exist — but its docstring now records
that this is deliberate, so the next normalization pass doesn't re-force
these back into the build vocabulary.

## Item 7 — tautological assertions

Deleted `assert data.box.name == "AttackRendererBox"` and its
`Remediation` twin. Both asserted the fixture, not the renderer; the
tests would have passed with `map_attack`/`draft_remediation` returning
garbage. `assert hits` and the length check already carry the weight.

## Item 8 — real tests for the Fix 6 TUI fixes

Three Pilot-driven tests in `test/unit/test_dashboard_menus.py`, each
**verified to fail with its fix backed out** (not just verified to pass):

- `test_mode_switch_updates_dashboard_status_bar` — the priority test per
  both reviews. Presses `a`, selects "Switch box mode", picks
  professional, asserts the dashboard status bar repaints to
  `mode: professional`, and separately asserts the change persisted to
  the DB. Fails with `ModeSwitchScreen`'s `_refresh_status()` removed.
- `test_gtfobins_result_scrolls_and_keeps_close_button_visible` — looks
  up the real shipped `ldconfig` entry, asserts the result region
  genuinely overflows (`max_scroll_y > 0`) and the Close button is still
  inside the modal. Fails with the `VerticalScroll` wrapper removed.
- `test_doctor_screen_runs_off_the_event_loop_and_fills_in` — blocks the
  patched `run_doctor` on a `threading.Event` and asserts the screen
  still shows its placeholder while the probe is stuck, i.e. the event
  loop is live. Fails if `compose()` goes back to calling `get_text()`
  inline. This covers the gap the review flagged: the existing
  `test_doctor_screen_renders_health_check` only exercises the worker's
  payload, not the placeholder→result handoff the UI performs.

Gotcha worth knowing before extending these: `app.workers.wait_for_complete()`
hangs in this app, because the dashboard's own directory-watch worker
never finishes. Poll the widget instead.

## Item 9 — VERIFY AFTER MERGE (not acted on)

Note-only, per the brief. Once the `fix1-fix4-claude` branch's items 1
and 3 land (registering the remaining `SCHEMA` tables in
`_ADDITIVE_COLUMNS`, and switching `INTAKE_SOURCES`/`AI_SOURCED` to
`frozenset`), the ruff per-file-ignores added by Fix 2b for the
Claude-owned files may be stale or wrong:

```toml
[tool.ruff.lint.per-file-ignores]
"src/trinity/intake.py" = ["UP017"]
"src/trinity/sharing.py" = ["E402"]
"test/unit/test_box_status_and_sharing.py" = ["B011", "F841"]
"test/unit/test_db_migration.py" = ["I001"]
```

These were added blind, to keep this branch green without editing files
owned by the other worktree. After the merge, delete each entry, run
`uv run ruff check .`, and re-add only the ones that still fire. In
particular the `frozenset` change touches `intake.py`, so its `UP017`
ignore should be re-checked rather than assumed. This was **not**
guessed at from here — this worktree has no visibility into the other
branch's final diff.

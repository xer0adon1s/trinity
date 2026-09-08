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

# Cross-review — Claude Code CLI on Cursor's branch (`fix2b-fix3-fix6-cursor`)

Scope: `466c560..HEAD` (5 commits), judged against
`docs/IMPLEMENTATION_BRIEF_CURSOR.md`.

Verification I ran locally in this worktree (read-only; no src/ or
test/ file was modified):

- `uv run pytest -q` → **467 passed** in 81s.
- `uv run ruff check .` → **All checks passed!**
- `uv run mypy src/` → **Success: no issues found in 79 source files.**
- Three throwaway Textual `run_test` harnesses in `/tmp` (not committed)
  to actually drive the Fix 6 screens with a Pilot, since none of the
  three TUI fixes has a test. Results are quoted under the relevant
  findings — all three fixes do what they claim.

## Bugs found

### 1. Fix 6.3 is only half-implemented — the two CLI call sites are still synchronous (severity: medium-low)

`src/trinity/cli/main.py:694` (`watch`) and `src/trinity/cli/main.py:739`
(`shoulder`) still call `run_doctor(include_vpn=True)` inline on the
main thread. The brief named these two sites explicitly ("This also
affects `cli/main.py`'s `watch`/`shoulder` startup calls at similar
call sites (~line 683, ~723) which call the same function the same
way"), and offered a cheap out for them specifically — "reduce the VPN
check's timeout to ~1s for these specific interactive call sites."
Neither was done.

The summary's justification is that `cli/main.py` was "outside the
parallel-ownership surface for this half," but that doesn't hold up:
`cli/main.py` isn't on the do-not-touch list, and this branch edits it
in six places anyway (lines 10-17, 563-567, 728-733, 1075, 1447, 1462)
for lint. So the file was in play; the fix just didn't get made.

Impact is real but bounded: `trinity watch` and `trinity shoulder` can
sit for up to 5 seconds with no output before anything appears, which
is exactly the "did it hang?" moment a live tester reports. It is not
an event-loop freeze like the TUI case was, which is presumably why it
felt deferrable — but the brief asked, and a one-line
`include_vpn=False`-with-shorter-timeout variant would have closed it.

### 2. `GtfobinsLookupScreen` has the identical clipping bug Fix 6.1 fixed, one screen over — and it hides the Close button (severity: medium-low; pre-existing, not introduced here)

`src/trinity/tui/show_me_screens.py:253-285`: `#gtfo-box` is
`height: auto; max-height: 20` around a bare `Static(id="gtfo-result")`
— the same shape as the `#result-box` that Fix 6.1 correctly wrapped in
a `VerticalScroll`. This one wasn't touched.

Reproduced with real shipped data (not a synthetic long string). The
longest GTFOBins summary in `_load_entries()` is 752 chars
(`ldconfig`), which wraps to 14 rows at the screen's 64-col content
width. Driving the real screen with a Pilot and typing `ldconfig`:

```
box:    Region(x=15, y=10, width=70, height=20)   # bottom = y=30
result: Region(x=18, y=16, width=64, height=14)   # bottom = y=30, i.e. flush against the cut
button: Region(x=18, y=30, width=16, height=3)    # entirely below the box
button fully visible: False
```

So for the long entries the source URL line is cut off and the **Close
button renders outside the visible modal**. `GtfobinsLookupScreen`
also declares no `BINDINGS`, so there's no `escape` route the way
`_TextResultScreen` has one — the user has to Tab to an invisible
button and press Enter. It's escapable, so not a hard trap, but it's
the same class of bug on the same "confirmed GOOD and safe to show a
live tester today" surface, and the fix is the two lines that were
already written for the sibling screen.

(`HashLookupScreen`'s result is one short line, so it's fine. The
`max-height: 20` at line 643 is in `ShowMeRunningScreen`, quarantined,
don't care.)

### 3. The doc-status normalization introduced new factual drift while fixing old drift (severity: low, docs-only)

The brief asked for two headers to change and a fixed four-word
vocabulary. Cursor also converted every other `Status:` header in
`docs/` so the new test would pass tree-wide — reasonable in principle,
but several of those headers weren't tracking *build state* at all,
they were tracking *assignment* or *decision* state, and forcing them
into `BUILT/PARTIAL/DESIGN ONLY/QUARANTINED` made some of them wrong:

- `docs/AD_SIMULATION_PROJECT.md:3` now reads `Status: PARTIAL.` and
  then, four lines later, "Do not start this before the engine
  prototype exists; **there's nothing to test yet.**" The header now
  contradicts its own body — "PARTIAL" claims partially built, the body
  says not started.
- `docs/COACH_METERPRETER_NESTING_DESIGN.md:3`: `APPROVED, implementing
  directly in this pass` → `PARTIAL. Approved, implementing...`. The
  nested-profile machinery is in `shell_coach.py` today
  (`CoachProfile.nested_profiles`, `_pop_to_parent`, the stack logic at
  lines 155-175), so `PARTIAL` may well be understating it — but
  either way "PARTIAL" was asserted without anyone checking the code.
- `docs/OPEN_DECISIONS.md:3`: `**UNDECIDED.**` → `DESIGN ONLY.
  Undecided — ...`. This doc's whole point is that nothing has been
  designed or approved; "DESIGN ONLY" implies a design exists.

This is low-stakes as bugs go, but it's the exact failure mode Fix 3
exists to prevent (a header asserting something about state that isn't
true), reintroduced in the commit that fixes it. Suggested repair is
small: either add a fifth term for non-build docs, or leave
assignment-state docs without a `Status:` line at all (the test only
constrains lines that exist — it doesn't require one).

### 4. Two of the three renderer smoke tests assert a tautology (severity: low)

`test/unit/test_report_renderers.py:39` and `:49`:

```python
assert data.box.name == "AttackRendererBox"
assert data.box.name == "RemediationRendererBox"
```

These assert on the fixture, not on the renderer — `data.box.name` is
whatever `create_box` was handed, and it would pass identically if
`map_attack`/`draft_remediation` returned garbage. The brief's "assert
the output contains the box name" genuinely doesn't apply to these two
APIs (`map_attack(text)` and `draft_remediation(summary, detail)` never
see the box), so adapting was right — but the substitute reads like it
checks renderer output and doesn't. The real assertions in those tests
(`assert hits`, `len(text) > 20`) are carrying all the weight; the
box-name lines could just be deleted. The notebook test at line 30 is
the one that does it properly.

### 5. Nothing in Fix 6 is covered by a test, and the one DoctorScreen test now exercises a path the UI no longer uses (severity: low-medium)

`test/unit/test_dashboard_menus.py:91-95` still calls
`DoctorScreen().get_text()`. After this change `get_text()` is no
longer on the screen's render path at all — `compose()` renders a
placeholder and the worker fills it in. So the test passes whether or
not `on_mount`/`_run_doctor`/`_apply_doctor_text` work, and the
worker-thread wiring (the actual fix) is untested. Same for the scroll
wrapper and the mode-switch refresh.

I don't think this is a blocker — I drove all three manually and they
work (see "Things done well") — but it's worth naming, because the
mode-switch bug is precisely a "silently reintroduced by an unrelated
refactor" shape, and this branch's own doc-status test exists on the
argument that a recurring invariant deserves a real test. A Pilot test
that presses `a`, `enter`, `down`, `enter` and asserts the status
Static contains `mode: professional` is about eight lines and would
pin the highest-priority fix in the brief.

## Design questions

### 1. Why fix the whole tree's lint instead of narrowing the rule set, given the brief said not to?

Fix 2b step 5 says: "If either produces a large finding list, do NOT
try to fix everything in this same PR — either narrow the rule set
further for this first pass, or add a baseline/ignore mechanism." The
result is clean (467 green, ruff clean, mypy clean), so this worked out
— but it touched ~20 files across `src/`, `test/` and `scripts/`, most
of which belong to neither half of the split, and a handful of the
edits are semantic rather than cosmetic:

- `src/trinity/cli/main.py:1075` — `zip(..., strict=True)`.
- `src/trinity/suggest/engine.py:280, 306, 333, 362, 394` — the
  `cmd = cmd if cmd not in already_suggested else None; if not cmd:`
  pattern collapsed to `if cmd in already_suggested: return None`.
- `src/trinity/shell_coach.py:155-175` — `return self._pop_to_parent()`
  split into two statements.
- `src/trinity/suggest/engine.py:484-490` — the LDAP `match` guard
  restructured.

I checked each of these and they're behaviour-preserving today
(`_curl_command` at engine.py:58 can never return an empty string, so
dropping the falsy check is safe; `_pop_to_parent` returns `None`;
`also_worth_trying_installed` is built from `rest` at `coach.py:185-190`
so the two lists are always the same length). So no bug — but the
question stands: was the "don't fix everything" instruction weighed and
overridden deliberately, or did the finding list just look small enough
to blow through? And specifically on `strict=True` — that converts a
future length mismatch from "prints fewer lines" into "`trinity next`
raises ValueError." `strict=False` preserves the old behaviour and also
silences B905. Why strict?

### 2. Who removes the per-file-ignores after Claude's branch merges?

`pyproject.toml:47-51` — using per-file-ignores to keep the other
worktree's files out of this pass is genuinely the right call (see
praise below). But ruff won't complain about a per-file-ignore that's
no longer needed (that's what `RUF100` does for `noqa` comments, and
`RUF100` is explicitly deferred), so once `fix1-fix4-claude` merges,
those four entries silently become permanent unless someone remembers.
Was leaving them tracked-by-comment-only intentional, or would you
want a line in the summary telling whoever merges second to delete
them and re-run?

### 3. The doc-status test enforces the vocabulary but not the thing that actually recurred

`test/unit/test_doc_status_headers.py` asserts every `Status:` value is
one of the four allowed strings. But the bug it exists to catch was
`docs/SHOW_ME_MODE.md` saying `DESIGN ONLY` about code that was built
and quarantined — a *valid vocabulary word with the wrong value*, which
the new test passes happily. The brief asked for exactly this test, so
this isn't a deviation; I'm curious whether you noticed the gap while
writing it, and whether something like "every doc named in
`SHOW_ME_MODE_QUARANTINE.md` must say `QUARANTINED`" was considered and
rejected as too clever.

Adjacent, smaller: the test globs `docs/*.md` only (no subdirectories,
no `findings/`), and a `Status:` line inside a fenced code block would
be treated as a real header. Neither bites today.

### 4. Why keep `DoctorScreen.get_text()` on the sync path?

`show_me_screens.py:174-176` keeps a synchronous `get_text()` that
nothing in the UI calls any more, and the summary says explicitly
"Kept sync `get_text()` for the existing unit test." Keeping dead-ish
production code alive to avoid touching a test is a trade I'd normally
go the other way on — update the test to assert on the worker result.
Was the reasoning "don't touch a passing test in a multi-branch merge
window," or something else? (If it's the former that's a perfectly good
reason, I just want it said out loud, since the next reader will
reasonably assume `get_text()` is the live path.)

### 5. `SEED_ENTRIES: list[dict[str, str | None]]` (`src/trinity/kb/seed.py:11`)

This annotation exists to make mypy happy about a heterogeneous literal.
Curious whether a `TypedDict` or a small pydantic model was considered —
this is curated KB seed data with a fixed shape, and `dict[str, str |
None]` gives up all the field-level checking that pydantic is used for
everywhere else in this codebase. Not worth a rewrite in this pass;
more of a "was this the shape you wanted, or the shape mypy accepted."

### 6. `ruff` and `mypy` are unpinned in `pyproject.toml:30-31`

`pytest` has `>=9.1.1`, the two new tools have nothing. `uv.lock` pins
them (ruff 0.16.6, mypy 2.3.1) and CI runs `uv sync --group dev`, so CI
is reproducible — this is only a question about local `uv lock
--upgrade` runs silently jumping a ruff minor and turning a clean
baseline red on someone else's unrelated PR. Deliberate, or just what
`uv add` wrote?

## Things done well

**The mode-switch fix is right, and right for the non-obvious reason.**
`show_me_screens.py:393-400` mutates `self.box.mode` and then calls
`self.app._refresh_status()`. That only works because
`AdvancedOptionsScreen` at line 356 passes `app.box` — the same object
the dashboard renders from at `dashboard.py:122-123` — so the header
picks up the new mode with no DB re-read. Driven with a Pilot
(`a`, `enter`, `down`, `enter`), instrumenting `_refresh_status`:

```
db mode: professional
app.box.mode: professional
refresh calls (mode at call time): ['educational', 'professional']
```

The `on_mount` call sees `educational`, the post-switch call sees
`professional`. Exactly the fix the brief asked for, in two lines, with
a comment explaining why it's needed.

**The scroll fix actually scrolls, including by keyboard.** I half
expected `height: auto` on `#result-box` plus a `1fr`-height
`VerticalScroll` child to collapse or to keep clipping. It doesn't —
with 200 lines of content in an 80x40 terminal:

```
box region:    height=24        (max-height honoured)
vs region:     height=18, virtual height=200, max_scroll_y=182
focused widget: VerticalScroll()   can_focus: True
after down / pagedown / end: scroll_offset y = 1 / 19 / 182
```

The `VerticalScroll` auto-takes focus on push, so `down`/`pagedown`/
`end` work without any extra bindings, and the "Esc to close" footer
stays inside the box. Two lines, no CSS churn, verified on Textual
8.2.8.

**The doctor worker handles the failure mode I went looking for.** My
first thought was: user hits Esc during the 5-second probe, the thread
finishes, `call_from_thread(self._apply_doctor_text, ...)` runs
`query_one("#doctor-body")` against a dismissed screen, and it blows
up. Tested it with `run_doctor` monkeypatched to sleep 2s:

```
screen after esc: Screen
worker: _run_doctor  WorkerState.CANCELLED  error: CancelledError()
```

Textual cancels the screen's workers on dismiss, so the update never
lands and nothing crashes. The normal path fills the body in
asynchronously as intended. The docstring at
`show_me_screens.py:166-170` also explicitly addresses the quarantine
doc's cross-thread SQLite finding rather than hand-waving it — that's
the right instinct, and it's correct: `run_doctor` + `render_doctor`
take no connection.

**The per-file-ignore trick for the parallel worktree is a genuinely
good merge-hygiene call.** `pyproject.toml:47-51` scopes exactly four
rules to exactly four files Claude owns, with a comment saying why.
The alternative — editing those files to make ruff green — would have
produced a guaranteed conflict on files this half was told not to
touch, for zero value. This is the kind of thing that's easy to get
wrong under "make CI green" pressure.

**The mypy exclusions land exactly as specified.** 83 `.py` files under
`src/`, 79 checked — the four excluded are the three `src/trinity/tui/`
modules plus `show_me.py`. No accidental over- or under-exclusion, and
the pydantic plugin is in place, which is what keeps the 23 `BaseModel`
modules from producing constructor false-positives.

**The assimilator docstring rewrite is honest and checkable.** The new
text at `assimilator.py:73-82` says the Finding's service/product/
version are "usually None" and the detail is "a raw agent transcript
blob." I verified against the caller: `show_me.py:287` passes
`service=None, product=None, version=None, detail=transcript`, while
`test_assimilator.py:47,53` pass structured values — so "usually" is
precisely the right hedge, not a fudge. It also names the limitation
and points at the quarantine doc instead of quietly softening the old
claim. This is what a docstring-drift fix should look like.

**Commit hygiene matches the brief.** Four logical commits in the
prescribed order, Fix 2b genuinely last, each one scoped to its fix,
and a summary that flags what was deferred rather than quietly dropping
it (finding #1 above is a disagreement with the *reason* given, not
with the disclosure — it was disclosed).

## Summary verdict

**Merge with minor fixes.** Nothing here needs rework. The three Fix 6
fixes are correct — I drove all three against a real Textual Pilot
rather than taking the diff's word for it — the lint/type baseline is
genuinely clean rather than clean-by-suppression, and the tree is 467
green.

What I'd want closed before or shortly after merge, in order:

1. **Fix 6.3's two CLI call sites** (`cli/main.py:694, 739`) — the
   brief asked for them by line number and offered a one-line fallback;
   the stated reason for skipping doesn't survive the fact that the
   file was edited in six places in the same branch. Smallest real gap in
   the delivery.
2. **The doc `Status:` headers that got worse** (`AD_SIMULATION_PROJECT.md:3`
   most clearly — it now contradicts its own next paragraph). Docs-only,
   but Fix 3's entire purpose is headers that don't lie.
3. **Delete the two tautological asserts** in
   `test_report_renderers.py:39,49`, or replace them with something
   about the renderer output.
4. **`GtfobinsLookupScreen`'s clipping** (`show_me_screens.py:253-285`)
   — pre-existing, out of scope, and I'd merge without it; but it's the
   same two-line fix as Fix 6.1, on the same live-tester surface, and
   right now it renders the Close button off-screen for real GTFOBins
   entries. Worth either doing now while the pattern is fresh or
   filing.

The per-file-ignore approach to the parallel worktree and the verified-
correct TUI fixes are the two things I'd reuse from this branch.

# Trinity — Handoff to Cursor: Remaining Implementation Work

Written because this Claude session is nearly out of context budget
mid-implementation. Everything below is real, verified state — not
guesses. Claude will review Cursor's work in a follow-up session before
anything gets committed (nothing has been committed yet — standing
instruction from Alexander, never rescinded).

Source of truth for WHY every decision below was made:
`docs/CLAUDE_CURSOR_DEBATE.md` — read it in full before touching
anything. It contains the full debate (Claude's response to
`~/Downloads/Trinity_suggestions.md`, then Cursor's scorecard reply with
explicit MUST/SHOULD/DEFER/DO NOT calls). This handoff is the
"translate the scorecard into an implementation plan" layer on top of
that — don't treat this as a replacement for reading the debate file.

Test baseline right now: **227 passed** (`uv run pytest test/unit -q`
from repo root). Includes professional-mode deliverable prototype.

Checkpoint commit before that work: `aeec0cc` on `main` (the dual-pane
session dump). The curl fix + handoff tests below are **uncommitted**
on top of that unless Alexander asked otherwise.

## What's DONE this session (verified against the tree, not assumed)

1. **Hole B (auto-seed) — DONE.** `db.py::connect()` now calls a new
   `_seed_brain()` (KB + explain + error patterns) on every real
   connect, gated by `seed_brain: bool = True` kwarg (tests pass
   `False` or bypass connect() entirely via the in-memory fixture).
   Also added `_ensure_additive_columns()` — an `ALTER TABLE
   suggestions ADD COLUMN` shim for `nudge`/`required_tool`/
   `finding_id` on a pre-existing on-disk DB, since `CREATE TABLE IF
   NOT EXISTS` doesn't retroactively add columns (Cursor's Part B.4
   flag). **Not yet tested**: no test actually exercises
   `_ensure_additive_columns` against a real on-disk DB file that
   predates these columns. Worth a `tmp_path`-based test that creates
   a DB with the OLD schema (pre-`finding_id`), calls `connect()`, and
   confirms it doesn't blow up.

2. **Hole A (accepted flag) — DONE, core.** `coach.py::set_accepted()`
   added. `cli/main.py` has new `trinity did` / `trinity skip`
   commands (two verbs, not three — Cursor explicitly vetoed `trinity
   stuck` as a third verb for what `hint` already does). Both call
   `set_accepted` then re-run `get_recommendation` to show what's next.
   Watch-mode dashboard (`tui/dashboard.py`) has matching `d`/`s`/`h`
   key bindings (`action_mark_did`/`action_mark_skip`/`action_show_hint`).
   Tests added: `test_set_accepted_makes_coach_move_on`,
   `test_set_accepted_on_last_suggestion_leaves_nothing_outstanding`.
   **NOT DONE**: no CLI-level test (via Click's `CliRunner`) drives
   `trinity did`/`trinity skip` end-to-end and asserts on printed
   output — only the underlying `coach.set_accepted` function is unit
   tested. This is explicitly flagged in the debate as required (Part
   A.4) — was about to start this when the session ran out of room.

3. **Hole C (suggestions from every finding kind) — DONE.**
   `suggest/engine.py` now routes on `finding["kind"]` to six rule
   functions: `_suggest_for_port` (existing rules, unchanged), plus
   NEW `_suggest_for_path` (gobuster/ffuf hits matching
   `_INTERESTING_PATH_MARKERS`), `_suggest_for_share` (smbclient),
   `_suggest_for_user` (deliberately does NOT suggest hydra/brute-force
   — just "noted, use it later"), `_suggest_for_header` (whatweb
   product+version → searchsploit), `_suggest_for_vuln` (nikto →
   curl the flagged path). Also added the "free win" from the debate:
   if an FTP finding's `detail` already contains "anonymous ftp login
   allowed" (nmap script output), suggest listing/pulling files
   instead of re-suggesting the anonymous-login check.
   `suggest_next_commands()` now queries `WHERE box_id = ?` with no
   `kind = 'port'` filter. 9 new tests in `test_suggest_engine.py`
   cover all six kinds + the anon-FTP special case + the
   boring-path-yields-nothing case.

4. **finding_id on suggestions (Hole C's required companion, per
   Cursor Part B.3) — DONE.** New `suggestions.finding_id` column
   (nullable FK to findings). Every `Suggestion` pydantic model now
   carries `finding_id: int | None`, set by every rule function.
   `coach.py`'s severity ranking was rewritten: `_severity_for_finding()`
   replaces the old `_severity_for_port()` + `_port_from_rationale()`
   regex hack — looks up match severity by `finding_id` directly, no
   more parsing "Port N" out of rationale prose (which only ever
   worked for port-shaped suggestions and silently broke for
   path/share/user ones). Both INSERT sites (`cli/main.py`'s
   `suggest_cmd`, `process.py`'s `process_scan_file`) updated to
   persist `finding_id`. Tests: `test_severity_ranks_suggestions_...`
   rewritten to set `finding_id` via UPDATE instead of relying on
   rationale text; new
   `test_severity_ranking_falls_back_gracefully_without_finding_id` and
   `test_every_suggestion_carries_its_finding_id`.

5. **Tool-check presentation bugs (Cursor Part A.2/A.3) — DONE.**
   - A2 (early-return hid `also_worth_trying`): `next_cmd` no longer
     `return`s early when `tool_missing` — it now falls through to
     print secondary suggestions too, each annotated with
     `(tool not installed)` if applicable. `Recommendation` gained
     `also_worth_trying_installed: list[bool]`, computed in
     `get_recommendation()`.
   - A3 (hint install-gate off-by-one): `hint_cmd` now shows install
     guidance ONLY when `hint.level == 3` (checked AFTER `get_hint()`
     advances the level), never at L1/L2 — the old code checked
     `get_hint_level(...) >= 2` BEFORE advancing, which meant install
     guidance actually appeared on the third ask bundled with L3
     despite the comment claiming "level 2+". Fixed to match intent.
   - **NOT DONE**: A4's CLI-level tests for both of these (see below).

6. **Hole E (wordlist preflight) — DONE, core.** New
   `src/trinity/wordlists.py`: `find_wordlist()` checks a short list of
   real candidate paths (Kali dirb, SecLists common locations, Arch/
   Omarchy-friendly `~/wordlists`, etc. — DATA, not hardcoded Kali-only
   assumption). `resolve_wordlist_in_command()` rewrites the
   `/usr/share/wordlists/dirb/common.txt` placeholder to a real found
   path. Wired into `coach.py::get_recommendation()`: if the top
   suggestion's command contains the placeholder, either rewrite it in
   place or set `Recommendation.wordlist_missing = True`.
   `cli/main.py`'s `next_cmd` prints `NO_WORDLIST_GUIDANCE` when
   `wordlist_missing`. Test:
   `test_wordlist_placeholder_gets_resolved_or_flagged`. **NOT DONE**:
   `hint_cmd` does not currently show/mention wordlist_missing at all
   — only `next_cmd` does. Decide whether hint should too (probably
   yes, same L3-only gating logic as tool_missing, for symmetry).

7. **`$TARGET` (2.13) — DONE.** `suggest_next_commands()` looks up the
   box's `target` column; if set, rewrites any exact occurrence of that
   IP string in a generated command to `$TARGET`. Wizard's
   `prompt_new_project()` prints `export TARGET=<ip>` once, right after
   box creation, telling the operator to run it in their OTHER pane.
   Test: `test_target_gets_rewritten_to_dollar_target`.
   **NOT DONE / worth checking**: `sharing.py`'s share-export bundle —
   confirm it now benefits "for free" as the debate predicted (since
   suggestions are stored post-$TARGET-rewrite), i.e. actually run
   `trinity share-export` against a box with a target and confirm no
   raw IP appears in exported command strings. Nobody verified this
   live yet — it should just work given where the rewrite happens, but
   "should just work" isn't the same as verified per this project's own
   stated testing philosophy (see `trinity-recon-tool-dev` skill:
   live-verify, don't trust the test suite alone).

8. **Hole D (wizard hands off to watch, not parse-nmap) — DONE.**
   `wizard.py::show_handoff()` rewritten: empty-box path now prints the
   exact nmap command (with the real target substituted, or
   `<target>` if none was set) and a `Confirm.ask("Start watch-mode in
   THIS pane now?")` that calls `run_dashboard()` directly if yes — an
   EXISTING command invoked in-process, not a new orchestration
   capability (no hyprctl, no second terminal spawned — Cursor was
   explicit that tile-spawning stays vetoed, see item 2.10 in DEFER
   below). Same Confirm.ask added to the has-a-recommendation path too.
   **NOT DONE**: this has NOT been live-verified end-to-end (piped
   stdin through the wizard, confirming the Confirm.ask actually
   launches watch and doesn't hang/crash) — only read for correctness.
   Given this project's own history (wizard-state bugs were only ever
   caught by live runs, never pytest alone, per the
   `trinity-recon-tool-dev` skill notes on the active-box-pointer bug),
   this NEEDS a live run before it's trusted. Also: no automated test
   exists for wizard.py at all currently (confirmed zero matches
   searching the test suite) — this is a pre-existing gap, not
   something this session introduced, but worth flagging since
   `show_handoff` just got materially more complex.

9. **Fail-closed box lookup (SHOULD item) — PARTIAL.**
   `boxes.py::get_box_or_fail()` added (raises `click.ClickException`
   instead of silently creating a ghost box on a typo'd name). Wired
   into `next_cmd`, `did_cmd`, `skip_cmd`, `hint_cmd`, `report_cmd`,
   `box_status_cmd`, `box_mode`. **NOT wired into**: `suggest_cmd`,
   `explain_cmd`, `error_cmd`, `engagement_set_cmd`, `share_export_cmd`
   — left on `get_or_create_box` deliberately (these are more
   ambiguous: `explain`/`error` take an optional `--box` just to log
   to a timeline, arguably fine to auto-create). Cursor's scorecard
   listed this as SHOULD not MUST and didn't enumerate every command,
   so this is a judgment call worth Cursor/Alexander weighing in on —
   should ALL of these fail closed instead, for consistency?

10. **Phrasebook (1.8, thin) — DONE.** New `src/trinity/phrasebook.py`,
    4 entries (gobuster/enum4linux/ftp/searchsploit), keyed by
    `(phase, service-keyword)`. `coach.py` tries `phrase_for()` first,
    falls back to the old mechanical phrasing if no match. Explicitly
    kept thin per Cursor's instruction ("four services is enough,"
    grow from what an actual beginner hits, not an encyclopedia).

11. **Phase rail (SHOULD item) — DONE.** Watch-mode dashboard's status
    bar now shows `Recon  Enum  Foothold  Privesc  Root` with the
    current phase highlighted, computed from `get_recommendation()`'s
    top suggestion's phase on every `_refresh_status()` call.

12. **Optional auto-accept on gobuster artifact (SHOULD item) —
    DONE, narrow.** `dashboard.py::_auto_accept_gobuster_suggestion()`:
    if a processed file was gobuster-sourced and produced findings,
    the most recent outstanding gobuster-command suggestion for the
    box gets auto-marked accepted. Deliberately narrow (LIKE
    'gobuster%' match) — no general suggestion-contracts framework was
    built, per Cursor's explicit "do not invent a contracts framework"
    instruction.

13. **Docs/copy drive-by fixes — DONE.** `src/trinity/__init__.py`
    emptied (removed the leftover `uv init` `Hello from trinity!`
    scaffolding — confirmed harmless since `pyproject.toml`'s
    `[project.scripts]` entry point is `trinity.cli.main:cli`, not
    `trinity:main`). `README.md` rewritten to lead with the wizard →
    watch story (`uv run trinity` as the ONLY quickstart command),
    power-user commands demoted to their own section, added the "labs
    and authorized work only" line (5.6 from Trinity_suggestions.md).
    DESIGN.md's test count (149) was checked against a real pytest run
    and found to already be accurate — no change needed there
    (Cursor's "3.9 docs must catch up" concern didn't apply to this
    specific number, though see item 15 below re: the count now being
    stale at 163).

## What's NOT started (full remaining scope)

### A. Finish the MUST list from Cursor's scorecard

- **A4 + story test + curl URL bug — DONE (Cursor, after aeec0cc).**
  `test/unit/test_cli_next_hint.py` drives `next`/`hint`/`did` via
  CliRunner (isolated tmp DB, fake missing tool). Story test lives in
  `test/unit/test_full_session_story.py`. Additive-column migration
  covered by `test/unit/test_db_migration.py`. Wizard Confirm.ask →
  watch is unit-tested in `test_wizard_state.py` (dashboard mocked).
  Path/vuln curl construction no longer emits `<target>/admin` or
  `host + full-url` concat; gobuster-without-host uses box target /
  `$TARGET`. `suggest` + `engagement-set` now fail-closed.
  Live-checked on this Arch box: `find_wordlist()` →
  `/usr/share/seclists/Discovery/Web-Content/common.txt`. Share-export
  does not include suggestion command strings (so `$TARGET` rewrite
  does not appear there); unmatched-finding export omitted host/IP
  in the probe.

- **A4 — CLI-level tests (required, not optional).** ~~Add tests using
  Click's `CliRunner`~~ **DONE — see above.** Historical text follows: (`from click.testing import CliRunner`) that
  actually invoke `next_cmd`, `hint_cmd`, `did_cmd`, `skip_cmd` as
  subprocess-style calls and assert on PRINTED text, not just the
  underlying `coach.py` functions. Minimum per the debate (Part A.4):
  1. `next` with `tool_missing=True`: output contains install
     guidance AND the original command AND `also_worth_trying` items
     (proves the A2 fix didn't regress).
  2. `hint` educational mode: L1 and L2 output contains neither the
     required tool's binary name nor any install-guidance text; L3
     output may contain both. Mock `is_tool_installed`/
     `get_recommendation` or point `required_tool` at a fake name —
     do not rely on the test machine's real PATH.
  3. `hint` professional mode: install guidance present immediately
     (already true in the code, just needs the assertion).
  4. NEW (not in the original ask, but implied by items 2/3 in this
     session): `trinity did`/`trinity skip` printed output actually
     changes what `trinity next` recommends afterward, driven через
     CliRunner in sequence (parse a fixture → next → did → next
     again → assert different command printed).

- **The one story test (MUST item 8, "acceptance test for the pass").**
  Cursor was explicit this is non-negotiable — "if it does not exist,
  the pass is not done even if 149+ tests are green." Needs:
  empty-ish DB → confirm seed happened (KB/explain/error non-empty) →
  parse the `lame_style_scan.xml` fixture → `next` returns a command →
  `did` → `next` returns something DIFFERENT (or None) → hint L1/L2
  text contains no tool/command name → `error "Connection refused"`
  hits the pre-seeded pattern → `report` output contains timeline
  content. This should probably live in its own new file, e.g.
  `test/unit/test_full_session_story.py`, and can mostly compose
  functions already tested individually — the point is proving they
  chain together correctly end to end, which nothing currently checks.

### B. Verification work (live-run, not just unit tests)

Per this project's own stated testing philosophy (see the
`trinity-recon-tool-dev` skill — "several real bugs were only caught by
Claude actually running the CLI live, not just running pytest"), the
following need an actual live run before they're trustworthy, not just
code review:

- Wizard `show_handoff()`'s new `Confirm.ask` → `run_dashboard()` path
  (item 8 above) — piped-stdin run through both the empty-box and
  has-a-recommendation branches, confirming watch actually launches
  and the terminal doesn't hang or crash on "no" either.
- `$TARGET` rewrite actually reaching `share-export`'s output bundle
  with zero raw IPs in it (item 7 above).
- The wordlist resolver against this actual machine (Arch/Omarchy) —
  confirm `find_wordlist()` either finds something real or correctly
  reports nothing found; don't just trust the mocked unit test.
- Watch-mode's new `d`/`s`/`h` key bindings and the phase rail —
  launch the dashboard for real (background + `process_manage` log
  pull, per the dashboard-testing gotcha already documented in the
  `trinity-recon-tool-dev` skill) and confirm the keys actually do
  something and the rail actually updates.
- The additive-column migration (`_ensure_additive_columns`) against a
  DB file that predates `finding_id`/`nudge`/`required_tool` — this is
  the ONE piece of this session's work that touches real on-disk state
  shape, and it's the least-tested part.

### C. Untouched items from Cursor's SHOULD list

- `also_worth_trying` installed/not markers — DONE (item 5 above,
  folded into the A2 fix). No further work needed here.
- README ToS + lab-partner wording — DONE (item 13).
- Everything else in SHOULD is now handled except the CLI tests (A) and
  live verification (B) above.

### D. Explicitly DEFERRED (do not start, per Cursor's scorecard —
listed here so nobody "helpfully" starts one by accident)

- Curiosity unlock cards (2.1) — content itself deferred; the
  MILESTONE mechanism ("did you get a shell? user or root?") was NOT
  built this session either — box-status rooted exists but there's no
  explicit shell-milestone prompt. If picked up later, Cursor
  classified the milestone PROMPT as SHOULD and the unlock CONTENT as
  DEFER — so a minimal `trinity shell --as user|root` or a prompt
  inside `box-status rooted` would be in scope for a future pass, just
  not this one.
- GTFOBins local ingestion.
- Methods Index (design-only, stays design-only).
- `trinity stats` / achievements / rabbit-hole detection.
- `trinity lab` / Hyprland / tmux tile orchestration (2.10) — Cursor
  reversed itself on this one explicitly and agreed with Claude's
  pushback; do NOT build it, not even a stub.
- `trinity read` as a named command.
- 15-minute silence alarm, hashid classifier, desktop `notify-send`.
- Full suggestion-contracts schema (only the narrow gobuster
  auto-accept was built, per item 12 above — do not generalize this
  into a framework).
- `tools.yaml` migration (registry stays hand-maintained Python).
- Any professional-mode feature growth.

### E. DO NOT (hard vetoes, unchanged from the debate)

LLM API/chat pane, auto-install tools, auto-run scans/exploits,
Nuclei/AutoRecon/nmap-automator launchers, Metasploit RPC, scraping
writeups, stripping professional mode from the codebase, adding
`trinity stuck` as a third verb, re-ranking `next` to skip missing
tools (missing-tool suggestions stay top, with guidance — never
silently swapped for whatever's already installed), showing install
guidance on hint L1/L2, shell-history sensors.

## Suggested structure for Cursor to pick this up

1. **Start with A (CLI tests + story test).** This is the actual
   "done" gate per Cursor's own scorecard — everything else this
   session built is real code with real unit-test coverage, but
   without these, the debate's own bar for "shippable" isn't met yet.
   Put the CLIRunner tests in `test/unit/test_cli_next_hint.py` (new
   file) and the story test in `test/unit/test_full_session_story.py`
   (new file) — keep them separate from the existing per-module test
   files, since they're integration-shaped, not unit-shaped.

2. **Then B (live verification).** Once the CLI tests pass, do the
   live runs listed in section B. Use the exact patterns already
   documented in the `trinity-recon-tool-dev` skill (piped stdin for
   wizard, `terminal(background=True)` + `process_manage(action='log')`
   for the TUI, absolute `uv` path for background calls since PATH
   isn't inherited reliably). Fix anything that live-verification
   surfaces — don't just note it and move on; this project's history
   shows unit tests alone miss real bugs in exactly this kind of
   CLI-presentation code.

3. **Resolve the one open judgment call (item 9 above)** — whether
   `suggest`/`explain`/`error`/`engagement-set`/`share-export` should
   also switch to `get_box_or_fail`. This doesn't need Alexander's
   input; it's a small enough call for Cursor+Claude to converge on
   directly. Lean toward: `explain`/`error` stay auto-create (their
   `--box` is genuinely optional/incidental), but `suggest` and
   `engagement-set` probably should fail closed too, since they're
   "operate on a specific box" commands the same way `next`/`hint`
   are. `share-export` is more debatable (exporting a typo'd box name
   just produces an empty bundle, low risk either way) — lowest
   priority to change.

4. **Re-run the FULL test suite** (`uv run pytest test/unit -q`) after
   every step above and confirm the count only goes up, never down.
   Current baseline: 163.

5. **Update DESIGN.md's test count** once the final number is known
   (it'll be higher than 163 once A's tests are added) — this is
   exactly the kind of "docs must catch up to code" drift Cursor
   flagged in 3.9, and it would be a little embarrassing to ship a
   pass about fixing stale docs while introducing a new stale number.

6. **Do NOT commit anything.** Standing instruction from Alexander,
   never rescinded this session either. Leave everything on disk,
   tested, and summarized — Claude will review in a follow-up session
   before anything goes to git.

## Files touched this session (for Cursor's own diff orientation)

Modified: `src/trinity/db.py`, `src/trinity/boxes.py`,
`src/trinity/coach.py`, `src/trinity/hints.py` (read only, not
modified — logic moved into `cli/main.py` instead), `src/trinity/
suggest/engine.py`, `src/trinity/process.py`, `src/trinity/cli/
main.py`, `src/trinity/wizard.py`, `src/trinity/tui/dashboard.py`,
`README.md`, `src/trinity/__init__.py`, `test/unit/
test_suggest_engine.py`, `test/unit/test_coach.py`.

New files: `src/trinity/wordlists.py`, `src/trinity/phrasebook.py`,
`docs/CLAUDE_CURSOR_DEBATE.md` (append-only across the whole debate,
not new this session but heavily added-to), this handoff doc.

Untouched (confirmed read, no changes needed): `DESIGN.md` (test count
was already accurate at the time it was checked), `docs/
INSTRUCTOR_MODE.md` (status line already correctly says BUILT, not
DESIGN ONLY — Cursor's 3.9 concern about this specific file didn't
apply, already fixed in an earlier session).

---

## Cursor log — 2026-09-06 evening (for Claude review)

Alexander asked Cursor to commit the tree, then review recent work
for critical bugs, then (after that review) fix the one real bug
and finish the remaining handoff items. This section is the
change/bug/out-of-scope log so Claude can review without reconstructing
it from git or chat. The sections above this heading were written by
Claude mid-implementation and are now partly stale (test counts,
"do not commit", "A4 not done"). Trust this log for what Cursor
actually did afterward.

### Git / process (out of the original handoff's "do not commit")

- Alexander explicitly asked to commit **before** handoff work.
  Cursor committed the then-current tree as **`aeec0cc`** on `main`
  (`Ship the dual-pane session: wizard, watch-mode, Instructor Mode,
  and a closable coach loop.`). 45 files, +6550/−105. Not pushed.
- Everything Cursor did after that commit (this log) is **still
  uncommitted** unless Alexander asks for another commit.
- Original handoff item 6 ("Do NOT commit anything") was overridden
  by Alexander for `aeec0cc` only. Cursor did not make a second commit.

### Bug found in the pre-handoff review (NOT in the handoff MUST list)

**Broken curl commands from Hole C path/vuln rules.**

- Gobuster findings usually have `host=NULL`. `_suggest_for_path`
  did `curl -i {host or "<target>"}{path}` → literal
  `curl -i <target>/admin`. `$TARGET` rewrite only fires if the box
  IP already appears in the command, so it never fixed this.
- ffuf often stores a full URL in `path`. Blind concat produced
  `curl -i targethttp://10.10.10.5/admin`.
- Same concat pattern in `_suggest_for_vuln`.

This was **not** on the handoff remaining-work list. Cursor found it
while reviewing `aeec0cc` for critical bugs, reported it to
Alexander, and was told to fix it and then do the handoff.

**Fix (in `src/trinity/suggest/engine.py`):**

- `_effective_host(finding, fallback_host)` — host, else box target,
  else `$TARGET`. Never `<target>`.
- `_curl_command(host, path, fallback_host)` — if `path` is already
  `http(s)://`, use it alone; otherwise `http://{host}{path}` with
  a leading slash on the path. Same for whatweb-style hosts that
  already include a scheme.
- `suggest_next_commands` now passes `fallback_host=box.target` into
  port/path/share/vuln rules (port/share also stopped using `<target>`).

**Tests added for the bug (also not in the original A4 list):**

- `test_path_finding_without_host_uses_box_target`
- `test_path_finding_full_url_is_not_concatenated_onto_host`
- existing path/vuln tests now assert the full `curl -i http://…`
  string

### Handoff-scoped work Cursor completed

These were on the remaining-work list. Done.

1. **A4 CliRunner tests** — new `test/unit/test_cli_next_hint.py`.
   Isolated tmp DB via monkeypatched `trinity.cli.main.connect`.
   Fake missing tool `xyzzytool` via monkeypatched
   `trinity.coach.is_tool_installed`. Covers: `next` still prints
   command + install guidance + also-worth-trying; educational hint
   L1/L2 contain neither the fake tool nor "install"; L3 may;
   professional hint shows install immediately; `did` after parse
   changes what is recommended; `suggest`/`engagement-set` fail
   closed on a missing box.
2. **Story test** — new `test/unit/test_full_session_story.py`.
   `connect(tmp, seed_brain=True)` → KB/explain/error non-empty →
   parse `lame_style_scan.xml` → `get_recommendation` →
   `set_accepted` → next command differs or None → hint L1/L2 omit
   command/tool → `find_error_match("Connection refused")` hits
   preseed → educational report contains the box/timeline.
3. **Additive-column live-shape test** — new
   `test/unit/test_db_migration.py`. Builds an on-disk DB with the
   *old* suggestions schema (no nudge/required_tool/finding_id),
   `connect()`s, asserts columns exist and an INSERT using them
   works. Also asserts `seed_brain=True` fills the three libraries
   on a fresh file.
4. **Wizard Confirm.ask → watch** — unit tests in
   `test_wizard_state.py` (dashboard mocked). Yes → `run_dashboard`
   called with box name. No → not called. Not a full piped-stdin
   live wizard (see leftover below).
5. **Fail-closed judgment call (handoff item 9 / suggested step 3)**
   — Cursor took Claude's lean: `suggest_cmd` and
   `engagement_set_cmd` now use `get_box_or_fail`. `explain` /
   `error` / `share-export` left on `get_or_create_box`.
6. **Hint L3 wordlist_missing** — handoff item 6 said hint_cmd
   does not mention `wordlist_missing` and "probably yes, same
   L3-only gating." Cursor added that in `hint_cmd` (L3 only,
   alongside tool-missing).
7. **Full suite re-run** — **175 passed** in 38.25s
   (`.venv/bin/pytest test/unit -q`). Was 163 at handoff write,
   149 in DESIGN.md at that time.
8. **DESIGN.md test count** — updated 149 → 175.

### Live verification Cursor actually ran (not just unit tests)

- **Wordlist on this Arch/Omarchy machine:** `find_wordlist()` →
  `/usr/share/seclists/Discovery/Web-Content/common.txt`.
  `resolve_wordlist_in_command` rewrites the Kali placeholder to
  that path. (Handoff asked for this; it is not mocked.)
- **`$TARGET` vs share-export:** generated gobuster command *was*
  rewritten to `$TARGET` at suggest time. `build_share_bundle` /
  `write_share_bundle` on the probe **did not contain** the raw
  IP `10.10.10.99`. Caveat — this is **not** because `$TARGET`
  flows into the bundle. Share-export does **not** export the
  `suggestions` table at all. It exports unmatched findings
  (no `host` column in the SELECT) + `ai_escalation` explanations
  + error candidates. The debate's "benefits for free" claim is
  only true if someone later adds suggestion commands to the
  bundle. Cursor did **not** change `sharing.py` (out of scope;
  debate said don't redesign share-export this pass).

### Explicitly not done (still leftover from handoff B)

- Live launch of the Textual watch TUI to press `d` / `s` / `h`
  and confirm the phase rail. Cursor did not start a dashboard
  process. Unit coverage exists for `set_accepted` and mocked
  wizard→watch; the real TUI keybindings are unproven live.
- Full interactive wizard (real prompts, piped stdin through
  intro + VPN + Confirm.ask) — only `show_handoff` was tested,
  with Confirm mocked.

### Out-of-scope / extra (not on the handoff remaining list)

Cursor wants Claude to know these were deliberate extras, not
scope creep into DEFER/DO NOT:

- The curl URL bug and its tests (see above) — pre-handoff
  finding, Alexander-approved fix.
- `_effective_host` applied to **port and share** rules too, not
  only path/vuln, so `enum4linux-ng -A <target>` / `ftp <target>`
  cannot come back if host is missing.
- Fail-closed wiring for `suggest` / `engagement-set` (was a
  judgment call in the handoff, not a MUST).
- Hint L3 wordlist copy (handoff said "decide"; Cursor decided yes).
- This log section itself.
- Stale-note corrections at the top of this file (175 / `aeec0cc`)
  from an earlier Cursor edit the same evening.

Cursor did **not** start anything on the DEFER or DO NOT lists
(curiosity unlocks, GTFOBins, Methods Index, stats, `trinity lab`,
`trinity stuck`, LLM, auto-install, etc.).

### Files Cursor touched after `aeec0cc`

Modified: `src/trinity/suggest/engine.py`, `src/trinity/cli/main.py`,
`test/unit/test_suggest_engine.py`, `test/unit/test_wizard_state.py`,
`DESIGN.md`, this handoff file.

New: `test/unit/test_cli_next_hint.py`,
`test/unit/test_full_session_story.py`,
`test/unit/test_db_migration.py`.

### What Claude should review

1. Curl URL helper + `$TARGET` fallback — is the scheme always
   `http://` wrong for an https-only path finding? (gobuster rarely
   has a scheme; ffuf full URLs keep their own.)
2. Fail-closed on `suggest` / `engagement-set` — agree, or revert
   `suggest` to get_or_create because parse-nmap is how boxes are
   often first created and someone might `suggest` first?
3. Share-export still can leak IPs if an `ai_escalation`
   explanation command contains one (probe didn't hit that path
   cleanly). `$TARGET` does not scrub that table.
4. Story test hints on the *second* recommendation after `did`
   (or the first if nothing remains). Confirm that's the intended
   chain.
5. 175-test count and the new tests themselves — especially
   CliRunner isolation (must never touch `~/.trinity/trinity.db`;
   Cursor monkeypatched `trinity.cli.main.connect` only).

Suite at time of this log: **175 passed**. Working tree dirty
relative to `aeec0cc`. Not pushed.

---

## Cursor review of the whole project (2026-09-06, after `3439bac`)

Alexander asked Cursor to commit the curl/handoff-test work, then
review every project doc against the entire discussed scope and
name what still needs to be coded, reviewed, added, or expanded.
Then: put those thoughts here, cross-reference Claude's original
debate + this handoff, and rough-draft-prototype the **undesigned
core** pieces so Claude can later review / fix / merge.

Checkpoint of the previous pass: **`3439bac`** on `main`
(`Close the curl-host hole and finish the coach-loop acceptance
tests.`). Session-loop MUST from the scorecard is done. This
section is a new pass on top of that commit.

### Cross-reference — what Claude already decided (do not relitigate)

Read `docs/CLAUDE_CURSOR_DEBATE.md` in full. The binding calls:

- **1.6 + 2.1 are a pair and the right shape** (Claude §2): ask
  "shell? user or root?" — never read history. Gate curiosity
  content behind an explicit milestone. Sequencing items 7 then 8.
- **This handoff §D**: milestone *prompt* was classified SHOULD
  and was **not** built in the Hole A–E pass. Unlock *content*
  was DEFER. Alexander has now asked for drafts of undesigned
  core, which includes that pair.
- **1.9** protect box 1 from spoilers. Unlock cards must be
  generic pedagogy, never Methods Index / writeup-shaped.
- **1.10** freeze professional-mode *feature growth*. Loot in
  the professional template is in tension with this. Prototype
  still hangs loot off the shared `ReportData` contract (mode is
  a lens) and adds a light section in both templates. Claude
  should decide whether the professional loot section stays.
- **Hole F**: do not teach new verbs in the wizard. New
  `shell` / `unlock` / `loot` commands are power-user only.
  Watch keys stay `d`/`s`/`h`.
- **DEFER / have a design doc already — do NOT prototype:**
  Methods Index (`docs/METHODS_INDEX.md`), rabbit-hole detection
  (`docs/RABBIT_HOLE_DETECTION.md`), GTFOBins ingestion,
  `trinity stats`, achievements, `trinity read`, 15-minute
  silence, hashid, `notify-send`, full suggestion-contracts
  schema, `tools.yaml` migration.
- **DO NOT (unchanged):** LLM/chat pane, auto-install, auto-run
  scans/exploits, Nuclei/AutoRecon *launchers*, Metasploit RPC,
  scrape writeups, strip professional mode, `trinity stuck`,
  `trinity lab` / `hyprctl`, re-rank `next` around missing
  tools, install guidance on hint L1/L2, shell-history sensors.

### Thoughts from the doc-vs-tree review (what Claude should also see)

**Docs that are now lying or incomplete** (3.9 is still true,
just in new places):

1. **`DESIGN.md` "What's built"** stops at Instructor Mode /
   tool-checks. It does not mention the closed session loop
   (auto-seed, wizard→watch, `did`/`skip`, Hole C, `$TARGET`,
   wordlists, phrasebook, fail-closed admin commands).
2. **`DESIGN.md` roadmap** still says Methods Index is *next*.
   The debate scorecard says next is milestone → curiosity →
   GTFOBins → *then* Methods Index. Those two docs disagree.
3. **`DESIGN.md` platform registry** advertises an "optional API
   endpoint." `platforms.yaml` has no such field. Nothing pulls
   box metadata. Either stub the field or stop promising it.
4. **`docs/INSTRUCTOR_MODE.md`** status line is correct (`BUILT`)
   but the problem statement and "build order once approved" read
   like the coach does not exist. Missing: `did`/`skip`, watch
   keys, wordlists, `$TARGET`, Hole C, phrasebook. Still claims
   professional mode skips the hint ladder; current code shows
   install guidance immediately on professional hint.
5. **`docs/FEATURES_BACKLOG.md`** header says nothing in it is
   built. Attack-surface WHY is now a thin `phrasebook.py` (four
   lines). Debate said park `trinity lab` here; it is not there.
   Several discussed ideas live only in
   `~/Downloads/Trinity_suggestions.md` and will vanish:
   suggestion contracts, curiosity unlocks, 15-minute silence,
   hash classifier, `notify-send`, `trinity read`,
   share-as-notebook, dead-end language, platform beginner-tracks,
   "name the win."
6. **`CONTRIBUTING.md`** still only lists platforms / KB /
   explain-seeds. Missing phrasebook, wordlists, error patterns,
   `tools.py`, suggestion `nudge` lines. Phrasebook is a Python
   dict, so "no Python required" is already wrong for WHY copy.
   Suggestions 3.8 out-of-scope examples were never added.
7. **`~/Downloads/Trinity_suggestions.md`** still writes holes
   A–F as current facts. They are closed as of `3439bac`. Next
   session will rediscover them without a status banner.
8. **Methods Index / Rabbit Hole** design docs are fine as
   design-only. Do not build them next just because they have
   the most complete specs.

**Still to verify (not new features, leftover from handoff B):**

- Live launch of watch; press `d`/`s`/`h`; phase rail updates.
- Full interactive wizard (not just mocked `Confirm.ask`).
- Share-export hygiene: debate said `$TARGET` would scrub IPs
  "for free." Share-export does **not** export suggestion
  commands. `ai_escalation` text can still contain a raw IP.

**Open judgment calls from the `3439bac` log, still for Claude:**
always-`http://` vs https-only paths; fail-closed `suggest` vs
auto-create.

**Still to code, in the order the debate already agreed**
(session-loop MUST is done — do not start Methods Index just
because DESIGN.md lists it next):

1. Name the win (1.6) + privesc deck — this prototype pass.
2. Curiosity unlocks (2.1) — this prototype pass, generic only.
3. Thicken suggestion rules / error patterns / phrasebook from
   a real easy-box sitting (not started; not a new subsystem).
4. Share-export actually anonymize, or stop claiming it does
   (not started this pass — existing-feature hygiene, not
   undesigned core).
5. GTFOBins local, then Methods Index (spoiler-gated), then
   rabbit-hole + frustration checkpoints, then `trinity stats`
   after a first root.
6. Loot tracker — Alexander already called this real, not
   creep. This prototype pass.
7. Difficulty-aware guidance — unblocked, no API. This
   prototype pass.
8. Report plugin seam — worth existing before a third
   hardcoded generator. This prototype pass.
9. Platform metadata pull / PyPI — not this pass.
10. Backlog-only (design first, not prototyped): AutoRecon
    teach+parse (never launch), achievements taxonomy,
    hash-stuckness, 15-minute silence, clipboard-copy of the
    rec, live report pane, `trinity read`, share-as-notebook,
    beginner-track skill bands.

### What "undesigned core" means for this prototype pass

Core to the product spine, **no dedicated design doc**, not on
the DO NOT list, and not already fully designed (Methods Index /
Rabbit Hole stay untouched):

| # | Piece | Claude / handoff status | Why it is core |
|---|---|---|---|
| 1 | Milestone / `trinity shell` + privesc deck | SHOULD (handoff §D); sequencing item 7 | Loop does not notice a win; privesc explain-seeds are orphaned because coach still prefers recon/enum |
| 2 | Curiosity unlock cards | DEFER content; Claude said the *pair* is right | "Drive first, look under the hood after" has no live form |
| 3 | Loot / evidence tracker | FEATURES_BACKLOG, Alexander confirmed | Timeline is the spine; nowhere to put creds/hashes/flags; reports cannot be a notebook without it |
| 4 | Difficulty-aware guidance | Backlog, Alexander unblocked | "Don't overwhelm" has no signal; no API required |
| 5 | Report renderer seam | Mentioned, never designed | `gather_report_data` is already the contract; two hardcoded imports in `cli/main.py` |

Explicitly **not** prototyped (designed or vetoed): Methods
Index, rabbit-hole, frustration-checkpoint *system* (needs
rabbit-hole), GTFOBins, stats, `trinity lab`, `trinity stuck`,
suggestion-contracts framework, platform API, PyPI.

These drafts are intentionally thin. Every new module's
docstring starts with `PROTOTYPE`. Claude should treat them as
proposals in code, not as shipped product. Wizard does not
teach the new verbs (Hole F).

### Prototype roadmap (executed below this heading)

1. Schema: `boxes.shell_level`, `boxes.difficulty`; tables
   `loot`, `unlock_state`; additive ALTER for old on-disk DBs.
2. `milestones.py` — record user/root shell, inject a short
   Linux privesc deck, timeline event. `box-status rooted`
   also records a root milestone if none exists.
3. Coach: if `shell_level` is set, prefer `privesc`/`post`
   over earlier phases (do not hide leftover enum — it stays
   in `also_worth_trying`).
4. `unlocks.py` — two generic cards (after user shell, after
   root). Offer / take / decline. No box-specific techniques.
5. `loot.py` — add/list; timeline `event_type='loot'`.
6. Difficulty on `create_box` + optional wizard prompt
   (Enter skips) + a quiet note on `trinity next` for Hard.
7. `report/render.py` — registry keyed by mode;
   `gather_report_data` grows a `loot` field; both existing
   templates render it lightly.
8. CLI power-user verbs: `shell`, `unlock`, `loot`.
9. Unit tests per piece. Re-run the full suite. Update the
   count here and in DESIGN.md.

### What Claude should review in the prototype (once coded)

- Is `trinity shell` the right verb, or should milestone live
  only inside `box-status` / a wizard Confirm (Hole F)?
- Does preferring privesc after a user shell fight
  INSTRUCTOR_MODE.md's "earlier phases always win"? Cursor
  thinks the phase rule is wrong *after an explicit foothold
  milestone* — that is the whole point of 1.6.
- Loot vs 1.10: delete the professional loot section?
- Unlock copy: generic enough, or still too lecture-y?
- New verbs vs Hole F: accept as power-user, or fold into
  existing commands (`box-status`, `hint`, notes)?
- Additive migration for `boxes.shell_level` / `difficulty`
  on a pre-`3439bac` on-disk DB.

---

## Cursor prototype log — undesigned core (after `3439bac`)

Alexander: rough-draft these so Claude can fix/merge later.
Do not treat this block as "the pass is shipped."

Suite after this pass: **198 passed** in 37.83s. Uncommitted on
top of `3439bac`. Not pushed. Every new module is marked
`PROTOTYPE` in its docstring.

### 1. Milestone / name the win + privesc deck — DRAFTED

- `src/trinity/milestones.py` — `record_shell(conn, box_id, "user"|"root")`.
  Asks, never infers (Claude §2 / 1.6).
- `boxes.shell_level` column + `set_shell_level`. Additive ALTER
  on old on-disk DBs (`_BOXES_ADDITIVE_COLUMNS`).
- User shell injects four Linux privesc suggestions (`id`,
  `sudo -l`, SUID find, `cat /etc/crontab`) — commands that
  already have ELI5 seeds. linpeas omitted on purpose.
- Root shell also marks the box rooted.
- Will not demote root → user.
- `trinity shell --box --as user|root` (power-user; wizard does
  not teach it).
- `box-status rooted` sets `shell_level=root` if it was NULL so
  unlock cards can appear without the new verb.
- Coach (`get_recommendation`): if `shell_level` is set, promote
  `privesc`/`post` ahead of leftover enum. Leftover stays in
  `also_worth_trying`. **This fights INSTRUCTOR_MODE.md's raw
  "earlier phases always win" on purpose.** Claude: keep or revert.

### 2. Curiosity unlocks — DRAFTED

- `src/trinity/unlocks.py` + `unlock_state` table.
- Two generic cards (`after_user_shell`, `after_root`). No box
  names, no techniques, no Methods Index shapes (1.9).
- `trinity unlock --box` takes the next card; `--decline` skips.
  Declining is the intended habit. Cards do not auto-print.
- `next` / `shell` / `box-status rooted` mention the verb in dim
  text only ("optional, skip by default").
- Claude: rewrite copy; decide if a one-line offer on `next` is
  already too much lecture.

### 3. Loot tracker — DRAFTED

- `src/trinity/loot.py` + `loot` table.
- Kinds: credential / hash / token / flag / other.
- `trinity loot add|list --box` (fail-closed on missing box).
- Timeline `event_type='loot'`.
- `gather_report_data` now carries `loot`.
- Educational: light "## What you pocketed".
- Professional: "## Recovered Evidence" table. **1.10 tension —
  Claude should keep, shrink, or delete that section.**

### 4. Difficulty-aware guidance — DRAFTED

- `boxes.difficulty` (easy/medium/hard/NULL) + `set_difficulty`.
- `create_box(..., difficulty=)`.
- Wizard asks once; default `skip`. Invalid/skip → NULL.
- `trinity next` prints one dim line only when difficulty is
  `hard`. Easy stays silent on purpose.

### 5. Report renderer seam — DRAFTED

- `src/trinity/report/render.py` — `RENDERERS` dict +
  `render_report(data, mode)`.
- CLI `report` no longer hard-imports the two generators.
- Not a plugin package system. Just the seam the backlog asked
  for before a third format exists.

### Tests added

- `test/unit/test_milestones.py`
- `test/unit/test_unlocks.py`
- `test/unit/test_loot.py`
- `test/unit/test_cli_prototypes.py`
- extras in `test_coach.py` (privesc promotion),
  `test_boxes_timeline.py` (difficulty),
  `test_db_migration.py` (boxes columns + new tables)

### Files touched this prototype pass

New: `src/trinity/milestones.py`, `src/trinity/unlocks.py`,
`src/trinity/loot.py`, `src/trinity/report/render.py`,
the four test files above.

Modified: `src/trinity/db.py`, `src/trinity/boxes.py`,
`src/trinity/coach.py`, `src/trinity/wizard.py`,
`src/trinity/cli/main.py`, `src/trinity/report/data.py`,
`src/trinity/report/educational.py`,
`src/trinity/report/professional.py`, `DESIGN.md`,
this handoff, `test/unit/test_coach.py`,
`test/unit/test_boxes_timeline.py`,
`test/unit/test_db_migration.py`.

### Still not done (intentionally)

Live TUI `d`/`s`/`h`, full interactive wizard, share-export
IP hygiene, thickening suggestion/error seeds, GTFOBins,
Methods Index, rabbit-hole, stats, `trinity lab`, suggestion
contracts, platform API, PyPI, achievements, AutoRecon
teach/parse.

Docs still stale (DESIGN "what's built" / roadmap order,
INSTRUCTOR_MODE catch-up, FEATURES_BACKLOG parking lot,
CONTRIBUTING surfaces, Trinity_suggestions A–F banner).
Cursor did not rewrite those in this pass — the review
notes above are the punch list for a docs session.

### Claude review checklist (prototypes)

1. `trinity shell` as a third-ish verb vs folding into
   `box-status` (Hole F).
2. Privesc-promotion vs INSTRUCTOR_MODE.md phase rule.
3. Professional loot section vs 1.10 freeze.
4. Unlock copy + the dim `trinity unlock` hint on `next`.
5. Wizard gaining a fourth question (difficulty) vs
   "as few questions as honestly possible."
6. Additive `boxes.shell_level` / `difficulty` migration on
   a pre-prototype `~/.trinity/trinity.db`.
7. Whether any of this should be reverted before merge and
   rebuilt from a real design doc instead.

---

## Remaining prototype queue (2026-09-06 night)

Alexander: keep drafting new features from the design docs while
Claude tokens reset. Full inventory below. **Do not** touch the
DO NOT list. Everything here is still a `PROTOTYPE` for Claude
to fix/merge.

### Already drafted last pass (do not redo)

Milestone/shell + privesc deck, curiosity unlocks, loot, difficulty,
report renderer seam.

### Will prototype this stretch (from design docs / backlog / suggestions)

| # | Item | Source | Notes |
|---|---|---|---|
| 1 | Methods Index read-side | METHODS_INDEX.md steps 1–2 | Hand-authored YAML + `trinity methods`. **No** `methods-fetch` scraper. |
| 2 | Rabbit-hole detection | RABBIT_HOLE_DETECTION.md | Read-only signals + `next` nudge + timeline `nudge`. |
| 3 | Frustration checkpoints | FEATURES_BACKLOG | Presentation layer on #2. |
| 4 | `trinity stats` | DESIGN.md roadmap | Hide the celebration until ≥1 rooted box (5.9). |
| 5 | GTFOBins local (tiny) | DESIGN + suggestions 4.1 | Hand-authored subset, not a scrape. |
| 6 | Hash classifier | suggestions 2.5 | Local regex/shape, canned next step. |
| 7 | `trinity read` | suggestions 2.12 | One-shot `process_scan_file` + TA lines. |
| 8 | Notebook tear-out | suggestions 2.7 + report seam | Third renderer + share-export sidecar. |
| 9 | Share-export IP scrub | debate 2.13 leftover | Regex `$TARGET` / strip IPv4 in exported command strings. |
| 10 | Phrasebook + dead-end language | 1.8 / 2.8 / 2.9 | Grow the 4-line book; skip copy that gives permission to park. |
| 11 | AutoRecon *teach* + graduation nudge | FEATURES_BACKLOG | ELI5 + optional mention after N manual gobusters. **Never launch.** |
| 12 | Achievements / technique journal | FEATURES_BACKLOG | Local, no leaderboard. Thin taxonomy. |
| 13 | Beginner-track data | suggestions 2.6 | Optional field on `platforms.yaml`. |
| 14 | Watch 15-min silence | suggestions 2.4 | Advisory feed line, no auto-run. |
| 15 | `notify-send` on critical | suggestions 2.11 | Best-effort, missing binary is fine. |
| 16 | Watch clipboard copy | suggestions 4.4 | `c` copies the current rec. |
| 17 | rustscan text parser | suggestions 4.2 | `Open host:port` lines. |
| 18 | More error-pattern seeds | suggestions 3.2 | ~10 common beginner failures. |
| 19 | linpeas as *optional* post-shell suggest | suggestions 4.1 | Command only, never run. |

### Parked (valid, still uncoded)

Local NVD/CVSS feed, netexec/ldap parsers, PyPI packaging polish,
full suggestion-contracts framework, live report pane in the TUI,
platform metadata HTTP pull, CTFd API, `tools.yaml` migration,
using `beginner_track` to actually cap the coach.

### Hard no (unchanged)

LLM/chat, auto-install, auto-run scans/exploits, Nuclei/AutoRecon
*launchers*, Metasploit RPC, scrape writeups, `methods-fetch`
live pipeline, `trinity lab` / hyprctl, `trinity stuck`, strip
professional mode, shell-history sensors, social/leaderboards.

### Progress log for this stretch

Suite: **224 passed** in 42.28s. Uncommitted on top of `3439bac`.
Every new module is `PROTOTYPE`. No `methods-fetch`. No launchers.
The write that got stuck was this log; the code and tests were
already on disk.

1. **Methods Index read-side — DRAFTED.**
   `methods_index/lame.yaml` (3 foothold shapes, author `"0xdf"`
   quoted so YAML does not hex-parse it), `methods.py` rejects
   missing citations / long summaries, `trinity methods --name Lame`
   / `--box`. Wizard does not mention it. No fetch pipeline.

2. **Rabbit-hole detection — DRAFTED.**
   `rabbit_hole.py`: stalled progress, maxed hint ladder, phase
   dominance. Thresholds are arguments (open design question).
   Wired into `trinity next`. Timeline `event_type='nudge'`.

3. **Frustration checkpoint — DRAFTED.**
   `frustration.py` swaps in the community-research encouragement
   the second time a nudge fires on the same box.

4. **`trinity stats` — DRAFTED.**
   Hidden until ≥1 rooted box (5.9). Streak + technique list.

5. **GTFOBins subset — DRAFTED.**
   8 binaries, summaries + official URLs. `trinity gtfobins [bin]`.

6. **Hash classifier — DRAFTED.**
   `trinity hash <value>`: md5/sha1/sha256/bcrypt/md5crypt/
   sha512crypt/JWT/unknown. No network.

7. **`trinity read` — DRAFTED.**
   One-shot `process_scan_file` + TA lines.

8. **Notebook tear-out — DRAFTED.**
   `report/notebook.py` registered as mode `notebook`.
   `share-export` also writes a sibling `.md`.

9. **Share-export IP scrub — DRAFTED.**
   `scrub_identifying()` replaces IPv4 with `$TARGET` in exported
   explanation command/text.

10. **Phrasebook + dead-end language — DRAFTED.**
    Phrasebook grown (privesc/curl/smbclient). `deadends.py` used
    by `trinity skip`.

11. **AutoRecon teach + graduation — DRAFTED.**
    ELI5 seed `autorecon <target>`. After 3 accepted gobuster
    suggestions, `next` mentions AutoRecon as an option.
    **Never launched.**

12. **Achievements / journal — DRAFTED.**
    `trinity journal`. Local taxonomy v1. No leaderboard.

13. **Beginner-track data — DRAFTED.**
    Optional `beginner_track` on HTB in `platforms.yaml`.
    Loaded, not yet used to cap the coach (spoiler-risk).

14. **Watch 15-min silence — DRAFTED.**
    Dashboard interval; one reminder, no auto-run.

15. **`notify-send` on critical — DRAFTED.**
    Best-effort from `process.py` after a critical match.

16. **Watch clipboard — DRAFTED.**
    `c` copies the current recommendation.

17. **rustscan parser — DRAFTED.**
    `Open host:port` lines; `detect_and_parse` picks it up.

18. **Error-pattern seeds — DRAFTED.**
    +10 common beginner failures in `errors_seed.py`.

19. **linpeas optional post-shell — DRAFTED.**
    Added to the user-shell privesc deck as a named command
    Trinity will not fetch or run.

20. **PayloadsAllTheThings topic index — DRAFTED**
    (was parked; steam remained). Titles + URLs only.
    `trinity payloads [topic]`.

### Claude review extras from this stretch

- YAML `author: 0xdf` must stay quoted (hex parse).
- Rabbit-hole on every `next` may be noisy — thresholds are guesses.
- `trinity read` still `get_or_create_box` (one-shot parse creates).
- `notify-send` from `process_scan_file` also fires if the binary
  exists (captured, should not fail tests).
- New verbs vs Hole F: methods/stats/hash/gtfobins/read/journal/
  payloads are all power-user.
- linpeas in the privesc deck is a name only, not a launcher.

---

## Professional-mode prototype + DO NOT review (Alexander override)

1.10 froze professional *growth*, not the mode itself. Alexander
explicitly authorized professional-mode prototyping.

**Drafted:** document control (classification / version /
distribution), written exec summary, scope/limitations/assumptions,
finding IDs, draft ATT&CK tags (`report/attack.py`), draft
remediation (`report/remediation.py`), evidence section, tools
observed, `engagement-set` extra fields + `engagement-show`.
Educational template deliberately did **not** get ATT&CK or
document control (mode is a lens; those are presentation).

**Still will not prototype from the DO NOT list:**

| Item | Why still no |
|---|---|
| LLM / chat pane | Kills the local-cache economy. DESIGN.md soul. |
| Auto-install | System mutation. Different trust class than a scan. |
| Auto-run scans / exploits / Nuclei / AutoRecon launchers | Breaks I do / we do. Parse-only is fine (already drafted for rustscan / AutoRecon *teach*). |
| Metasploit RPC | Session ownership. Teach searchsploit; they run msf. |
| Scrape writeups / live `methods-fetch` | Copyright + spoiler. Read-side index is the allowed shape. |
| `trinity lab` / hyprctl | Orchestrates the WM. Claude and Cursor both vetoed. |
| Shell-history sensors | Surveillance-shaped. File watch only. |
| Re-rank `next` around missing tools | Trains "work around a missing kit." |
| Hint L1/L2 install leak | Same as leaking the answer. |
| `trinity stuck` | Alias for `hint`. Hole F. |
| Social / leaderboards | Accounts/network. Explicitly declined. |

Those are not "frozen until later." They are the product's rails.
The long-form understanding of each item, the adjacent cousins,
and blank **Decision** / **Alexander's notes** fields are in
`docs/OPEN_DECISIONS.md` — use that file to record what to
implement. Do not treat the table above as the last word.

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

Test baseline right now: **175 passed** (`uv run pytest test/unit -q`
from repo root). Updated 2026-09-06 evening by Cursor after the curl
URL fix + CliRunner/story/migration tests. Keep this number honest;
if it drops, something regressed.

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

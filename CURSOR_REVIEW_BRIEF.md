# CURSOR_REVIEW_BRIEF.md — AI-readable only. Not user-facing docs.

Purpose: this is a FOLLOW-UP review. Your previous pass
(`~/Downloads/trinity_cursor_review.md`, now deleted after being acted
on) found 8 real bugs plus several doc/design contradictions. Claude
fixed all of them. This brief tells you exactly what changed and asks
you to verify each fix actually holds, plus do a fresh general pass in
case anything new broke. Do not re-read your old report — it's gone;
everything you need to verify is described below.

## Your task

1. Read this brief fully.
2. Re-read `DESIGN.md`, `docs/INSTRUCTOR_MODE.md` in the repo root/docs
   (both were updated).
3. For each of the 8 previously-fixed bugs below, verify the fix
   actually holds against the CURRENT code — cite file:line, same
   rigor as last time. Don't take Claude's word for it.
4. Run the test suite (`uv run pytest test/unit -q` from repo root)
   and report the real pass/fail count.
5. Do a fresh look for anything NEW broken by these fixes (regressions
   introduced while fixing the original 8), plus a general sanity pass
   on the touched files.
6. Write your report to `~/Downloads/trinity_cursor_review_2.md`
   (note the `_2` — keep it separate in case there's a round 3).
7. Do NOT edit any repository file. Do NOT commit or push. Read-only
   review, same as last time.

## What Trinity is (unchanged since your last pass)

Free, open-source, local-first recon copilot for CTF/HTB/TryHackMe-
style practice. Parses recon tool output, matches against a local KB +
live offline searchsploit, suggests/ranks next commands, explains
commands/errors from a local cache (AI escalation only on genuine
cache miss, always as a copy-paste prompt), generates educational or
professional reports off one shared timeline. Philosophy: "drive the
car before you build the car" — let a beginner crack their first box
before requiring deep understanding; Trinity narrates, the operator
always runs the actual tools themselves ("I do / we do").

## The 8 bugs from your last pass — what changed for each

### BUG-1 (high, principle violation): hint level 2 leaked the tool/answer

Root cause you found: `hints.py`'s level 2 rendered
`rationale.split('.')[0]`, and every suggestion rule's `rationale` is
one sentence that names the tool (SMB) or the literal answer (FTP).

Fix: `suggest/engine.py`'s `Suggestion` model now has a second field,
`nudge` — written per rule, deliberately vague, never names the tool
or gives the answer away. `hints.py`'s `build_hint()` now takes both
`nudge` and `rationale` as separate parameters; level 2 renders
`nudge`, level 3 still renders the full `rationale` + command. The
`suggestions` table gained a `nudge` column (db.py); every INSERT site
(`process.py`, `cli/main.py`'s `suggest_cmd`) now writes it;
`coach.py`'s row reconstruction reads it back.

New test: `test/unit/test_hints.py::test_no_real_suggestion_rule_leaks_its_command_at_hint_level_2`
— iterates every real suggestion rule (http/smb/ftp/ssh) via a real
`findings` row round-trip, asserts the resulting `nudge` never
contains the command's own tool name (case-insensitive first-token
check). Also: `test_level_2_uses_nudge_not_rationale`.

Please verify: read every rule in `suggest/engine.py` yourself and
confirm each `nudge` string genuinely doesn't name the tool, don't just
trust that the test passes (a test can be wrong).

### BUG-2 (high): whatweb.json undetectable

Root cause: `process.py`'s `detect_and_parse` handled `.json` first
(ffuf/nikto/enum4linux-ng), returning `None` on no match, so the
whatweb branch (gated behind `.jsonl` or `"whatweb" in name`) was
unreachable for whatweb's own documented `--log-json=out.json`
invocation (a `.json`-suffixed file that's actually JSON Lines).

Fix: for any `.json`/`.jsonl` file, `detect_and_parse` now first tries
parsing just the FIRST LINE as JSON and checks for a `"plugins"` key
(whatweb's shape) before falling through to whole-document JSON
parsing for ffuf/nikto/enum4linux-ng. Filename-based whatweb detection
kept as a fallback for non-JSON-suffixed files.

New tests: `test/unit/test_process.py::test_detect_and_parse_recognizes_whatweb_json_extension`
(a file literally named `whatweb.json`), plus
`test_detect_and_parse_still_recognizes_ffuf_json_after_whatweb_fix`
(guards against the fix swallowing genuine ffuf/nikto/enum4linux-ng
`.json` files) and `test_detect_and_parse_recognizes_unrecognized_dot_json_as_none`.

Please verify: confirm the JSONL-first-line check can't false-positive
match a genuine ffuf/nikto/enum4linux-ng document that happens to have
a `"plugins"` key somewhere unexpected, and confirm malformed/truncated
`.json` files still degrade to `None` rather than raising.

### BUG-3 (medium-high, security): searchsploit argv injection

Root cause: `kb/searchsploit.py`'s `search()` passed `*terms` (which
ultimately come from nmap XML `product`/`version` fields) directly
into `subprocess.run(["searchsploit", "-j", *terms])`. A crafted/
malformed scan producing a term like `-u` would trigger a full
ExploitDB mirror update instead of being treated as a search string.

Fix: new `_sanitize_terms()` drops any term starting with `-` before
it reaches subprocess. IMPORTANT: the first fix attempt tried adding a
`--` GNU end-of-options separator, but `searchsploit`'s own CLI parser
does NOT understand `--` (errors with "illegal option") — verified
against the actual installed binary. The final fix just drops
dangerous terms outright, no `--` separator.

New test file `test/unit/test_searchsploit.py`: sanitizer unit tests,
plus a mocked-subprocess test confirming `-u` never reaches the actual
`subprocess.run` call, plus confirmation that legitimate multi-word
terms (`vsftpd`, `2.3.4`) still work.

Please verify: run `searchsploit -j vsftpd 2.3.4` yourself on this
machine (real binary, not mocked) via
`uv run python3 -c "from trinity.kb.searchsploit import search; print(search('vsftpd','2.3.4'))"`
and confirm real results still come back (i.e. the fix didn't break
legitimate lookups) AND that
`search('-u', '--help')` returns `[]` without ever calling subprocess.

### BUG-4 (medium): error-cache false positives on long generic words

Root cause: `errors.py`'s `_is_meaningful_overlap` treated ANY single
overlapping token >= 8 characters as distinctive enough for a match —
but "connection" (10 chars), "forbidden" (9), "unexpected" (10) are
common English words, not actually distinctive, and were causing
confident-looking wrong diagnoses (e.g. "connection error" matching
the seeded "Connection timed out" pattern).

Fix: added `_GENERIC_STOPWORDS` (connection, forbidden, unexpected,
permission, timeout, refused, denied, etc.) and `_is_distinctive_token()`
— a token now needs to be BOTH >= 8 chars AND not in the stopword list
to count alone; 2+ overlapping tokens of any length still counts
regardless of the stopword list.

New tests: `test_long_generic_words_do_not_cause_false_positive_matches`
(the exact 4 false-positive queries from your last report, now
asserted `None`), `test_distinctive_single_token_still_matches`
(confirms the fix didn't overcorrect — a genuinely distinctive single
token like "publickey" still matches alone).

Please verify: think of 2-3 more long-but-generic English words
plausible in error text (not already in `_GENERIC_STOPWORDS`) and
manually check whether they'd still cause a false positive — the
stopword list is inherently incomplete, and I want your judgment on
whether the approach (stopword list) vs. an alternative (e.g. requiring
2+ tokens always, dropping the single-distinctive-token exception
entirely) is the better tradeoff.

### BUG-5 (medium, design vs impl): coach ranking didn't match its own spec

Root cause: `docs/INSTRUCTOR_MODE.md` specified phase → per-suggestion
severity → recency. The code read ONE box-level severity (latest
match on the whole box) and applied it identically to every
suggestion, making it unable to rank two suggestions against each
other by severity at all; and `ORDER BY id` + stable sort put OLDEST
first within a phase, the opposite of "recency."

Fix: `coach.py` now has `_port_from_rationale()` (regex-extracts the
port number every current rationale mentions, since they all start
"Port N is...") and `_severity_for_port()` (looks up the specific
finding tied to that port, via a `timeline JOIN findings` query on
`f.port`). Ranking key is now
`(phase_rank, severity_rank, -suggestion_id)` — negative suggestion id
so higher (more recent) ids sort first as the tiebreaker.

New tests: `test_severity_ranks_suggestions_against_each_other_not_box_wide`
(two suggestions on different-severity findings in the same phase;
asserts the critical one wins even though inserted second) and
`test_recency_breaks_ties_within_same_phase_and_severity`.

Please verify: the port-extraction approach (`_port_from_rationale`)
is a regex over rationale TEXT, which is fragile if a rationale is ever
rewritten to not start with "Port N is..." — check whether this is an
acceptable coupling or whether the severity lookup should instead be
threaded through more directly (e.g. storing a `finding_id` on the
`suggestions` table itself, which the current schema does NOT do).
This might be worth flagging as a "works but fragile" finding rather
than a clean pass.

### BUG-6 (medium): watch-mode duplicate persistence

Root cause: `tui/dashboard.py`'s `_handle_file` called
`process_scan_file` (which always INSERTs) on every qualifying
filesystem event with no dedup, so a paired added+modified event pair
(or any duplicate fire) for the same save would double-insert
findings/timeline events.

Fix: added `self._last_processed_hash: dict[str, str]` (path ->
sha256 of last-processed content). `_handle_file` now hashes the
file's current bytes, skips processing entirely if the hash matches
what was last processed for that path, and only updates the stored
hash after a successful (non-exception) `process_scan_file` call.

New test file `test/unit/test_dashboard.py` (there were ZERO dashboard
tests before): constructs a `TrinityDashboard` via `__new__` (bypassing
Textual's `App.__init__`/mount, since this is testing pure logic, not
UI) and confirms (a) calling `_handle_file` twice on identical content
only persists once, (b) calling it again after the file's content
genuinely changes DOES reprocess.

Please verify: the `TrinityDashboard.__new__` bypass technique used in
the test is a bit unusual (skips Textual's own init) — confirm it's
actually exercising the real `_handle_file` logic and not
accidentally testing a mock/stub. Also check whether hashing the whole
file on every event is a real performance concern for very large scan
files (probably not for typical recon output, but worth a sanity
check).

### BUG-7 (low-medium, UX): VPN "connected but operator says no" copy was false

Root cause: `wizard.py`'s `run_vpn_check` printed "No active VPN
connection detected" even when an interface WAS detected but the
operator answered "no" to "are you already connected" (e.g. a
different VPN happens to be up).

Fix: the messaging now branches — if an interface was detected but the
operator says no, it says "a VPN-looking interface is up, but let's
make sure it's actually connected to your lab" instead of falsely
claiming nothing was detected.

No new automated test added for this (it's UI copy, not logic) —
please manually trace through `wizard.py:run_vpn_check` and confirm
the message shown in that specific branch is accurate.

### BUG-8 (low): parse-nmap's wrong error message on unrecognized files

Root cause: `cli/main.py`'s `parse_nmap_cmd` treated `process_scan_file`
returning `None` (file not recognized as any known format) the same
as it returning an empty findings list, printing the misleading
"No open ports found in that scan" for a file that wasn't even parsed.

Fix: split into two branches — `None` now prints "wasn't recognized as
nmap XML output (or any other known scan format)"; empty findings
still prints the original "no open ports" message.

Please verify: `cli/main.py`'s `parse_nmap_cmd` around where it calls
`process_scan_file` — confirm the two branches are distinct and the
messages match reality.

## Additional fixes beyond the original 8 (found while fixing the above, or flagged in your report's "New bugs"/"Design docs vs implementation" sections)

- **sharing.py box-scoping leak**: `build_share_bundle` previously
  pulled ALL `ai_escalation` explanations globally (the table isn't
  box-scoped), so exporting "box A's bundle" leaked every cached
  explanation on the machine, including from unrelated boxes. Fixed:
  now cross-references the box's own `timeline` for `explanation`
  events to scope the export to only what was actually encountered
  working THIS box. Also removed the `detail` field from exported
  findings (could carry hostnames/banners/usernames). Also added
  `error_candidates` to the export (previously `error_patterns` fed
  nothing into sharing, despite `INSTRUCTOR_MODE.md` saying it should).
  New tests in `test/unit/test_box_status_and_sharing.py`:
  `test_build_share_bundle_is_scoped_to_this_box_only`,
  `test_build_share_bundle_excludes_finding_detail`.

- **Professional-mode instructor commands weren't actually quieter**:
  `INSTRUCTOR_MODE.md` specified professional mode should skip the WHY
  narration and hint ladder; the code never checked `box.mode` at all.
  Fixed: `cli/main.py`'s `next_cmd` and `hint_cmd` now branch on
  `box.mode == "professional"` — skip the WHY paragraph in `next`,
  skip the Socratic ladder entirely in `hint` (goes straight to the
  full answer, since a pentest deliverable has no use for being coy).
  No dedicated automated test added for this branch yet — please check
  whether one should exist and flag if its absence is a real gap.

- **Doc staleness**: `DESIGN.md`'s test count (was hardcoded "99",
  actual current count is 138) and `docs/INSTRUCTOR_MODE.md`'s status
  header (was "DESIGN ONLY", corrected to "BUILT" since coach/hints/
  errors are all implemented and tested) were both corrected. Also
  corrected the ranking description in `INSTRUCTOR_MODE.md` to match
  what BUG-5's fix actually implemented (per-suggestion severity +
  real recency, not one box-wide value).

- **A bug Claude introduced while fixing BUG-1, then caught itself
  during live testing** (not in your original report, disclosed for
  transparency): the first attempt at splitting `next_cmd`'s
  professional/educational branches had a quadruple-escaped f-string
  (`\\\\\\\"`) that rendered literal backslash-quote characters in the
  terminal instead of actual quote marks. Caught by re-running the CLI
  command live (not just trusting the test suite, which didn't cover
  this exact rendering path) and fixed by building the quoted strings
  as separate variables instead of escaping inline. Please specifically
  check `cli/main.py`'s `next_cmd` for any other escaping issues in the
  professional/educational branch strings — this class of bug is worth
  a careful look since it already slipped through once.

## Test suite

Was 99 passing at your last review. Currently 138 passing (`uv run
pytest test/unit -q`). New test files since your last pass:
`test_searchsploit.py`, `test_dashboard.py`. Substantially extended:
`test_hints.py`, `test_coach.py`, `test_errors.py`, `test_process.py`,
`test_box_status_and_sharing.py`.

## Files most relevant to re-review (changed since your last pass)

```
DESIGN.md
docs/INSTRUCTOR_MODE.md
src/trinity/db.py                          (suggestions.nudge column, schema)
src/trinity/suggest/engine.py              (Suggestion.nudge field, per-rule nudge text)
src/trinity/coach.py                       (per-suggestion severity, recency ranking)
src/trinity/hints.py                       (nudge param, build_hint signature change)
src/trinity/errors.py                      (stopword list, _is_distinctive_token)
src/trinity/kb/searchsploit.py             (_sanitize_terms)
src/trinity/process.py                     (whatweb JSONL-first detection)
src/trinity/tui/dashboard.py               (content-hash dedup)
src/trinity/wizard.py                      (VPN copy fix)
src/trinity/sharing.py                     (box-scoping, error_candidates, detail removal)
src/trinity/cli/main.py                    (parse-nmap error message, professional-mode next/hint, escaping fix)
test/unit/test_hints.py                    (new leak-regression test)
test/unit/test_coach.py                    (new severity/recency tests)
test/unit/test_errors.py                   (new stopword regression tests)
test/unit/test_process.py                  (new whatweb.json tests)
test/unit/test_searchsploit.py             (new file)
test/unit/test_dashboard.py                (new file)
test/unit/test_box_status_and_sharing.py   (new scoping tests)
test/unit/test_suggest_engine.py           (nudge presence test)
```

## Environment notes

- Repo root: `~/Work/trinity`
- Run tests: `uv run pytest test/unit -q` (from repo root; `uv` may
  not be on PATH in a non-interactive shell — use the same workaround
  you used last time, e.g. `.venv/bin/pytest`, if needed)
- Nothing has been committed yet — full delta is visible in `git diff`/
  `git status` against HEAD
- Do not run `git commit`, `git push`, or modify ANY file. Write your
  findings ONLY to `~/Downloads/trinity_cursor_review_2.md`.

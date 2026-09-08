# Show Me Mode — QUARANTINED (2026-09-07)

Status: **DISABLED at both entry points** (`trinity show-me` CLI
command, and the TUI Tools menu's "Assimilate Attack Vector" item).
Code is intact under `src/trinity/show_me.py`, `src/trinity/tui/
show_me_screens.py`, and the `assimilator_runs`/`show_me_runs`/
`show_me_attestation` tables — nothing deleted, nothing reverted.
Quarantine is enforced with a hard `raise click.ClickException(...)`
at the top of `show_me_cmd` and a `notify()`-only stub in the TUI menu
handler. Re-enable only after the fix plan below (or a superseding
design) ships and is itself reviewed.

## Why

Two independent full-program code reviews (Cursor and Claude Code
CLI, dispatched in parallel worktrees, read-only, both reproduced
findings against a real running Trinity install rather than
theorizing) converged on the same conclusion without coordinating:
**do not enable Show Me Mode for a live user test.** Full reports:
`findings/full_review_cursor.md` and `findings/full_review_claude.md`
(worktree branches `full-review-cursor` / `full-review-claude`, not
merged to main — the findings are consolidated here instead).

## The core architectural problem (not just bugs)

`show_me.py`'s execution loop runs every agent-proposed command as a
**local subprocess on the OPERATOR's own machine** — there is no SSH
session, no persistent connection, no remote shell to the target at
all. `subprocess.run(shlex.split(command))` just runs the literal
command locally. This means:

- Commands that legitimately reach the network (`nmap $target`, `curl
  http://$target/`) do test the real target and work as designed.
- But **"get a foothold shell" is architecturally unreachable by this
  loop.** A one-shot local subprocess call cannot establish or
  maintain an interactive remote session. There is no mechanism to
  catch a reverse shell or carry state between turns.
- The milestone detector (`_detect_shell_evidence`) is therefore
  pattern-matching LOCAL command output for signs of a REMOTE shell
  that structurally cannot exist in this design — which is exactly
  why it false-positives on things like running `id` locally (both
  reviews reproduced this) or any output line ending in `$`.
- `test_show_me.py`'s success-path test mocks `subprocess.run` to
  return `uid=33(www-data)...` as if that's what running `id` LOCALLY
  would produce for a remote foothold — the test papers over a
  scenario that cannot occur against the real loop.

This needs an explicit decision before rebuild, not just bug fixes:
either (a) rescope Show Me Mode to network-reaching recon/verification
only, with clear language that it does not attempt to grant or claim a
remote shell, or (b) build the real thing — a persistent connection
object (SSH session, netcat listener) that the agent's proposed
commands actually execute through. Both reviews reproduced the same
underlying symptom independently; this doc records it once so it
isn't rediscovered as a "surprise" bug during the rebuild.

## Full findings inventory (converged from both reviews)

### Blocking (must fix before any re-enable)

1. **`record_shell()` mutates student state on every Show Me
   invocation, including FAILED runs.** Sets `boxes.shell_level`,
   writes a timeline row falsely claiming "operator declared... Trinity
   did not inspect any shell history," injects 5 privesc suggestions,
   and can set `status='rooted'`. Violates the explicit rail written
   into `docs/OPEN_DECISIONS.md` and `docs/SHOW_ME_MODE.md` this same
   session: "nothing counts until the student runs it themselves."
   Both reviews reproduced this end-to-end against a real DB.
   (`show_me.py`'s call into `milestones.record_shell`.)

2. **TUI crashes 100% of the time via SQLite cross-thread usage.**
   `ShowMeRunningScreen`'s `@work(thread=True)` worker reuses the
   dashboard's connection, created on the main thread.
   `sqlite3.ProgrammingError` on the first query. No `try/except`
   around the worker body, so the modal hangs forever on "running..."
   with zero error feedback — reproduced by both reviews.

3. **Report-integrity gap: failed runs get zero AI disclosure while
   still mutating state (per #1).** `report/data.py`'s
   `ai_assisted_steps` query filters to `outcome IN ('succeeded',
   'already_known')` — so the (likely more common) failure case
   produces a report showing a false "declared shell" with no
   disclosure anywhere. `notebook.py` (the third report renderer) has
   no AI-disclosure block at all, in either outcome case.

4. **The architectural gap above** — milestone detection cannot be
   trusted while the loop has no real remote session.

### High-priority (fix before broad use, not necessarily before a
narrowly-scoped internal re-test)

5. **Denylist/target-pin bypassable by any interpreter** (`bash -c`,
   `python3 -c`, `find -delete`, `systemctl` with flags between verb
   and command, hostname targets inverting the IPv4-only pin, decimal/
   hex-encoded IPs). Both reviews enumerated concrete working bypass
   strings. Claude's reframing matters: since commands run locally
   (see above), the denylist is defending the wrong host — it reads
   like "don't break the target" but the operator's own machine is
   what's actually exposed.

6. **`check_already_known()` is called with `service=None,
   product=None, version=None`, plus the full raw transcript as
   `detail`.** Confirmed live: this does NOT make it too narrow (my
   original assumption) — it FTS-matches the entire transcript and
   returns real, wrong hits (a generic "run gobuster after finding a
   webserver" KB entry matched against an unrelated foothold
   transcript). Corrupts the `already_known_hit` leverage metric.
   Fix: call it BEFORE the agent session, against the box's real
   structured `findings` rows, with confidence restricted to
   `confirmed` only.

7. **No wall-clock cap, no abort path.** Design doc lists both as hard
   stops (`docs/SHOW_ME_MODE.md` §6); neither exists. Worst case ~24
   minutes of silent execution (12 turns x up to 120s each).

8. **Consent gates bypassable via piped stdin.** `echo y | trinity
   show-me ...` clears both the attestation and per-invocation
   disclosure — the design doc explicitly promised "no `--yes` flag,
   no env-var bypass." Missing `sys.stdin.isatty()` guard.

9. **No progress narration despite the disclosure text promising it.**
   `ShowMeRunningScreen`'s docstring claims "live status updates as
   commands execute, not a silent spinner" — there are zero updates;
   `run_show_me()` takes no progress callback at all.

### Medium priority (real, but not blocking)

10. `assimilator_runs` schema missing 6 fields from
    `docs/ASSIMILATOR_PROJECT.md` §7 (`fixture_sha`,
    `precision_check_passed`, `reviewer`, `reviewed_at`, `fix_commit`,
    `agent_calls`, `wall_clock_seconds`); 4 existing columns
    (`secondary_causes`, `fix_shape`, `boxes_regressed`,
    `new_false_positives`) have no write API. No
    `_ensure_additive_columns` entry for either new table — the first
    schema change will silently no-op on existing installs (the exact
    trap `db.py` documents and guards against for every other table).
11. `primary_cause` is hardcoded to `"capability_gap"` at open and
    never refined — every live run, including trivial ones, lands in
    the most alarming taxonomy bucket.
12. Failure-to-bucket mapping is wrong: any stop reason (including
    "agent call timed out") becomes `escalated_capability_gap`,
    inflating the CEO-facing headline metric with unrelated failures.
13. `outcome='aborted'` is defined in the schema/model but never
    produced by any code path.
14. `leverage_summary()` has no CLI/TUI surface — the "headline
    metric" from the design doc is currently only called by a test.

### Also found in the whole-program pass (unrelated to Show Me, real regressions)

15. **`sharing.py` regression from the intake provenance fix.** Fixing
    `approve_candidate()` to preserve real source (correct, done this
    session) broke `sharing.py`'s hardcoded `WHERE source =
    'ai_escalation'` filter — approved Agent Harness entries no longer
    reach share-exports. One-line fix, needs a real test (existing
    tests insert rows directly, bypassing the actual approval path,
    which is why this wasn't caught).
16. **No CI, no linter, no type checker**, despite source code
    carrying `# noqa:` / `# type: ignore` annotations for tools that
    aren't installed or run anywhere.
17. Several docstring-drift items (`docs/SHOW_ME_MODE.md` and
    `docs/ASSIMILATOR_PROJECT.md` still say "Status: DESIGN ONLY" —
    the same defect `abbdb4b` explicitly fixed for Shoulder Mode/Agent
    Harness was reintroduced two commits later for these two docs;
    `doctor.py`'s docstring claims no subprocess spawns while `vpn.py`
    spawns one).

## What's confirmed GOOD and safe to show a live tester today

Both reviews independently confirmed these are solid, tested, and
ready: the match engine's false-positive gates, coach/suggest ranking,
report renderers (outside the Show Me gap above), the wizard,
`recap.py`, `doctor.py`, confidence labels on matches, the intake
provenance fix itself (the regression is in `sharing.py`'s filter, not
the fix), and the Tools/Advanced TUI menus for everything except Show
Me Mode (loot, recap, GTFOBins, hash classifier, doctor all work).

## Re-enable checklist

Before un-quarantining, at minimum:
- [ ] Architecture decision made and documented (recon-only rescope,
      or real persistent-session build)
- [ ] `record_shell()` call removed from the live-execution path;
      nothing mutates student state until they run the recipe
      themselves
- [ ] TUI thread-safety fixed (separate connection per worker, real
      error handling with visible failure state)
- [ ] Report disclosure fires on ANY Show Me run regardless of
      outcome, in all three renderers including notebook
- [ ] `check_already_known()` reworked to run pre-agent against real
      findings with a tightened confidence bar
- [ ] Denylist/target-pin re-evaluated against whatever the
      architecture decision implies for the actual threat model
- [ ] Wall-clock cap + abort path implemented
- [ ] `sys.stdin.isatty()` consent gate added
- [ ] A fresh, independent review pass on the specific diff that
      re-enables it

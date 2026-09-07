# Coach Subsystem — Design Doc

Status: DESIGN ONLY. Nothing in this document is built yet. This is a
scoped design pass per Alexander's request, following the same rigor
as `docs/AD_ENGINE_PROTOTYPE_PROJECT.md` before any code is written.

## Origin

Alexander's framing, verbatim intent: Trinity's Shoulder Mode already
watches the operator's terminal live. When a box needs an interactive,
multi-turn tool (Metasploit, a landed reverse shell, evil-winrm), does
Trinity actually help someone use it, step by step, live? Today: no.
Shoulder Mode only recognizes "a shell/root prompt appeared" — it has
zero awareness of the *tool session itself*, so an operator sitting at
an `msf6 >` prompt having forgotten to `set RHOSTS` gets no help at
all, even though Trinity is technically watching every keystroke.

This doc designs a **Coach subsystem**: a live, per-tool-session
extension of what Shoulder Mode already captures, narrating and
nudging through a recognized interactive tool's session the same way
Instructor Mode's hint ladder already narrates and nudges through
Trinity's own CLI. This is explicitly NOT a new capture mechanism —
it reuses Shoulder Mode's existing pty stream — and NOT a new
escalation UX — it reuses Instructor Mode's existing nudge -> stronger
nudge -> explicit-answer ladder shape. What's new is the middle layer:
recognizing WHICH tool session is currently active inside the watched
pane, and tracking a small expected-sequence/state-machine per tool.

## Hard rule, non-negotiable, stated up front

**The coach only ever observes, narrates, and nudges. It NEVER injects
keystrokes into the tool session on the operator's behalf.** This is
the same "Trinity never runs the box" line that governs Shoulder Mode,
AutoRecon, and every other capability in this codebase (see
`docs/OPEN_DECISIONS.md`'s auto-run rail) — extended explicitly to
cover live interactive sub-sessions, where the temptation to "just
type `set RHOSTS $TARGET` for them" would be strongest. If a future
session of this project catches itself writing anything that sends
bytes INTO the watched pty (as opposed to reading FROM it), that is
the rail. Confirm this against Shoulder Mode's own "What this does
NOT do" section before writing the capture-side code.

## Scoping decision: which tools actually need a coach

Kali/Parrot ship 600+ tools between them, but the overwhelming
majority are single-shot CLI invocations (nmap, gobuster, ffuf, nikto,
hydra, sqlmap default mode, john, hashcat, whatweb, enum4linux-ng,
theHarvester, recon-ng, WPScan, searchsploit) — run once with flags,
read output, react. These are already fully served by Trinity's
existing suggest engine + explain cache. There is no multi-turn
session to get lost in, so a coach adds nothing here. Verified via
live web research (2026-09-07), not assumed.

The coach concept only earns its keep for tools with their OWN
interactive, multi-turn session — a sub-REPL the operator navigates by
typing successive commands, where forgetting a step or not knowing
what comes next is a real, common failure mode. Confirmed real
examples, ranked by real-world frequency across HTB/THM-style Linux
and Windows/AD engagements:

1. **A landed raw shell itself** (reverse or bind, before/without a
   dedicated framework) — universal; happens on essentially every box
   regardless of foothold method. Highest value, lowest tool-specific
   complexity (no external binary's own prompt/output format to parse
   — just recognizing shell-landed, which Shoulder Mode already does).
2. **msfconsole** (Metasploit Framework) — the clearest, most
   requested example; has its own prompt (`msf6 >`), its own
   multi-step workflow (search -> use -> set options -> run/exploit ->
   sessions -i), and is genuinely one of the most common places
   beginners stall.
3. **evil-winrm** — confirmed via live research as extremely common on
   Windows/AD boxes specifically, once credentials are in hand
   (`evil-winrm -i <target> -u <user> -p <pass>`); has its own prompt
   and a small but real command surface (`upload`, `download`, `menu`
   for loading scripts/binaries).

Second-wave candidates, real and worth building later, explicitly
DEFERRED from this pass (listed here so they're not forgotten, not
because they don't matter):

- **smbclient's interactive shell** (`smb: \>` prompt) — common,
  smaller command surface than evil-winrm (ls/get/put/cd), lower
  urgency.
- **Impacket's `wmiexec.py`/`smbexec.py`** — each drops into its own
  shell-like prompt, distinct from evil-winrm's; real but narrower.
- **gdb/pwndbg** — real interactive REPL specific to binary
  exploitation/pwn challenges; narrower audience than the web/AD-heavy
  HTB Easy/Medium boxes this project has focused on so far, but a
  genuine, common source of confusion for that audience when it comes
  up.
- **mysql/psql interactive clients** — once DB creds are found, real
  session, smaller/more standardized command surface (well-known SQL),
  lower urgency since the SQL itself isn't Trinity's teaching domain.

**Do not build second-wave profiles in the same pass as first-wave.**
Prove the shared engine works cleanly for one full profile
(post-exploitation shell) before adding msfconsole/evil-winrm, and
prove those two before ever touching the second wave. Second-wave
tools also have a materially different command surface shape
(smbclient/mysql are much smaller/simpler state machines than
msfconsole/evil-winrm) — don't assume the same profile shape fits all
of them without re-examining each one specifically when its turn
comes.

## Architecture: one shared engine, per-tool profiles plugged in

Do NOT build one bespoke Python module per tool with duplicated
capture/nudge/escalation logic. Build ONE small coach engine (state
machine + hint-ladder wiring, reusing `hints.py`'s existing
nudge -> stronger nudge -> answer pattern) that any tool PROFILE plugs
into as data, the same "shared engine, pluggable profile" shape
`platform_registry.py` already uses for HTB/THM/VulnHub platform
differences, and the same shape `advisories.py` uses for its provider
registry.

### Data shape (sketch, refine at build time)

```
CoachProfile
  tool_id: str                    # 'msfconsole', 'evil-winrm', 'raw_shell'
  prompt_pattern: re.Pattern      # recognizes "we are now inside this tool's session"
  exit_pattern: re.Pattern        # recognizes "session ended" (prompt returned to normal shell)
  states: list[CoachState]        # ordered or graph-shaped expected steps

CoachState
  name: str                       # e.g. 'awaiting_module_selection'
  recognize: re.Pattern           # what operator input/tool output means "we are in this state"
  expected_next: list[str]        # command patterns that are a normal, on-track next move
  stall_nudge: str                # phrase for a first-level nudge if nothing matches for N lines/seconds
  stall_stronger_nudge: str       # second-level nudge (more specific, still no literal command)
  stall_answer: str               # third-level: literal next command, Instructor-Mode style
```

This mirrors `hints.py`'s existing three-level structure exactly —
`build_hint()`'s level-1/2/3 shape (Socratic -> nudge -> literal
answer) is the same escalation a coach state's stall response should
use, not a new invented pattern.

### How it plugs into Shoulder Mode

`shoulder.py`'s `record_session()` already tees every byte of the pty
to a log file. The coach's job is a SECOND, LIVE consumer of that same
stream (not a replacement for `scan_for_milestones()`'s existing
shell/root detection, which keeps running independently) — as new
lines arrive:

1. Check if any `CoachProfile.prompt_pattern` newly matches (operator
   just entered a recognized tool's session) — if so, announce it
   ("Looks like you're in msfconsole now — I'll narrate along the way
   if you get stuck") and set the active profile/state.
2. While a profile is active, match each new line against the current
   `CoachState.recognize` pattern to track state transitions (operator
   ran `use exploit/...` -> now in "module selected" state -> expected
   next is `set RHOSTS`/`set LHOST`/`show options`/`run`).
3. If N lines or M seconds pass with no state transition and no
   `expected_next` match (the operator is idle or repeating the same
   failing thing), fire the stall ladder — level 1 first, escalating
   only if the stall continues, same "starts back at a nudge, never
   inherits escalation from an unrelated earlier stall" rule
   `hints.py`'s `_advance_hint_level` already documents.
4. Check `exit_pattern` to know when the tool session ended and hand
   control back to Shoulder Mode's normal (non-coached) narration.

This needs a live-updating read loop, not `shoulder.py`'s current
"record everything, scan the whole transcript once at the end"
pattern (`record_session()` writes then `scan_for_milestones()` reads
after the fact) — the coach fundamentally needs to react WHILE the
session is running, which is a real, new piece of plumbing this
project must design carefully (likely: `record_session()` gains an
optional per-chunk callback hook that the coach registers into,
rather than the coach re-implementing pty capture itself). Get this
plumbing right for one profile before assuming it generalizes.

### Where profile content comes from (reuses the Update Framework, per Alexander's own instinct)

Alexander's stated idea: "if a program doesn't have a coach yet,
Trinity should be able to ask the operator's own agent CLI to draft
one, review it, then guide install/use." This is not a new mechanism —
it's the Agent Harness + Update Framework's intake queue, already
built for exactly this shape of problem (`docs/AGENT_HARNESS.md`,
`docs/UPDATE_FRAMEWORK.md`), pointed at a new content type
("coach profile") instead of "command explanation" or "methods index
entry." Concretely:

1. **Path A (this project, first-wave): hand-authored profiles.**
   Same trust tier as the existing 6 KB entries and 86 ELI5
   explain-seed entries — a human (or Claude, reviewed) writes the
   `CoachProfile` data for raw-shell/msfconsole/evil-winrm directly,
   shipped as defaults, same as `kb/seed.py`'s pattern.
2. **Path B (future project, NOT this pass): live-drafted profiles.**
   When Shoulder Mode recognizes an UNKNOWN interactive prompt pattern
   it has no profile for, Trinity can ask the Agent Harness to draft a
   `CoachProfile` for that tool (given its name/a sample of its
   prompt/help output), route the draft through the SAME intake-queue
   review gate as every other Agent-Harness-generated content type
   (never auto-trusted, reviewed before it's live), then use it. This
   is a real, coherent extension of the existing architecture — but
   it is explicitly a LATER phase, built only after Path A proves the
   engine/profile shape works for at least one real tool. Do not build
   the self-learning half before the hardcoded half is proven.

## Build order (once approved)

1. **DONE.** Shared coach engine (`src/trinity/shell_coach.py` --
   deliberately NOT `coach.py`, which already exists as Instructor
   Mode's suggestion-ranking layer, an unrelated system) + ONE
   profile: raw landed shell. No external tool's prompt/output format
   to parse -- this profile reuses Shoulder Mode's EXISTING shell/root
   detection (`scan_for_milestones`'s own regex, literally shared via
   the same pattern) as its "session started" signal, then a small,
   real post-foothold checklist (stabilize the tty, `id`/`whoami`,
   check `sudo -l`, check SUID, check cron) as its expected-next-steps
   state machine. Wired live into `shoulder.py`'s `record_session()`
   via a new optional `on_chunk` callback parameter (the pty capture
   loop already reads 4096-byte chunks; the callback fires on each
   one, feeding a line-buffered `CoachSession.feed_line()` -- this IS
   the "per-chunk callback hook" plumbing point flagged as an open
   design question above, now resolved: callback on `record_session`,
   not a competing capture mechanism). `trinity shoulder` prints
   coach narration inline via a `[coach]` prefix. Proven end-to-end
   against a REAL spawned pty subprocess (not just unit tests over
   synthetic strings) -- confirmed shell-landing announcement + a
   level-1 stall nudge both fire correctly from real captured bytes.
   9 new unit tests (`test/unit/test_shell_coach.py`), 384/384 passing
   full suite.
2. **msfconsole profile.** First real external-tool prompt to
   recognize (`msf6 >` / `msf >`), first real multi-step workflow
   (search/use/set/run/sessions). Proves the engine generalizes past
   the raw-shell special case.
3. **evil-winrm profile.** Second real external tool, confirms the
   engine handles a genuinely different command surface (upload/
   download/menu vs Metasploit's module-based flow) without needing
   per-tool special-casing in the engine itself — if it does need
   special-casing, that's a signal the engine's abstraction was wrong
   and needs revisiting before adding more profiles.
4. **Live plumbing hardening** — once 3 profiles exist and are
   genuinely used, revisit whether the live-callback approach from
   step 1 held up under real multi-hour sessions (context leaks,
   missed transitions on fast typers/pastes, false stall triggers on
   an operator who's just reading output slowly) before considering
   this "done" rather than "prototyped."
5. **Path B (Agent-Harness live profile drafting)** — only after step
   4, its own project, its own design-doc-level scrutiny on the
   review-gate specifics for this new content type.

## Explicitly out of scope for this pass

- Any second-wave tool profile (smbclient, Impacket shells, gdb/
  pwndbg, mysql/psql) — listed above for completeness, not scheduled.
- Path B (self-learning/live-drafted profiles) — scoped above as a
  clearly later, separate project.
- Any keystroke injection into the watched session, under any
  circumstance, for any reason (see "Hard rule" above).
- Any change to Shoulder Mode's existing shell/root milestone
  detection — the coach is an ADDITIONAL consumer of the same stream,
  not a replacement or modification of what's already there.
- Any new CLI command beyond what's needed to enable/announce coach
  mode inside the existing `trinity shoulder` command — this should
  feel like Shoulder Mode got smarter, not like a new subsystem the
  wizard has to teach (same Hole F discipline as everything else).

## Open questions for whoever builds this

- Exact stall-detection threshold (N lines of unrecognized input, or
  M seconds of no input, or both) — not specified here, pick something
  conservative and document it, consistent with how
  `docs/UPDATE_FRAMEWORK.md` left its own interval choice open for the
  builder to pin down.
- Whether coach narration should be a SEPARATE visual channel from
  Shoulder Mode's existing milestone-detected messages (so an operator
  can visually distinguish "you got a shell" from "you seem stuck in
  msfconsole") — likely yes, but the exact rendering approach is a
  build-time UX decision, not a design-doc-level one.
- Whether `CoachProfile` definitions should live in a single Python
  module (like `kb/seed.py`) or as YAML files (like `platforms.yaml`)
  — YAML is probably more consistent with this project's "shipped
  defaults, locally extensible, PR-able upstream" crowdsourcing model,
  especially once Path B needs to write NEW profiles as data rather
  than code, but this is a build-time call.

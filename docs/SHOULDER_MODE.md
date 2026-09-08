# Shoulder Mode — Design

Status: BUILT. Implemented in `src/trinity/shoulder.py`
(pty recording + milestone detection), wired to `trinity shoulder
--box <name>` in `src/trinity/cli/main.py`, 39 passing unit tests
across `test/unit/test_shoulder.py` and related files. This doc
retains its original design rationale below; it is no longer a
proposal. This was an explicit, deliberate reversal of an earlier
decision — see
"Relationship to the earlier veto" below before assuming this
contradicts prior project history by accident.

## The goal

Today, watch-mode only reacts to files: it notices when a scan output
file lands in the watched directory and parses it. It has zero
visibility into the operator's OWN terminal pane — the one where they
actually run commands, get shells, and work privesc. Milestones
("I got a user shell") currently require the operator to self-report
via a command (`trinity shell --as user`), which is honest but is not
what Alexander actually wants: "I thought we were making Trinity be
able to see everything happening in the 2nd terminal... trinity can
see 'over our shoulder' the whole time... i want it to spy though.
that's the whole point."

Shoulder Mode is full visibility into the operator's own working pane
— not just its saved output files, but everything typed and everything
printed back, in real time — so Trinity can notice things itself
instead of asking.

## Relationship to the earlier veto

`docs/OPEN_DECISIONS.md` previously carried a "Shell-history sensors"
entry marked as a rail: reading `~/.bash_history`/`~/.zsh_history` to
infer what the operator ran was rejected as "surveillance-shaped,
fragile across shells, and easy to lie about (history off, another
user, timestamps)."

That veto is NOT wrong on its own terms — persistent shell history is
genuinely a bad signal (stale, shell-dependent, easy to disable,
doesn't capture output at all, only the command line typed). Shoulder
Mode is a different mechanism, not a loophole around the same one:

- Shell history reads a FILE that may or may not reflect what actually
  happened, after the fact, with no output attached.
- Shoulder Mode records the LIVE SESSION itself, byte for byte,
  input and output, in the one pane the operator explicitly started
  it against — the same category of thing as `script(1)` (a decades-
  old, well-understood Unix tool for exactly this), not a novel
  surveillance mechanism.
- Scope is explicit and narrow: only the pane the operator ran
  `trinity watch`/the shoulder-mode entry point against. Trinity never
  reaches into a DIFFERENT terminal, another user's session, or reads
  any persistent history file. The operator opted in by starting the
  session inside Trinity's own launched pane (or handing it a pty to
  attach to) — this is closer to "I'm running my recon tool through a
  wrapper that also happens to be watching" than "something is reading
  my files behind my back."
- Per Alexander's explicit call: this is a **hard requirement**, not
  an opt-in flag, when running in the dual-pane setup — "always on
  when running in the dual-pane setup" is the intended default
  experience, not a power-user toggle.

## Mechanism

**Recording:** `script`-equivalent capture of the operator's working
pane — every keystroke sent, every byte of terminal output, with
timing, into a session log Trinity's watch-mode process owns. Python's
`pty` module (stdlib) is the natural implementation surface — spawn
the operator's shell inside a pseudo-terminal Trinity controls, proxy
input/output transparently so the operator's actual experience is
unchanged (same shell, same prompt, same everything), while Trinity
taps the byte stream on the side.

**How the operator starts it:** the natural integration point is
`trinity watch` itself growing a mode where it launches (or attaches
to) the operator's actual working shell, rather than the operator
manually running `nmap`/`gobuster` in a totally separate pane Trinity
has no connection to. This changes the dual-pane story slightly: today
it's "two independent panes, linked only by the filesystem"; Shoulder
Mode makes one of those panes something Trinity itself spawned and is
watching directly. `docs/DESIGN.md`'s existing "Trinity does not
orchestrate the operator's environment / no hyprctl" rail is NOT
violated by this — Trinity still never opens a tile, spawns a window,
or touches the window manager. It's watching a SHELL SESSION, not
managing WINDOWS. That distinction matters and should stay explicit
in any implementation: `docs/OPEN_DECISIONS.md`'s `trinity lab` veto
is about window/tile orchestration and remains fully in force; this is
about terminal I/O capture within a pane the operator is already using
Trinity from.

**Signal extraction (what Trinity actually looks for in the stream):**
- Shell prompt changes suggesting a new user context (e.g. a
  `whoami`/prompt-string change consistent with `su`/a reverse shell
  landing).
- Specific command invocations that ARE the milestone signal
  themselves — running an exploit that's known to pop a shell,
  `sudo -l` output showing exploitable entries, a `find ... -perm
  -4000` result naming a GTFOBins-covered binary, an `id`/`whoami`
  call returning `root`.
- The same finding-shaped facts the parsers already extract from
  scan files, just sourced from live terminal output instead of a
  saved file afterward — conceptually, this is "one more parser,"
  reading a different kind of stream (live pty output instead of a
  static file), feeding the exact same `process_scan_file`-shaped
  pipeline (findings → match → suggest → timeline) that already
  exists. Do not build a second, parallel pipeline for
  terminal-derived findings; feed the existing one.

**Milestone auto-detection**: once shell-context signals are reliably
extractable, `milestones.py::record_shell()` gets called automatically
from the stream detector instead of requiring `trinity shell --as
user`. The manual command should remain as a fallback/override (for
false-negatives, or operators not running Shoulder Mode), not be
removed.

## Privacy and trust framing (still matters, even with this reversal)

Full session recording is a materially bigger trust step than
anything else Trinity does, and being an honest OSS project about it
matters more here, not less:

- The recording is LOCAL ONLY by default — same rule as everything
  else in Trinity (no silent network). It only ever leaves the machine
  if the operator explicitly opts into sharing something derived from
  it (and even then, only structured findings/milestones get shared,
  never raw session transcripts — see `docs/UPDATE_FRAMEWORK.md`'s
  opt-in sharing rules, which apply here too).
- The operator should be able to see clearly, at any time, that
  Shoulder Mode is active (a persistent visual indicator, not a silent
  background capture) — same "nothing hidden" principle as the rest
  of the product.
- Raw session logs should have a retention policy (e.g. kept only for
  the active box's lifetime, deleted on `box-status rooted/abandoned`,
  or truncated to a rolling window) rather than accumulating forever —
  full keystroke/output logs are exactly the kind of data that
  shouldn't silently pile up unbounded on disk.
- README/CONTRIBUTING should state this plainly and early — a public
  OSS security tool that records full terminal sessions needs to be
  loud about that fact, not quiet about it, for the same reason
  `docs/OPEN_DECISIONS.md` already treats trust-boundary changes as
  worth a dedicated writeup rather than a quiet code change.

## What this does NOT change

- Trinity still never runs a command for the operator. Shoulder Mode
  watches; it does not inject keystrokes, does not auto-run anything,
  does not auto-answer prompts on the operator's behalf. Read-only
  tap on the byte stream, not a puppeteering layer.
- `docs/OPEN_DECISIONS.md`'s `trinity lab`/hyprctl veto (no window/tile
  orchestration) is unaffected — this is pty/shell-level, not
  WM-level.
- Auto-install, auto-run-scans, and auto-run-exploits remain vetoed.
  Seeing that the operator ran an exploit is not the same as running
  one — the line stays exactly where it was.

## Build order (once approved)

1. `pty`-based shell proxy as a standalone module, proven first with
   zero Trinity-specific parsing — just prove transparent pass-through
   works and the operator's actual shell experience is unaffected.
2. A minimal stream-tap that logs raw output to a bounded local file
   (retention policy from day one, not bolted on later).
3. Milestone-shaped signal detection (shell context changes, specific
   command/output patterns) feeding the existing
   `milestones.py::record_shell()` path.
4. Wider finding extraction feeding the existing
   `process_scan_file`-shaped pipeline, reusing existing `Finding`/
   match/suggest machinery rather than a parallel system.
5. Visual "Shoulder Mode is active" indicator in the watch-mode
   dashboard, from the first version that does anything at all with
   the captured stream (not deferred to "later polish").

## Open questions for whoever builds this

- Exact shell-integration mechanism: does the operator run `trinity
  watch --shell` (which then spawns their shell inside Trinity's pty),
  or does Trinity attach to an already-running shell via some other
  mechanism? The former is simpler and more honest about what's
  happening; lean toward it unless a real blocker shows up.
- How noisy/false-positive-prone is shell-prompt-based context
  detection in practice, across common shells (bash/zsh/fish) and
  prompt customizations (starship, oh-my-zsh, etc.)? Needs real
  testing against actual configured shells, not just a bare bash
  assumption.
- Retention window specifics (time-based vs. size-based vs.
  box-lifetime-based) — pick one, document it, make it configurable
  later if it turns out to matter.

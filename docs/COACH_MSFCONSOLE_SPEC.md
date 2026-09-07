# Coach profile spec: msfconsole (step 2 of docs/COACH_SUBSYSTEM_DESIGN.md)

STATUS: ready to implement. Step 1 (shared engine + raw-shell profile)
is DONE and merged to main (`src/trinity/shell_coach.py`). This is a
NARROW, FULLY-SPECIFIED task: add ONE new profile to the EXISTING
engine. Do not touch `CoachSession`/`CoachState`/`CoachProfile`'s
dataclass shapes unless you hit something this spec genuinely didn't
anticipate — if that happens, STOP and write it to
`docs/AD_ENGINE_OPEN_QUESTIONS.md`-style open-questions file (create
`docs/COACH_OPEN_QUESTIONS.md` if it doesn't exist) rather than
silently redesigning the engine.

## What you're building

A `CoachProfile` for `msfconsole` (Metasploit Framework's interactive
console), added to `DEFAULT_PROFILES` in
`src/trinity/shell_coach.py`, following the EXACT same pattern as the
existing `RAW_SHELL_PROFILE` in that same file — read it first, it is
your template for structure, docstring style, and comment density.

## Read first (in order)

1. `docs/COACH_SUBSYSTEM_DESIGN.md` — full design rationale, hard
   rule (observe/narrate only, NEVER inject keystrokes), architecture.
2. `src/trinity/shell_coach.py` — the engine + the raw-shell profile
   you're mirroring. Pay attention to: `CoachState.recognize` /
   `expected_next` semantics, the "same line may both enter a profile
   AND match a state" handling in `_try_enter_profile`, and the
   comment style (every non-obvious regex/decision gets a "why", same
   as the rest of this codebase).
3. `test/unit/test_shell_coach.py` — the existing test suite for the
   raw-shell profile. Your new tests follow the same structure:
   feed synthetic line sequences into a fresh `CoachSession`, assert
   on the narration strings returned.

## Real msfconsole facts to build against (verify with your own
research pass before coding — do not take these as gospel, they are
a starting point, not a substitute for checking real tool output)

- Prompt: `msf6 >` (or `msf >` on older versions) at the top level;
  `msf6 exploit(windows/smb/ms17_010_eternalblue) >` once a module is
  selected via `use` (module path appears inside the parens).
- Typical real workflow, in order:
  1. `search <term>` — find a module (e.g. `search eternalblue`)
  2. `use <module/path>` — select it (prompt changes to show the
     module path, as above)
  3. `show options` — list required options
  4. `set RHOSTS <target>` (and often `set LHOST <attacker-ip>` for
     reverse-shell payloads, `set LPORT`, sometimes `set payload`)
  5. `run` or `exploit` — fire it
  6. `sessions -l` — list active sessions if it succeeded
  7. `sessions -i <id>` — interact with a specific session

## Profile design

- `prompt_pattern`: match `msf6? >` / `msf6? exploit(...)>` etc. —
  needs to match BOTH the bare top-level prompt and the
  module-selected variant. Write this carefully; msfconsole's prompt
  format is stable across versions but confirm with a real installed
  copy if `msfconsole` is available locally (check with
  `which msfconsole` — if present, launch it once yourself and paste
  a few real prompt lines into your test fixtures instead of guessing
  the exact regex shape).
- `exit_pattern`: recognize `exit`/`quit` at the msfconsole prompt, OR
  the shell returning to a normal OS prompt after msfconsole closes.
- States, roughly mirroring the real workflow above:
  - `searching` (operator ran `search`, hasn't `use`d anything yet) —
    expected_next: `use <something>`
  - `module_selected` (prompt shows the module path — this is your
    richest recognize signal, don't need separate detection of `use`
    itself) — expected_next: `set RHOSTS`, `show options`, `set
    LHOST`, `set payload`
  - `options_set` (a `set RHOSTS` or similar line was seen) —
    expected_next: `run`, `exploit`, `check`
  - `fired` (operator ran `run`/`exploit`) — expected_next: `sessions`
- Stall nudges should be Socratic first (per `hints.py`'s own level-1
  shape — no naming the exact tool/command yet), stronger nudge names
  the AREA (e.g. "you've picked a module but haven't told it what to
  attack yet"), full answer gives the literal command shape (e.g.
  `set RHOSTS <target>`) — this is the SAME 3-level pattern
  `RAW_SHELL_PROFILE` already uses, don't invent new phrasing rules.

## Guardrails — STOP AND ASK, do not silently do any of these

- Do not add any new CLI command. This profile plugs into the
  EXISTING `trinity shoulder` command's coach session automatically
  (it's already wired to try every profile in `DEFAULT_PROFILES`).
- Do not touch `RAW_SHELL_PROFILE` or the raw-shell tests.
- Do not touch the `CoachSession`/`CoachState`/`CoachProfile`
  dataclasses' shapes. If msfconsole's real workflow genuinely can't
  be expressed with the existing shallow checklist-state shape
  (e.g. because branching is much more complex than raw-shell's),
  log that specifically rather than redesigning the engine to fit.
- Do not add ANY keystroke-injection capability, ever, under any
  framing ("just to help them faster", "auto-fill the target IP",
  etc.) — the engine's hard rule is observe-only, and this profile
  must not be the one that breaks it.
- Do not scope-creep into a second profile (evil-winrm) — that's a
  separate, parallel task another agent is doing right now. Stay in
  your lane.

## Deliverable

- `MSFCONSOLE_PROFILE` added to `src/trinity/shell_coach.py`,
  registered in `DEFAULT_PROFILES`.
- New tests in `test/unit/test_shell_coach.py` (or a new
  `test_shell_coach_msfconsole.py` if you prefer to keep it separate
  — either is fine) covering: profile entry announcement, at least
  one full state-transition sequence (search -> use -> set -> run),
  and at least one stall-ladder test (mirroring the raw-shell stall
  tests' structure).
- Full test suite green (`uv run pytest -q`) — report the before/after
  count.
- A short report: what you built, any real msfconsole output you
  verified your regexes against (or confirmation you had to guess
  because msfconsole wasn't locally available), and anything you
  logged to `docs/COACH_OPEN_QUESTIONS.md` instead of silently
  deciding yourself.

Work in an isolated git worktree (branch `feat/coach-msfconsole`),
never touch `main` directly, do not push or merge — Doc reviews and
merges after.

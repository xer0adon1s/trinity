# Coach profile spec: evil-winrm (step 3 of docs/COACH_SUBSYSTEM_DESIGN.md)

STATUS: ready to implement. Step 1 (shared engine + raw-shell profile)
is DONE and merged to main (`src/trinity/shell_coach.py`). This is a
NARROW, FULLY-SPECIFIED task: add ONE new profile to the EXISTING
engine. Do not touch `CoachSession`/`CoachState`/`CoachProfile`'s
dataclass shapes unless you hit something this spec genuinely didn't
anticipate — if that happens, STOP and write it to
`docs/COACH_OPEN_QUESTIONS.md` (create it if it doesn't exist) rather
than silently redesigning the engine.

Another agent is simultaneously building a SEPARATE msfconsole profile
in a different worktree/branch, following an equivalent spec. Your
work is independent — do not touch anything related to msfconsole,
and expect a possible merge (not a conflict, since you're each adding
a new, separate `CoachProfile` constant) when Doc reconciles both.

## What you're building

A `CoachProfile` for `evil-winrm` (the standard post-credential
interactive WinRM shell tool used heavily on Windows/AD boxes once
credentials are in hand), added to `DEFAULT_PROFILES` in
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

## Real evil-winrm facts to build against (verify with your own
research pass before coding — do not take these as gospel, they are
a starting point, not a substitute for checking real tool output)

- Invocation (NOT something the coach launches — this is context for
  what the operator already typed before entering the tool):
  `evil-winrm -i <target> -u <user> -p '<password>'` (or `-H <hash>`
  for pass-the-hash).
- Prompt once inside: `*Evil-WinRM* PS C:\Users\<user>\Documents>`
  (a PowerShell-style prompt with the `*Evil-WinRM*` prefix — this is
  a very distinctive, low-false-positive-risk signal, use it as your
  primary `prompt_pattern`).
- Real command surface once inside (this is smaller/more
  standardized than msfconsole's module-based flow — do not assume
  the same shape of workflow applies, per the design doc's own
  warning that this profile should reveal whether the engine
  generalizes or needs special-casing):
  - Standard PowerShell/cmd commands work directly (`whoami`, `dir`,
    `type`, `cd`, etc.) since it IS effectively a PowerShell session.
  - `upload <local_path> <remote_path>` — evil-winrm's OWN built-in
    command for pushing a file to the target (e.g. a privesc-check
    script like WinPEAS).
  - `download <remote_path> <local_path>` — the reverse.
  - `menu` — lists evil-winrm's own loaded "Powershell scripts" if
    any were loaded with `-s <path>` at launch (less universally
    used, lower priority for your first-pass state coverage).
  - Common real early-session moves worth modeling as expected-next
    states: `whoami /priv` (checking token privileges — a very
    common real next step, since evil-winrm sessions often have
    exploitable privileges like SeImpersonatePrivilege), `net user`,
    `Get-LocalGroupMember Administrators` or similar enumeration.

## Profile design

- `prompt_pattern`: match the `*Evil-WinRM* PS ...>` prompt shape.
  This is distinctive enough that false-positive risk against other
  PowerShell-looking output should be low — but double check it
  doesn't accidentally also match `RAW_SHELL_PROFILE`'s own
  `PS [A-Z]:\\\S*>` pattern in a way that causes ambiguous double-entry
  (read `_try_enter_profile`'s loop order in `shell_coach.py` — first
  match in `DEFAULT_PROFILES` wins, so profile ORDER in the list
  matters if two patterns could both match the same line; flag this
  clearly in your report rather than silently reordering the list
  without saying so).
- `exit_pattern`: recognize `exit` at the evil-winrm prompt, or the
  connection closing (evil-winrm often just returns to the OS shell
  silently on exit — check real behavior if you can install/test it,
  otherwise document your best-effort pattern and flag the
  uncertainty in your report).
- Given the smaller, more freeform command surface here (versus
  msfconsole's clear linear module-workflow), a reasonable first-pass
  state design:
  - `landed` (prompt recognized) — expected_next: `whoami`, `whoami
    /priv`, `net user`, `hostname`
  - `enumerated` (a `whoami /priv` or `net user` was seen) —
    expected_next: `upload`, `Get-LocalGroupMember`, `systeminfo`
  - Consider whether a THIRD state for "uploaded a tool, now what"
    is worth it or overkill for a first pass — your call, but explain
    your reasoning in the report either way.
- Stall nudges: same 3-level Socratic -> named-area -> literal-command
  shape as `RAW_SHELL_PROFILE`. First nudge should NOT name
  `whoami /priv` outright — ask what's worth checking about privilege
  level once you have PowerShell access as a specific user.

## Guardrails — STOP AND ASK, do not silently do any of these

- Do not add any new CLI command. This profile plugs into the
  EXISTING `trinity shoulder` command's coach session automatically.
- Do not touch `RAW_SHELL_PROFILE`, its tests, or (if present when
  you start) an `MSFCONSOLE_PROFILE` another agent may be adding in
  parallel — only ADD your own profile and its own tests.
- Do not touch the `CoachSession`/`CoachState`/`CoachProfile`
  dataclasses' shapes. If evil-winrm's real command surface genuinely
  can't be expressed with the existing shallow checklist-state shape,
  log that specifically (this is actually the MOST likely place to
  find such a gap, per the design doc's own framing — evil-winrm's
  freeform PowerShell surface is a good stress test of whether the
  engine's abstraction holds) rather than redesigning the engine.
- Do not add ANY keystroke-injection capability, ever, under any
  framing — the engine's hard rule is observe-only.
- Do not scope-creep into smbclient/Impacket/gdb/mysql profiles —
  those are explicitly second-wave, deferred, not this task.

## Deliverable

- `EVIL_WINRM_PROFILE` added to `src/trinity/shell_coach.py`,
  registered in `DEFAULT_PROFILES`.
- New tests in `test/unit/test_shell_coach.py` (or a new
  `test_shell_coach_evilwinrm.py` — either is fine) covering: profile
  entry announcement, at least one state-transition sequence, and at
  least one stall-ladder test.
- Full test suite green (`uv run pytest -q`) — report the before/after
  count.
- A short report: what you built, whether the freeform command
  surface required any judgment calls versus msfconsole's more linear
  workflow, any real evil-winrm output you verified your regexes
  against (or confirmation you had to guess), and anything logged to
  `docs/COACH_OPEN_QUESTIONS.md` instead of silently deciding
  yourself.

Work in an isolated git worktree (branch `feat/coach-evilwinrm`),
never touch `main` directly, do not push or merge — Doc reviews and
merges after.

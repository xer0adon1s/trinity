# Coach subsystem: open questions for the engine

Findings from building individual `CoachProfile`s that felt like they
might eventually warrant a change to the shared engine in
`src/trinity/shell_coach.py`, logged here instead of being decided
unilaterally by whoever happened to hit them (per
`docs/COACH_SUBSYSTEM_DESIGN.md` and the per-profile specs, which both
ask contributors to log rather than redesign). Nothing here blocked
shipping the profile it was found under — each was worked around at
the profile-authoring level, documented in code comments at the
point of the workaround.

## A recurring `recognize` pattern silently disables stall nudges — FIXED

**Status: fixed in `CoachSession._advance_active_profile`** (see
`test/unit/test_shell_coach_engine_fix.py` for the regression suite).
The section below is kept as historical record of how this was found
and reasoned about — both real profiles' existing workarounds
(banner/one-shot-command `recognize` patterns instead of a tool's
live per-line prompt) remain in place and are unaffected by this fix;
they were correct defensive choices independent of the engine bug,
not made obsolete by fixing it (a future profile author can now
safely reuse a live prompt as a state's `recognize` pattern too, but
doesn't have to retrofit existing profiles to do so).

**Found while building:** `EVIL_WINRM_PROFILE` (step 3,
`docs/COACH_EVILWINRM_SPEC.md`).

`CoachSession._advance_active_profile` returns early -- with no
narration, and *before* the stall-counter logic ever runs -- on ANY
line that matches ANY state's `recognize` pattern, including a
same-state re-match:

```python
for state in profile.states:
    if state.recognize.search(line):
        if state is not self.active_state:
            self.active_state = state
            self.stall_counter = 0
            self.stall_level = 0
        return None
```

This is harmless for a `recognize` pattern that's a genuine one-time
event (a banner, an `id` command's output). It's a real problem for a
`recognize` pattern that matches something the TOOL reprints on every
single line -- which is exactly what an interactive tool's own prompt
usually is. `RAW_SHELL_PROFILE`'s "landed" state reuses its own
`prompt_pattern` as its `recognize` (`_RAW_SHELL_PROMPT`, which
includes the `www-data@` and `PS [A-Z]:\S*>` alternatives) -- for a
raw shell this mostly works out because those particular signals tend
to be one-time (an `id`/banner line), not a live, per-command prompt.

evil-winrm doesn't get that same luck: its distinctive
`*Evil-WinRM* PS <pwd>>` prompt reprints before literally every
command, with no way for the operator to suppress it. Had
`EVIL_WINRM_PROFILE`'s "landed" state reused its own `prompt_pattern`
the same way `RAW_SHELL_PROFILE` does, every single operator-typed
line would re-match "landed" and return early -- meaning
`stall_counter` would never increment, in real usage, for any state,
ever. The engine's stall-nudge ladder would be silently dead code for
this profile.

**msfconsole hit the same underlying issue independently** (built in
parallel, step 2, `docs/COACH_MSFCONSOLE_SPEC.md`): the spec wanted
`msf6 exploit(...) >` (the module-context prompt) as the richest
"module selected" signal, but that prompt ALSO reprints on every
subsequent line (including the empty prompt after `set RHOSTS`).
Under first-match-wins that would snap the session back from
`options_set`/`fired` to `module_selected` after every command --
same root cause as evil-winrm's stall-suppression bug, different
symptom (state thrashing instead of dead stall detection).

**Workarounds used (profile-level, no engine change, in both cases):**
- `EVIL_WINRM_PROFILE`'s "landed" state recognizes evil-winrm's
  one-time startup banner line (`Evil-WinRM shell v...`, printed once
  at connect) instead of the live prompt. `prompt_pattern` (used only
  for profile-entry detection) still uses the live prompt as its
  primary signal, with the banner as a secondary alternative so entry
  is still detected on a session Shoulder Mode was already recording
  before the tool launched.
- `MSFCONSOLE_PROFILE` recognizes the one-shot `use <module>` command
  instead of the module-context prompt.

Both workarounds only work because each tool happens to have SOME
one-time signal to fall back on (a banner, a one-shot command). A
future profile whose tool reprints a persistent prompt AND has no
comparable one-time landing/transition signal would hit this with no
clean profile-level fix available.

**Engine-level fix, now applied:** don't short-circuit on a re-match
of the state that's *already* active — only return early on a
transition to a genuinely *different* state, and let a same-state
re-match fall through to the stall-counting logic below it (still
resetting the counter, just not skipping the return). This lets a
profile safely reuse its own prompt pattern as a state's `recognize`
without losing stall detection or causing state thrashing, matching
the more intuitive reading of "this line reaffirms where we are"
rather than "this line means nothing happened." Confirmed via a
dedicated regression suite (`test/unit/test_shell_coach_engine_fix.py`)
built around a minimal synthetic profile shaped exactly like the
failure case, verified to genuinely fail against the pre-fix code
(not just pass trivially), and re-verified live against a real
spawned pty subprocess.

## `back` does not deselect — FIXED

**Status: fixed via a `top_level` CoachState in `MSFCONSOLE_PROFILE`**
(see `test_msfconsole_back_returns_to_top_level_no_stale_module_nudge`
in `test/unit/test_shell_coach_msfconsole.py`). `back` is now
recognized the same safe way `use`/`search` are — a one-shot typed
command, not a live reprinting prompt — so it's a valid `recognize`
pattern per the engine fix above. `back` returning the console to
`msf6 >` now correctly clears `active_state` off whatever
module-context state (module_selected/options_set/fired) was
previously active, instead of leaving stall nudges stuck on stale
module-specific advice (e.g. "set RHOSTS") after the operator had
already backed out with nothing selected.

## Other required options (TARGETURI, RPORT, SMBUSER, etc.) — left as-is

Alexander's call (2026-09-07): current scoping is fine, note for
later, low priority. Only `set RHOSTS`/`set RHOST`/`setg RHOSTS`
enters `options_set` — LHOST/LPORT/payload remain on-track
`expected_next` from `module_selected` so setting a callback address
alone doesn't pretend the module is ready to fire. Not revisited
unless a real profile run shows this under-triggering `options_set`
in practice.

## msfconsole: other checklist-shape gaps (found 2026-09-07)

The existing shallow checklist (`recognize` = "we are in this state",
first match wins, no backward edges) does not quite fit a few other
real msfconsole shapes, beyond the shared issue above. Logged rather
than redesigning `CoachState`/`CoachSession`.

- **Already-in-module at capture start.** Restored `ActiveModule`,
  `msfconsole -x "use ..."`, or joining a session mid-module means
  the first captured line is already `msf6 exploit(...) >` with no
  `use` in the stream. Profile entry still fires; `active_state`
  stays None until the next `use`/`search`/`set RHOSTS`/`run`. A
  stall at that empty-state prompt produces no nudge (engine returns
  None when `active_state is None`). **Alexander's call: low
  priority, future feature, not critical.**

- **Meterpreter is a nested session — FIXED.** See
  `docs/COACH_METERPRETER_NESTING_DESIGN.md` for the full design and
  `test/unit/test_shell_coach_meterpreter.py` for the regression
  suite. Resolved via a `profile_stack` on `CoachSession` plus
  `nested_profiles` on `CoachProfile` — a LIFO stack, not a full
  graph-shaped state machine, since nesting always returns to the
  exact parent it was entered from. A new `METERPRETER_PROFILE` is
  registered only as `MSFCONSOLE_PROFILE.nested_profiles`. Popping
  back to the parent resets `active_state` to a blank slate rather
  than restoring msfconsole's prior state, so backing out of a real
  Meterpreter session no longer triggers stale "have you listed your
  sessions" nagging. A dropped/died Meterpreter connection (no typed
  exit) is also handled via the parent's own prompt reappearing.

- **Custom `Prompt`/`PromptChar`.** Operators can `setg Prompt`
  (`%T` timestamp, `%W` workspace, arbitrary text). We only match
  the default `msf`/`msf5`/`msf6` (+ module-context) form from
  driver.rb. Fancy Kali two-line OS prompts after exit are also
  unmatched; only `user@host:...$`/`#` is treated as "shell came
  back." **Alexander's call: low priority, future feature.**

- **Other required options.** See "Other required options" above —
  resolved as a logged decision, not a bug.

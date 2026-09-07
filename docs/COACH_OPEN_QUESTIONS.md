# Coach subsystem: open questions for the engine

Findings from building individual `CoachProfile`s that felt like they
might eventually warrant a change to the shared engine in
`src/trinity/shell_coach.py`, logged here instead of being decided
unilaterally by whoever happened to hit them (per
`docs/COACH_SUBSYSTEM_DESIGN.md` and the per-profile specs, which both
ask contributors to log rather than redesign). Nothing here blocked
shipping the profile it was found under -- each was worked around at
the profile-authoring level, documented in code comments at the
point of the workaround.

## A recurring `recognize` pattern silently disables stall nudges

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

**Workaround used (profile-level, no engine change):**
`EVIL_WINRM_PROFILE`'s "landed" state recognizes evil-winrm's
one-time startup banner line (`Evil-WinRM shell v...`, printed once
at connect) instead of the live prompt. `prompt_pattern` (used only
for profile-entry detection) still uses the live prompt as its
primary signal, per the spec, with the banner as a secondary
alternative so entry is still detected on a session Shoulder Mode
was already recording before the tool launched. See the comment
block directly above `_EVIL_WINRM_BANNER` in `shell_coach.py` for the
full reasoning.

This workaround only works because evil-winrm happens to have a
one-time banner line to fall back on. A future profile whose tool
reprints a persistent prompt AND has no comparable one-time landing
signal (a plausible shape for e.g. a hypothetical msfconsole-style
profile, if `msf6 >` were reused as a state's `recognize` the same
way) would hit this with no clean profile-level fix available.

**Possible engine-level fix, NOT applied here:** don't short-circuit
on a re-match of the state that's *already* active -- only return
early on a transition to a genuinely *different* state, and let a
same-state re-match fall through to the stall-counting logic below
it (still resetting the counter, just not skipping the return). That
would let a profile safely reuse its own prompt pattern as a state's
`recognize` without losing stall detection, matching the more
intuitive reading of "this line reaffirms where we are" rather than
"this line means nothing happened." Flagging rather than implementing
since it changes `CoachSession`'s control flow, which the specs for
both second-wave profiles were explicit about not doing unilaterally.

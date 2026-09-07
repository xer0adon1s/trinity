# Meterpreter nested-session design (Coach subsystem)

Status: APPROVED, implementing directly in this pass (per Alexander's
2026-09-07 call: "agreed. fully plan and implement this system/fix" —
critical engine-level system, Doc builds it directly, not delegated).

## The problem (from docs/COACH_OPEN_QUESTIONS.md)

> Meterpreter is a nested session. A successful `run`/`exploit` often
> drops the operator into `meterpreter >` rather than leaving them at
> `msf6 >` to type `sessions`. The spec's `fired -> expected_next:
> sessions` does not represent that fork. The coach stays in the
> msfconsole profile (exit_pattern does not match `meterpreter >`)
> and will eventually stall-nudge toward `sessions` while they are
> already inside the session. A nested profile or a graph-shaped
> state machine would be needed; both are engine changes.

`CoachSession` today tracks exactly ONE active profile at a time
(`active_profile: CoachProfile | None`). It has no concept of "this
tool session was launched FROM INSIDE another tool session" — which
is exactly what happens the moment `run`/`exploit` succeeds: the
`msf6 >` session doesn't end, it's just suspended underneath a brand
new `meterpreter >` session sharing the same pty. The engine currently
has no way to represent that without either (a) losing track of
msfconsole entirely (misreading `meterpreter >` as some unrelated
prompt, or worse, using RAW_SHELL_PROFILE's generic detection and
misclassifying it), or (b) staying "stuck" in msfconsole's `fired`
state and nagging about `sessions -l` while the operator is
demonstrably already inside a session.

## Chosen design: a profile stack (LIFO), not a graph

The design doc's own build-order note flagged this as "a nested
profile or a graph-shaped state machine." A full graph-shaped state
machine is a much bigger change than this problem actually needs —
nesting is fundamentally a STACK, not an arbitrary graph: you enter a
child session from a specific point in the parent, and you always
return to that same parent when the child ends. A stack captures that
exactly, stays consistent with the existing "shallow checklist, not a
graph" philosophy for the states WITHIN each profile, and generalizes
to future nested pairs (smbclient dropping into a sub-shell, wmiexec,
etc.) without redesigning anything.

### Data shape changes

```python
@dataclass
class CoachProfile:
    ...  # unchanged existing fields
    nested_profiles: list[CoachProfile] = field(default_factory=list)
    # Profiles that can be entered as a nested child WHILE this
    # profile is the active one -- checked regardless of which
    # CoachState is currently active within this profile. Empty for
    # every existing profile (raw_shell, evil-winrm) -- this is
    # additive and changes zero behavior for profiles that don't
    # declare any nested children.

@dataclass
class CoachSession:
    ...  # unchanged existing fields
    profile_stack: list[CoachProfile] = field(default_factory=list)
    # Parent profiles waiting underneath the currently active nested
    # child, most-recently-entered last. Empty whenever there's no
    # nesting in play (the overwhelmingly common case). Deliberately
    # stores ONLY the profile, not its prior CoachState/stall
    # counters -- see "Why the parent's state resets" below.
```

### Engine changes in `_advance_active_profile`

Three checks, in this order, before the existing state-transition/
stall logic (which is otherwise completely unchanged):

1. **Own exit.** Unchanged trigger (`profile.exit_pattern`), but the
   action changes: if `profile_stack` is non-empty, POP back to the
   parent profile instead of ending the whole coach session. Only a
   genuinely empty stack (the normal, non-nested case) fully ends the
   session the way it always has.
2. **Implicit exit via parent prompt reappearing.** NEW safety net: if
   `profile_stack` is non-empty and the CURRENT line matches the
   PARENT profile's own `prompt_pattern`, pop — even without a typed
   `background`/`exit` command. This covers a dropped Meterpreter
   connection, which Metasploit reports with an unprompted "Meterpreter
   session N closed" message and returns straight to `msf6 >` without
   the operator typing anything. Without this, a dead session would
   permanently strand the coach believing it's still inside
   Meterpreter.
3. **Nested entry.** If the active profile declares `nested_profiles`
   and the line matches one of their `prompt_pattern`s, PUSH the
   current profile onto the stack and switch active_profile to the
   child — same "check for an immediate state match on the same line"
   handling `_try_enter_profile` already does for top-level entry.

### Why the parent's state resets (not restores) on pop

The stack stores only the parent `CoachProfile`, not its
`CoachState`/stall counters. On pop, `active_state` is set to `None`
and stall counters reset to 0, regardless of what state the parent
was in before nesting.

This is the direct fix for the documented bug, not an accident of
simplicity. If the parent's exact prior state (`fired`, with its
`expected_next: sessions`) were restored unchanged, the operator would
return from a real, successful Meterpreter session straight back into
a stall countdown toward "have you listed your sessions yet?" — stale
advice, since they were LITERALLY just inside one. Resetting to `None`
means: no further stall narration fires until the operator does
something in the parent profile that matches a REAL recognized state
again (e.g. `search`, `use`, another `run`). That is exactly the
"blank slate, no false nagging" behavior the bug report asked for, and
it costs nothing extra to implement — it's the simpler of the two
options, not a compromise.

A future nested pair that genuinely needs to resume a parent's exact
prior state can extend `profile_stack`'s tuple shape then; nothing
here forecloses that, it's just not needed for this pair.

## The `METERPRETER_PROFILE` itself

Registered ONLY as `MSFCONSOLE_PROFILE.nested_profiles`, deliberately
NOT added to top-level `DEFAULT_PROFILES` — Meterpreter sessions are
only ever spawned from inside msfconsole in the workflows this coach
covers, so there's no real top-level "entered Meterpreter cold" case
to detect, and keeping it out of `DEFAULT_PROFILES` avoids any chance
of a stray "meterpreter >"-shaped string in unrelated output
misfiring a top-level profile switch.

- `prompt_pattern` / `states[0].recognize` reuse: real Meterpreter's
  prompt (`meterpreter > `) has no dynamic content (unlike
  msfconsole's module-context prompt), so — per the engine fix already
  applied for msfconsole/evil-winrm (see docs/COACH_OPEN_QUESTIONS.md's
  "recurring `recognize` pattern" fix) — it's now safe to reuse the
  live prompt directly as the `landed` state's `recognize`, since a
  same-state re-match no longer starves the stall counter.
- `exit_pattern` matches typed `background`/`exit`/`quit` at the
  Meterpreter prompt, OR Metasploit's own unprompted
  "Meterpreter session N closed" message (dropped/died connection) —
  belt-and-suspenders alongside the engine's generic parent-prompt
  fallback above.
- States: a small two-step checklist mirroring `RAW_SHELL_PROFILE`'s
  shape (`landed` -> confirm identity via `getuid`/`sysinfo` ->
  `identified` -> `ps`/`migrate`/`background`), not a full
  post-exploitation tutorial — deliberately scoped to "prove the
  nesting mechanism, with one real, useful checklist," matching this
  project's "narrow, specced" build discipline elsewhere.

**Caveat, same as the existing msfconsole/evil-winrm profiles:**
`msfconsole` is not installed on this machine (`which msfconsole` —
not found), so none of this was checked against a live pty paste.
Prompt/message text is taken from widely-documented, stable Metasploit
behavior (`meterpreter > ` prompt, `getuid`'s "Server username:"
output header, the "Meterpreter session N closed" disconnect message)
— treat as a starting point to correct against a real install the
same way the existing profiles already ask for.

## What this does NOT do

- No graph-shaped state machine inside a profile — states remain the
  existing shallow, ordered checklist shape. Nesting is handled
  entirely at the `CoachSession`/profile level, not inside
  `CoachState`.
- No keystroke injection, same hard rule as everything else in this
  subsystem.
- No second level of nesting is built or tested (Meterpreter spawning
  its own further nested tool) — the stack mechanism supports it
  structurally, but nothing in this pass exercises or claims to
  handle it.

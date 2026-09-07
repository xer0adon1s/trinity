# Coach subsystem — open questions

Ideas that showed up while building the msfconsole profile. None of
these were implemented. The engine dataclasses were left alone; Doc
reviews.

## msfconsole: checklist shape vs real workflow (found 2026-09-07)

The existing shallow checklist (`recognize` = "we are in this state",
first match wins, no backward edges) does not quite fit a few real
msfconsole shapes. Logged rather than redesigning `CoachState` /
`CoachSession`.

- **Module-context prompt cannot be a state `recognize`.** Spec
  wanted `msf6 exploit(...) >` as the richest "module selected"
  signal, and said we would not need to detect `use` itself.
  driver.rb reprints that prompt on every subsequent line (including
  the empty prompt after `set RHOSTS`). Under first-match-wins that
  would snap the session back from `options_set` / `fired` to
  `module_selected` after every command. The profile therefore
  recognizes `use <module>` (the one-shot command) instead. Using
  the prompt as a state signal would need edge-triggering or
  forward-only transitions in the engine.

- **Already-in-module at capture start.** Restored `ActiveModule`,
  `msfconsole -x "use ..."`, or joining a session mid-module means
  the first captured line is already `msf6 exploit(...) >` with no
  `use` in the stream. Profile entry still fires; `active_state`
  stays None until the next `use` / `search` / `set RHOSTS` /
  `run`. A stall at that empty-state prompt produces no nudge
  (engine returns None when `active_state is None`).

- **Meterpreter is a nested session.** A successful `run`/`exploit`
  often drops the operator into `meterpreter >` rather than leaving
  them at `msf6 >` to type `sessions`. The spec's `fired →
  expected_next: sessions` does not represent that fork. The coach
  stays in the msfconsole profile (exit_pattern does not match
  `meterpreter >`) and will eventually stall-nudge toward `sessions`
  while they are already inside the session. A nested profile or a
  graph-shaped state machine would be needed; both are engine
  changes.

- **`back` does not deselect.** `back` returns the prompt to
  `msf6 >` but matches no new state's `recognize` and is not an
  exit. Stall hints stay on whatever state was active (e.g. still
  talking about `set RHOSTS` at the top-level prompt).

- **Custom `Prompt` / `PromptChar`.** Operators can `setg Prompt`
  (`%T` timestamp, `%W` workspace, arbitrary text). We only match
  the default `msf` / `msf5` / `msf6` (+ module-context) form from
  driver.rb. Fancy Kali two-line OS prompts after exit are also
  unmatched; only `user@host:...$` / `#` is treated as "shell came
  back."

- **Other required options.** `TARGETURI`, `RPORT`, `SMBUSER`, etc.
  do not enter `options_set`. Only `set RHOSTS` / `set RHOST` /
  `setg RHOSTS` does — LHOST/LPORT/payload remain on-track
  `expected_next` from `module_selected` so setting a callback
  address alone does not pretend the module is ready to fire.

# Trinity's Voice — design draft v1

Status: DESIGN ONLY. Nothing in this document is built yet.

## The gap this closes

Right now Trinity's right pane (the recommendation feed in `trinity
watch`) is a list of commands and one-line "why" strings pulled from
the KB (`docs/METHODS_INDEX.md`, `src/trinity/coach.py`). That is
correct and fast, but it is not teaching -- it's a command list with
captions. Alexander's framing, verbatim: "most of the learning needs
to be PLAIN ENGLISH... like a textbook's worth." The match/suggest
engine already knows WHAT was found and WHAT to run next; nothing in
the program currently explains WHY, in the depth and voice of an
actual instructor, in a way the student can hold up against their own
scan and verify for themselves.

This is a genuine new subsystem, not a copy-fix. It sits downstream of
everything that already exists (match engine, Coach, suggest engine)
and never replaces or second-guesses their output -- it narrates it.

## Non-negotiable architectural rule

**The Voice explains findings. It never detects them.**

Detection (is this vsftpd 2.3.4, is this port open, is this a known
CVE) stays exactly where it is today: the local match/suggest engine,
deterministic, offline, instant, already trusted. The Voice is called
ONLY after a finding is already identified with full structured data
(service, version, CVE if known, port, the match engine's confidence
label) -- it receives that structured data as input and produces
PROSE as output. It cannot introduce a new "fact" the engine didn't
already establish; it can only explain, contextualize, and teach
around a fact that's already on the screen. This is the same
separation of concerns Assimilator/Show Me Mode's design already
established (diagnose locally, escalate to AI only for the narrow
thing local logic can't do) -- here the "thing local logic can't do"
is write a textbook paragraph, not identify a vulnerability.

Why this matters, concretely: it keeps the AI call cheap (no need to
re-derive anything, no risk of the AI inventing a wrong CVE), keeps
token spend on dialogue/teaching rather than "deep analysis" (per
Alexander's explicit ask), and keeps a hard trust boundary -- a
finding shown to the student is ALWAYS locally-verified fact; only the
narration around it is AI-generated and (per Trinity's existing
disclosure rules — see docs/SHOW_ME_MODE.md's AI-disclosure precedent)
labeled as such.

## The three things Alexander asked for, and how each maps to a design decision

### 1. Consistent voice, no wandering, no spoilers, personality

**Decision: a fixed prompt template per finding-type, not a free-form
"explain this" call.** Three or four templates covering the shapes
that actually recur (a named CVE/backdoor, a version-based
vulnerability class with no single CVE, a misconfiguration/weak
default, a technique/technique-class like path traversal or SSTI),
each with:
- A hard structural contract: 3-5 short paragraphs, defined order
  (what it is -> why it exists / the interesting story if there is
  one -> what it means for THIS box specifically -> what to watch for
  next time you see this shape). Same shape every time, so a student
  learns to read the RESPONSE format itself, not just the content --
  "oh, paragraph 3 is always the this-box-specific part."
- An explicit spoiler boundary: the template must never mention what
  happens AFTER the current milestone (no mentioning root if the
  student hasn't gotten a shell, no mentioning the actual privesc path
  while explaining a foothold vuln). This is the same rail Show Me
  Mode's design already had to solve for a different reason; reuse the
  milestone-gating logic rather than re-invent it.
- A voice directive that is DESCRIBED, never named: dry wit, quietly
  pattern-spotting, the tone of someone who's clearly seen this exact
  vulnerability class a thousand times and finds a bit of amusement in
  how often the same three mistakes recur -- confident, warm,
  occasionally a little knowing, never a cartoon, never breaks into
  jokes that undercut the teaching. (Deliberately not naming the
  cultural reference point in this doc or in any prompt text --
  Alexander's own instruction: it should be implied, never spelled
  out, and keeping it out of the prompt template entirely is the only
  way to guarantee it never leaks into a live response.)
- A finding-data injection contract: the template ALWAYS quotes back
  the specific data it's explaining (the exact banner string, the
  exact port, the exact version) inline in its own prose -- this is
  what makes the "verify against your own scan" workflow Alexander
  described actually work. If the response doesn't visibly reference
  the concrete finding, it reads as generic and can't be cross-checked
  against the student's own terminal.

### 2. When generation happens + the "Analyzing..." moment

**Decision: on-demand, lazily, the first time a finding is shown or
selected -- not pre-generated in batch, not blocking the dashboard.**
Rationale directly from Alexander's own framing: he wants the AI call
kept cheap and mostly-dialogue, and pre-generating a "textbook" for
every possible CVE/finding shape in the corpus is a much bigger,
separate, standing project (closer to the deferred community-KB-sync
vision than a v1 feature). Lazy-on-demand also means the first caching
win is free: two students hitting the same vsftpd 2.3.4 backdoor never
pay for two AI calls, since the second one hits the cache.

Concretely, reusing patterns already in the codebase rather than
inventing new ones:
- New table, same shape as `command_explanations`:
  `finding_explanations` keyed on a normalized signature of
  (service, product, version, cve_or_technique_id) so the SAME
  vulnerability across different boxes/students shares one cached
  explanation forever, the same way `command_explanations` already
  caches per-command.
- Call path: reuse `agent_harness.invoke_agent()` verbatim (bounded,
  one-shot, already detects the operator's own AI CLI in priority
  order) -- no new AI-invocation mechanism needed.
- UI: the right pane (or wherever the Voice's response renders) shows
  a real "Analyzing..." state with a visual indicator (a spinner, or a
  short animated dots line matching the existing TUI's dim/italic
  styling) for the duration of the bounded call, then replaces it with
  the response. This must run on a background worker exactly like
  Fix 6's DoctorScreen fix from this session (call_from_thread back to
  the UI, never block the event loop) -- same pattern, proven this
  session, reuse it rather than re-solve it.
- Failure path: if no AI CLI is detected, or the call fails/times out,
  fall back to the existing plain KB "why" string rather than leaving
  a blank pane or an error -- the Voice is additive, never a hard
  dependency for the program to function.

**Decision: the Voice speaks every time a finding is shown, not just
on request.** Alexander's explicit ask: "she should basically say
something EVERY TIME, like a professor would." This is a real product
decision (not a technical one) with a real cost implication --
confirm-before-build item, see Open Questions below.

### 3. Right-pane "what's happening" affordance for every command

**Decision: every command line in the recommendation feed gets a
lightweight "explain" trigger** (a keybind while a line is
focused/selected -- fits naturally as a Tools-menu-adjacent action
given the Tools/Advanced split just built this session), which invokes
the SAME Voice mechanism as findings, using the command's existing
`command_explanations` cache/generation path if it's a plain command,
or the new `finding_explanations` path if the line is finding-shaped.
This does not require two separate UIs -- it's one "ask the Voice"
affordance, routed to whichever cache/generation path matches what's
under the cursor.

## What this explicitly does NOT do (v1 scope boundary)

- Does not replace the match engine's confidence labels, the coach's
  ranking, or any existing deterministic logic. The Voice is a text
  renderer over already-established facts.
- Does not attempt to pre-build a "textbook" for the full known-CVE
  universe. That's a real, larger, separate future project (natural
  fit for the deferred community-KB-sync vision in
  `docs/TRINITY_2_0_VISION.md`) -- v1 is lazy generation + cache only.
- Does not touch Show Me Mode / Assimilator, which remain quarantined.
  The Voice is a pure narration layer with no execution capability at
  all -- it cannot run commands, propose commands to run, or touch the
  box in any way. This is a stricter boundary than Show Me Mode ever
  had, deliberately, since "explain this to me" is a fundamentally
  lower-trust-required feature than "act on this."
- Does not decide milestone/spoiler boundaries itself -- it consumes
  the existing milestone-gating logic (whatever currently prevents
  Coach from mentioning root before foothold) rather than
  re-implementing spoiler logic independently.

## Open questions for Alexander before this gets scoped into a real
## implementation plan

1. **"Every time" cost model.** If the Voice narrates every single
   finding by default (not on-request), that's an AI call per NEW
   finding-signature the student's scan surfaces (cached after the
   first time anyone anywhere sees that signature) -- likely a handful
   of calls per box, not per scan, given caching. Confirm that's the
   intended cost shape before this is scoped, since "every time" reads
   two ways: every time a finding is NEWLY discovered (cheap, cache
   absorbs repeats) vs. every time a finding is DISPLAYED/re-shown
   (would need its own dedup, since re-rendering a cached explanation
   is free but re-generating on every render would not be).
2. **Opt-out/toggle.** Should "Voice on every finding" be the default
   with an off-switch (for an experienced user who just wants the
   command list back), or default-off/on-request for v1 with
   "always-on" as a fast-follow once the cache is warm enough that
   most common boxes rarely trigger a live call at all?
3. **Which AI call model, precisely.** Reuse `agent_harness`'s
   existing "detect the operator's own CLI, one-shot, bounded" model
   (no API key needed, matches Trinity's local-first philosophy) --
   confirm this is preferred over introducing the (already-planned-
   for-2.0) API-key path early just for this feature.
4. **Pre-seeding.** Worth pre-generating explanations for the ~20-30
   most common findings in the existing coverage-sim corpus (vsftpd
   backdoor, EternalBlue, etc.) as a one-time batch job BEFORE v1
   ships, so the very first live box a student ever tries already has
   a warm cache and never shows "Analyzing..." for the classics? This
   would need the same review-before-merge discipline Assimilator's
   design already established for AI-generated content entering the
   shipped KB.

# Trinity's Voice — design draft v2 (post-review, build order flipped)

Status: PARTIAL. v1 (a hand-authored corpus + deterministic local
renderer, described below) is built: `src/trinity/voice.py`,
`src/trinity/voice_seed.py`, the `finding_explanations` table, and the
dashboard's feed integration. v2 (live AI generation, preserved below
as "Deferred: v2 design") remains DESIGN ONLY, intentionally not
started.

**Both reviews independently recommended the same fix: flip the build
order.** v1 ships an authored corpus (hand-written or agent-drafted
then human-reviewed, same pattern as `explain_seed/`'s 86 entries) with
a deterministic local renderer that substitutes the student's actual
finding data into the authored template at display time. Live AI
generation becomes v2, filling the long tail the corpus misses, gated
behind the same intake review discipline as every other AI-sourced
content path in Trinity, with the input-sanitization and output
validation rails both reviews specified.

This gets every real thing asked for, with none of the deferred risk:
consistent voice is solved by construction (one author, not five
different AI CLIs each with their own register); "the professor speaks
every time" costs nothing (no AI call, no "Analyzing..." latency);
spoiler safety is authored per-phase like the existing `nudge` field,
not a probabilistic prompt instruction; and the corpus is reviewed once
before shipping, not generated fresh (and untrusted) for every student.

The sections below are updated to describe the v1-as-built design.
Original v1 (live-generation-first) is preserved at the bottom of this
doc as "Deferred: v2 design" for when the authored corpus's long tail
actually needs filling.

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

**The Voice explains findings. It never detects them, and in v1 it
never calls an AI model live.**

Detection (is this vsftpd 2.3.4, is this port open) stays exactly
where it is today: the local match/suggest engine, deterministic,
offline, instant, already trusted. v1 of the Voice is a **hand-authored
corpus plus a deterministic local renderer** -- no live AI call at all.
This is a deliberate build-order flip from the original ask, made after
two independent reviews (`findings/voice_design_review_cursor.md`,
`findings/voice_design_review_claude.md`) found the live-generation
design had real, unresolved gaps: no spoiler gate exists anywhere in
the codebase to "reuse" (a prompt-text promise isn't a rail), the
proposed cache key doesn't exist in the schema (no CVE/technique-id
column anywhere; `kb_entries.id` is an unstable autoincrement, not a
cross-install key), and -- most seriously -- injecting live,
attacker-controlled banner text from the scanned box into an AI CLI
automatically, on every finding, with no human in the loop, is a
genuine prompt-injection surface, broader than Show Me Mode's (which
at least required per-invocation consent).

v1 gets everything actually asked for without any of that risk:
- **Consistent voice, solved by construction.** One author (a person,
  or an AI draft a person edits and approves before it ships), not
  five different AI CLIs each with their own register generating fresh
  prose per install.
- **"The professor speaks every time," free.** No AI call, no
  "Analyzing..." latency, no per-install cost -- the explanation is
  already written, the renderer just substitutes the student's actual
  finding data into it at display time.
- **Spoiler safety, authored not prompted.** Each entry is written
  phase-scoped from the start (never mentions a later phase), the same
  proven pattern as `hints.py`'s hand-authored `nudge` field, not a
  prompt instruction asking a model to be discreet.
- **"Verify against your own scan," actually reliable.** The
  renderer's substitution is guaranteed (real string formatting), not
  requested (an AI "please quote the banner back" instruction that
  might or might not happen).

Live AI generation is preserved below as "Deferred: v2 design" -- a
real future project to fill the long tail the authored corpus doesn't
cover, gated behind the same intake-review discipline as every other
AI-sourced content path in Trinity, with the input-sanitization and
output-validation rails both reviews specified. It is not needed for
v1 to deliver real value tonight.

## v1 architecture, as built

### Data model

New table `finding_explanations`, keyed on `kb_entries.title` (the
stable, human-authored, unique-by-seed-logic identifier -- NOT
`kb_entries.id`, which is an autoincrement that isn't stable across a
fresh install/re-seed):

```sql
CREATE TABLE IF NOT EXISTS finding_explanations (
    id INTEGER PRIMARY KEY,
    kb_title TEXT NOT NULL UNIQUE,     -- joins to kb_entries.title
    what_it_is TEXT NOT NULL,          -- paragraph 1
    why_it_happens TEXT NOT NULL,      -- paragraph 2 (the story, if there is one)
    what_to_watch_for TEXT NOT NULL,   -- paragraph 3 (generalizable lesson)
    source TEXT NOT NULL DEFAULT 'trinity_preseed',  -- matches db.py's
                                        -- existing source vocabulary
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
```

Deliberately NOT storing a "this box specifically" paragraph in the
authored text -- that part is assembled locally at render time from
the actual `Finding`/`KBMatch` object already on screen (the real
banner, the real port, the real IP), which is what makes the
verify-against-your-own-scan workflow actually reliable (guaranteed
substitution, not requested).

### Voice module (`src/trinity/voice.py`)

- `get_voice_text(conn, kb_title, finding) -> str | None`: looks up
  the authored entry by `kb_title`, and if found, renders all four
  parts (3 authored paragraphs + 1 locally-assembled instance
  paragraph) into one formatted block. Returns `None` on no entry (the
  caller falls back to the existing plain KB `summary`/`why` string --
  the Voice is additive, never a hard dependency).
- No network calls, no subprocess, no AI CLI invocation anywhere in
  v1's code path. Fully deterministic, fully unit-testable (per
  Claude Code CLI's review note: prose-generation rails need to be
  deterministic to be testable at all -- v1 skips the whole problem by
  not generating anything live).

### Seed corpus (`src/trinity/voice_seed.py`)

Mirrors `explain_seed/`'s proven pattern (86+ entries, human-reviewed,
merged via `combine.py`, seeded idempotently by unique key). v1 ships
entries for the small existing `kb/seed.py` corpus (6 entries as of
this writing, including the exact vsftpd 2.3.4 backdoor CVE-2011-2523
finding hit during tonight's live Lame test) -- growing this corpus
alongside `kb/seed.py` itself is the natural long-term maintenance
path, not a one-time batch job.

### UI: dashboard integration

`_render_result` (`tui/dashboard.py`) already iterates each finding's
top `KBMatch` to render the one-line feed entry. v1 adds: when a
finding's top match is `confirmed` or `likely` confidence (never
`best_guess` -- an unvetted searchsploit hit dressed up in confident
instructor prose would launder its own uncertainty) and a
`finding_explanations` entry exists for that KB title, render the
Voice's text as an expandable/inline block under that finding's feed
line, styled distinctly (dim italic header, e.g. "Trinity explains:")
from the plain match-line above it. No new AI-invocation UI is needed
in v1 (no "Analyzing..." state, since there's no live call) -- the
spinner from the original design is deferred to v2 along with the live
call it exists to cover.

### What v1 explicitly does NOT do

- Does not call any AI model, live, ever, in this pass.
- Does not attempt "every finding, every time" for findings outside
  the authored corpus -- an unmatched or uncovered finding just shows
  the existing plain KB line, same as today. No degraded/broken state,
  just no bonus narration yet.
- Does not touch Show Me Mode / Assimilator (still quarantined) or
  Agent Harness's live-invocation code path at all.
- Does not decide anything about milestone/spoiler gating that doesn't
  already hold for hand-authored content -- the author is responsible
  for not spoiling later phases, exactly like `hints.py`'s existing
  `nudge` authoring discipline.

## Deferred: v2 design (live AI generation, original ask)

Preserved verbatim below for when the authored corpus's long tail
actually needs filling. Do not build this until v1 has shipped, the
corpus has grown past what hand-authoring alone comfortably covers,
and the rails below are actually designed (not just named) -- see both
review documents for the specific gaps that must be closed first:
input sanitization on any live finding data reaching a model (`detail`
free text is attacker-controlled), an output validator that rejects
responses failing to quote back the injected structured fields, a real
deterministic spoiler filter (input-side phase filtering plus an
output-side forbidden-vocabulary post-filter), a hard per-call timeout
well under the general-purpose 120s default, a one-in-flight-call
budget so a burst of findings from one scan can't fire N sequential
cold-start CLI invocations, and routing all live-generated content
through `intake` for review before it ever becomes durable/cached --
never a write-through cache of unreviewed model output.

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

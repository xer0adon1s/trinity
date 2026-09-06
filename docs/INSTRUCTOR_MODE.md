# Instructor Mode — Design

Status: BUILT. The coach ranking (`coach.py`), graduated hint ladder
(`hints.py`), and error-diagnosis cache (`errors.py`/`errors_seed.py`)
described below are implemented and tested — `trinity next`, `trinity
hint`, `trinity error`, `trinity cache-error` all exist, and the
wizard hands off to a real recommendation at the end of onboarding.
This document remains the reference for why things are shaped the way
they are; treat "New command: ..." sections below as descriptions of
what's live, not proposals.

## The problem

Today, once the wizard hands off a box, the operator is on their own
with a set of CLI commands (`explain`, `suggest`, `watch`, `report`).
There's no continuous thread connecting "here's what we found" to
"here's what to actually do about it and why" to "here's what to do
when it doesn't work." Educational mode's entire promise — hold their
hand through the whole thing — currently ends the moment the wizard
exits.

Instructor Mode is that missing thread: a persistent "coach" layer that
sits on top of everything already built (suggestion engine, ELI5 cache,
timeline, KB matching) and turns them into one continuous conversation,
rather than a toolbox the operator has to know how to use.

## Core principle: WHAT → WHY → HOW, every time

Every piece of guidance Instructor Mode gives follows this shape,
because it's the actual thing that separates "learning" from
"copy-pasting a command":

- **WHAT** is going on (a finding, a match, a blocked step) — already
  captured by the existing match engine and timeline.
- **WHY** this path, and why now, not some other path — this is the
  genuinely new piece. Right now the suggestion engine emits a flat
  list of equally-weighted next commands; Instructor Mode picks one,
  states the reasoning (phase order, severity, what's already been
  ruled out), and explains why the others are secondary for now.
- **HOW** to actually do it — the exact command, already available via
  `explain`.

Professional mode keeps the same underlying data and the same command
recommendations, but skips the WHY narration and the hint ladder below
— it's the same engine, quieter output. Mode is still a lens over one
timeline, per DESIGN.md's existing principle; nothing about Instructor
Mode changes that.

## New concept 1: the "coach" recommendation

Today: `suggest_next_commands()` returns a flat list, all
equally-weighted, and the operator has to decide what to actually run
first. Instructor Mode adds a ranking step on top:

1. Phase order (recon → enum → foothold → privesc → post) — earlier
   phases are recommended before later ones, even if a later-phase
   suggestion technically exists (e.g. don't lead with a privesc
   command suggestion if enum on an open port hasn't happened yet).
2. Severity, per-suggestion (critical/high findings surface before
   low/info ones, within the same phase) — ranked by looking up the
   specific finding each suggestion is tied to, not one severity
   value applied to every suggestion on the box equally.
3. Recency, as the tiebreaker (the most recently generated suggestion
   wins over an older one sitting unactioned, within the same phase
   and severity bucket).

New command: `trinity next --box <name>` — asks "what should I do
right now," returns exactly one recommended command with its WHY, and
lists the rest as "also worth trying" underneath. This becomes the
single most-used command in the educational flow — the one thing a
beginner types over and over instead of having to remember the whole
command surface.

This is a pure-rules ranking layer (like the suggestion engine itself)
— no AI involved in deciding what to recommend first.

## New concept 2: graduated hints

Currently `explain` is all-or-nothing: full ELI5 explanation or
nothing. Instructor Mode adds a hint ladder for *technique* questions
(not command-syntax questions, which `explain` already covers well):

- **Level 1 (nudge):** Socratic, no answer given — "You've found
  something unusual on port X. What's different about it compared to
  the other services?"
- **Level 2 (stronger nudge):** points at the specific area without
  naming the tool/technique — uses a separate `nudge` field written
  per suggestion rule specifically for this purpose (never the full
  `rationale`, which routinely names the tool and would leak the
  answer one level early).
- **Level 3 (full answer):** names the technique/command directly,
  same as today's `explain`.

New command: `trinity hint --box <name>` — starts at level 1;
running it again on the *same* unresolved recommendation escalates to
level 2, then level 3. Resets per new finding/suggestion, so it's not
a one-time-per-box ratchet — every new stuck point starts back at a
nudge. This directly serves "keep learners from feeling overwhelmed":
the first response to being stuck is never "here's the answer," it's
an invitation to look harder, exactly like a good TA would do.

Data model addition: a small `hint_state` table (box_id,
suggestion_id, current_level) — tiny, no schema risk to anything
existing.

## New concept 3: error diagnosis that gets smarter over time

This is the piece that makes AI escalation genuinely rare over time,
not just at explain-a-command granularity but at "I ran the right
command and it still didn't work" granularity — the single most common
place a beginner gets stuck and currently has nowhere to turn inside
Trinity at all.

Flow:
1. `trinity error "<error text or description>" --box <name>` — the
   operator pastes whatever went wrong (a stack trace, "the exploit
   didn't work," a connection refused message, whatever).
2. Trinity checks a new local `error_patterns` KB (FTS5-searchable,
   same mechanism as the existing `kb_entries` table) for a fuzzy match
   against known error text.
3. **Hit:** instant, free, local — shows the known cause and fix, same
   trust/sourcing model as `command_explanations` (`source` field:
   `trinity_preseed`, `user_curated`, `ai_escalation`).
4. **Miss:** builds an escalation prompt (same copy-paste pattern as
   `explain.py`'s existing flow) — the operator brings it to their AI
   assistant, gets a diagnosis, and pastes the *confirmed-working* fix
   back in via `trinity cache-error "<error text>" "<fix>"`. That
   pattern is now permanently free for every future box, for this
   operator and (via the opt-in sharing bundle already built) every
   Trinity user who opts in.

This is the same "pay the AI cost once, centrally, never again" shape
as the ELI5 explanation cache — just applied one level up, at "why
didn't this work" instead of "what does this command do."

Data model addition: `error_patterns` table (id, error_text, cause,
fix, source, created_at) + its own FTS5 index, structurally identical
to `kb_entries`/`kb_fts`. Also feeds the opt-in `sharing.py` export
path already built — `ai_escalation`-sourced error fixes become
shareable/PR-able the same way explanation cache entries are.

## New concept 4: tool-availability checks (built)

A gap identified after the original three concepts shipped: the coach
could recommend a command (`gobuster dir -u ...`) without knowing
whether `gobuster` was actually installed on the operator's machine.
If not, the operator would just hit `command not found` in their own
terminal with no path back into Trinity for that specific problem.

Fix, built into the existing pieces rather than as a new subsystem:

- `suggest/engine.py`'s `Suggestion` model gained a `required_tool`
  field (e.g. `"gobuster"`), set per rule.
- A new `tools.py` module is a small registry (same shape as
  `platforms.yaml`) mapping tool name -> real availability check
  (`shutil.which`) + per-platform install one-liners (apt/pacman/brew)
  + a fallback URL/instructions when no clean package exists.
- `coach.py`'s `get_recommendation()` checks the top suggestion's
  `required_tool` against the registry. If missing, the recommendation
  still surfaces (never hidden), but carries `tool_missing=True` +
  `install_guidance` instead of jumping straight to command output.
- Critically, no new state was needed for "circle back to where we
  left off": because the coach always re-reads the same persisted,
  un-accepted `suggestions` row, the operator installing the tool and
  running `trinity next` again picks the exact same recommendation
  back up automatically the moment `shutil.which` finds it — verified
  live against a real missing tool (`enum4linux-ng`, genuinely absent
  on the dev machine) and a real re-check after it became available.
- Consistent with "I do / we do": Trinity tells the operator the exact
  install command for their platform, but never runs it — installing
  a tool is the operator's own action, in their own terminal, same as
  running a scan.

## What this does NOT change

- No orchestration — Trinity still never runs a command for the
  operator. `trinity next` recommends; the operator still types it
  themselves in their own pane, per the "I do / we do" philosophy.
- No new AI calls Trinity makes on its own — every AI touchpoint here
  is the same copy-paste escalation pattern already built, just applied
  to a new category (errors) and wrapped in more instructional framing
  around when/why to reach for it.
- Mode remains a lens, not a fork — professional mode gets the exact
  same `next`/`hint`/`error` commands, just with the narration stripped
  to the essential facts (no Socratic nudging, no "why" paragraph,
  straight to the recommended command and the fix).

## Build order (once approved)

1. `hint_state` table + coach ranking logic on top of the existing
   suggestion engine (`trinity next`) — smallest, most reused piece.
2. `trinity hint` graduated ladder.
3. `error_patterns` table + FTS5 index + `trinity error`/
   `trinity cache-error` commands.
4. Wire `trinity next` as the thing the wizard hands off to at the end
   of `prompt_new_project`/`prompt_resume_or_new` — closing the gap
   between "wizard exits" and "operator has no idea what to type next"
   that prompted this whole design.

Each piece is independently testable and shippable — no need to build
all three before any of them are useful.

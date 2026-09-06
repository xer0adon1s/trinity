# Rabbit Hole Detection — Design

Status: DESIGN ONLY. Nothing in this document is built yet.

## Why this deserves its own design (not just a roadmap bullet)

Recognizing you're in a rabbit hole — and getting yourself out of one —
is one of the actual core skills of offensive security, not a nice-to-
have. The HTB/THM community's own words for it, pulled directly from
research into real beginner threads: people burn 6+ hours on a single
wrong port without noticing, people with security master's degrees
still get stuck for hours on "easy" boxes, and the single most common
piece of advice given back to strugglers is "learn to recognize when
you're going down the wrong path." Trinity already has almost all the
raw data needed to help with this (the timeline), and it's a
near-perfect fit for the "prevent burnout" pillar of the whole project
— this is worth building well, not bolted on.

## What "a rabbit hole" actually looks like in Trinity's data

A rabbit hole isn't one specific bad state — it's a pattern over time.
Candidate signals, all derivable from the existing `timeline` table
with zero new instrumentation required:

1. **Stalled on the same recommendation.** The coach's top
   recommendation (`coach.get_recommendation()`) hasn't changed across
   multiple `trinity next`/`trinity hint` calls, and significant real
   time has passed since the last NEW finding/match was logged.
2. **Hint ladder maxed out, repeatedly, on unrelated things.** Hitting
   level 3 (full answer) on several different suggestions in a row
   without any of them leading to a new finding afterward — a sign the
   operator is consuming answers without them landing/working.
3. **A single phase or port dominating timeline activity.** E.g. 90%
   of recent timeline events reference the same port/service while
   other open ports/findings sit completely untouched — the classic
   "convinced this ONE port is the answer" pattern named explicitly in
   the HTB forum research (the "AHA!!! moment... and it's a trolling
   password" pattern).
4. **Elapsed wall-clock time since the box's last genuinely NEW
   finding**, independent of command count — someone can run the same
   fruitless command 40 times in 20 minutes; time-since-progress is a
   more honest signal than command count alone.

None of these signals require new schema — they're all queries over
`timeline`/`suggestions`/`hint_state` as they already exist. This
should be a read-only analysis layer, same shape as `coach.py`.

## What Trinity does when it detects one (this is the hard, important part)

The goal is NOT to just say "you're in a rabbit hole, stop." That's
unhelpful and slightly demoralizing on its own. The response needs to
teach the *meta-skill* of recognizing and escaping rabbit holes, not
just interrupt the person:

1. **Name it, gently, with the pattern.** "You've spent a while on
   port X without a new lead — that's a very normal rabbit-hole shape,
   not a sign you're doing something wrong."
2. **Reframe the sunk cost.** Borrowing directly from the actual
   community wisdom found in research for this: time spent going deep
   on something that didn't pan out is not wasted — it's exactly how
   the "mental toolbox" that experienced people talk about gets built.
   Trinity should say this outright, not just imply it.
3. **Offer a concrete alternative path**, not just "try something
   else" — pull an actual unexplored suggestion from the persisted
   `suggestions` table that hasn't been touched yet ("port Y is still
   completely unexplored — want to look at that instead for a bit?").
4. **Never force a redirect.** Purely advisory — if the operator wants
   to keep pushing on the same thing, that's a legitimate choice
   (sometimes the "rabbit hole" IS the actual path, just a hard one).
   Trinity flags, never blocks or nags repeatedly in the same
   conversation.

## Relationship to already-built/designed pieces

- Sits logically alongside `coach.py` (`trinity next`) and
  `hints.py` — likely surfaces as a note attached to `trinity next`'s
  output ("by the way, you've been here a while...") rather than a
  wholly separate command, so it's seen naturally rather than needing
  to be remembered/invoked.
- Directly feeds the Frustration Checkpoint idea (see
  FEATURES_BACKLOG.md) — rabbit-hole detection is the trigger
  condition, frustration checkpoint is one possible response shown
  when detected repeatedly.
- Should log its own nudges to the timeline (event_type: 'nudge' or
  similar) so a professional-mode report could honestly reflect "spent
  significant time on X before pivoting to Y" as a real part of the
  narrative — this is genuinely useful pentest-report content, not
  just an educational-mode nicety.

## Open design questions to resolve before building

- What's the right time threshold for "stalled"? Likely needs to be
  configurable/adaptive rather than a hardcoded number — a CTF sprint
  session and a slow weekend-long HTB session have very different
  "normal" paces.
- Should this ever look across BOXES (e.g. "you tend to rabbit-hole
  on SMB specifically, across multiple boxes") — that's a much more
  powerful, personalized insight than per-box detection alone, but is
  a bigger build (cross-box pattern analysis) than the per-box version
  above. Worth sequencing per-box first, cross-box as a real v2.

## Build order (once approved)

1. Read-only detection layer (`rabbit_hole.py` or similar) — pure
   query logic over existing tables, fully testable without any new
   schema.
2. Wire the "gently named + reframed + concrete alternative" nudge
   into `trinity next`'s output.
3. Timeline logging of nudges shown, so reports can reference them
   honestly.
4. (v2, later) Cross-box pattern analysis — "you tend to get stuck on
   X" as a personalized insight, once enough boxes exist in one
   operator's history for it to be meaningful.

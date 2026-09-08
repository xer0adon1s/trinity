# Show Me Mode — Design (v2, post-review)

Status: QUARANTINED. See docs/SHOW_ME_MODE_QUARANTINE.md. This
supersedes the v1 draft reviewed by Cursor and Claude Code CLI (see
`findings/design_review_cursor.md` and `findings/design_review_claude.md`
in the `design-review-cursor`/`design-review-claude` worktrees/branches)
— both reviews found real, code-verified problems in v1. This version
also reflects Alexander's own architectural correction (own-session
execution, not injection into the student's pane) and two explicit
philosophy calls (always-available, no hardcoded target allowlist).
See "What changed from v1" at the bottom for a full changelog against
the reviews.

## 1. Where this came from, stated honestly

The CEO (Alexander) asked for a feature where, at any point in a box,
the AI could silently command-inject to solve the next step in the
BACKGROUND, hidden from the student, then feed the result back into
Trinity's coaching so the student appears to have made the progress
themselves. Doc (this project's lead) pushed back hard on the HIDDEN
half specifically — not the underlying need. This document is the
counter-proposal that was accepted: same underlying goal (nothing
should ever be a permanent dead end, even genuine capability gaps),
delivered as a fully disclosed, always-available, per-invocation
feature instead of a silent one, with the AI acting in its own
execution surface rather than the student's.

**Show Me Mode IS Assimilator, triggered live.** Per Alexander's
explicit clarification: `docs/ASSIMILATOR_PROJECT.md` describes one
diagnose-hypothesize-verify-land engine with two triggers — an
offline/batch trigger (Doc sweeping the 122-box Coverage Sim corpus)
and this live/on-demand trigger (a student invoking `trinity
show-me` against one real box). Both are true at once; neither
replaces the other. "Solve the problem, assimilate the solution and
the data that goes with it" is literally what this command does — it
is not a separate sibling system that happens to share plumbing with
Assimilator, it is Assimilator's core loop running against a live
target instead of a fixture. This document specifies the parts unique
to the LIVE trigger (execution session, disclosure, milestone/safety
scoping, authorization); `docs/ASSIMILATOR_PROJECT.md` §2 and §4
specify the loop itself, shared by both triggers.

**Underlying, legitimate need this solves:** Coverage Sim confirms
some real retired boxes require techniques (BloodHound-style AD path
analysis, multi-step RBCD chains, live credential-chaining) that
Trinity's static match/suggest architecture genuinely cannot walk a
student through today, and may never fully cover no matter how much
KB content Assimilator's offline trigger adds (see
`docs/ASSIMILATOR_PROJECT.md` §8). Today those boxes are just dead
ends once Instructor Mode's hint ladder and the Methods Index are
exhausted. Show Me Mode is the escape hatch for that specific, narrow
case — and every successful invocation feeds the same leverage ledger
(`docs/ASSIMILATOR_PROJECT.md` §7) as an offline fix would, so the
population of boxes needing it should shrink over time (§8 below).

## 2. What it is

An opt-in, fully disclosed, always-available, per-step feature. When
invoked, Trinity's agent (the operator's own agent CLI — same
detection/invocation mechanism as Agent Harness, no Trinity-held API
key, no in-app chat pane) attempts the SINGLE next step live, **in its
own separate execution session against the target — never the
student's own terminal.** Once the agent confirms a working approach,
it hands the student the exact command sequence to run THEMSELVES, in
their own window. Nothing counts as the student's own progress, and
nothing is logged to the student's own timeline/report as their own
work, until the student actually runs it.

This is "watch a worked example, then do it yourself" — closer to a
textbook worked example than to an autograder solving the homework for
you.

## 3. Availability — always accessible, deliberately not gated behind a stuck-detector

**v1 gated this behind Rabbit Hole Detection's stuck signal. This
version does not, per Alexander's explicit call, and per a real bug
the reviews found in that gate anyway** (v1's proposed trigger,
described narratively as "5+ commands with no new finding, hint ladder
maxed," did not match what `rabbit_hole.py` actually implements — a
disjunction of three independent signals, one of which can be
satisfied with roughly six `trinity hint` calls in under a minute, no
real commands run. A gate that's that cheap to trip isn't a "genuine
last resort" gate at all — see `findings/design_review_claude.md` §B1
for the full trace against the code).

Alexander's reasoning for dropping the gate entirely, verbatim:
"its break glass in philosophy, but always accessible in a tool. We're
trusting people to use this the right way. if they were going to
cheat they would just use AI to solve everything. thats my thinking."
A stuck-detection gate doesn't stop a determined cheater — they'd
bypass Trinity and ask their own AI directly — it only adds friction
for the legitimate use case (genuine capability gaps) this feature
exists to serve.

**What this means concretely:** `trinity show-me` is a normal,
documented command, always runnable on any box with a confirmed
target, no rabbit-hole/hint-ladder/Methods-Index precondition. The
"break glass" framing lives in the disclosure UX (§4) and the report
tagging (§6), not in an access gate — every use is visible and
permanently recorded, which is the actual deterrent against casual
overuse, not an artificial unlock ritual.

## 4. Authorization — attestation, not a hardcoded target allowlist

**v1 proposed a software-enforced "is this box actually a retired
practice target" allowlist. Rejected outright, per Alexander's
explicit call**, not merely descoped:

"we're trusting that people are using our terms not hard coding a
preventitive. just like every other cybersec tool. If they agree to
our terms and conditions and whatever the legal checkboxes is, that
needs to be good enough."

This matches how every comparable offensive-security tool actually
works — Metasploit, Burp Suite, Cobalt Strike, nmap. None of them
maintain a hardcoded "targets you're allowed to attack" list; all of
them rely on the operator's own authorization and agreement to terms
of use. Building a hardcoded allowlist here would hold Trinity to a
stricter standard than the tools it teaches about, while also being
mechanically weak (v1's proposed platform-based version was already
shown to be defeatable — `platforms.yaml` is user-extensible by
design, and boxes can be created outside the wizard's confirmation
flow entirely — see `findings/design_review_claude.md` §B3 #3).

**What replaces it:** a one-time authorization attestation, same legal
shape as any pentest tool's terms-of-use acknowledgment — shown once
(not per-invocation, not in the first-run wizard per Hole F), logged,
and required before `show-me` unlocks at all. Wording draft:

```
Show Me Mode lets your agent CLI attempt live steps against targets
you use Trinity against. This is a real capability with real risk —
only use it against systems you are authorized to test (retired
practice boxes, your own lab, or engagements you're contracted for).
You are responsible for your own authorization. Trinity does not
verify targets.

[ ] I understand and agree.
```

Reuse `engagement_meta.authorization_ref` (already exists,
`src/trinity/db.py` — "e.g. HTB/THM platform + username, or a signed
engagement letter ref," already rendered in the professional report)
as the durable record of what the operator claimed authorization
against, rather than inventing a new field.

## 5. Execution architecture — own session, never the student's pane

This is the load-bearing architectural correction from v1, made by
Alexander directly and independently confirmed as necessary by both
reviews (which found the v1 claim of reusing Shoulder Mode's pty for
this purpose to be flatly wrong — `shoulder.py`'s own docstring states
it "only ever reads, never writes to or filters the pty," and
`agent_harness.py`'s `invoke_agent` is a buffered, non-streaming
`subprocess.run` that cannot host a live interactive session anyway).

**Trinity's agent runs in its OWN execution session, spawned by
Trinity for this purpose, completely separate from the student's own
terminal/Shoulder Mode session.** Concretely:

- A new module (name TBD, e.g. `show_me.py`) owns a real subprocess/pty
  the AGENT drives — NOT `shoulder.py`, which stays exactly as
  documented (read-only, never touched by this feature). This is a
  genuinely new execution surface, not a repurposed existing one, and
  should be reviewed as such — nothing in the existing trust model
  (Shoulder Mode watches; Agent Harness asks one bounded question)
  covers "an agent executes commands live."
- Trinity narrates progress from THIS session's output as it happens
  (same coaching voice as Instructor Mode), visible to the student in
  real time, but the student is watching, not participating.
- On success (the agent reaches the declared milestone — see §6), the
  session prints/hands off the EXACT working command sequence.
- The student then runs that sequence themselves, in their own
  terminal/Shoulder-Mode pane, same as running any other suggested
  command. THAT is what gets logged to the timeline as real progress —
  Trinity's own scratch session produced a verified recipe, nothing
  more.

This resolves several review findings at once:
- No trust-boundary confusion from repurposing a read-only module.
- Report integrity mostly falls out for free (§6) — nothing enters the
  student's own history until they actually type it.
- The agent's execution surface can carry its own safety policy (§7)
  without touching the student's shell/environment/credentials at all.

## 6. Milestone scope and safety on the agent's own session

Even though this session is Trinity's own (not the student's), it
still needs bounds — not because we don't trust the student, but
because we don't want an autonomous agent breaking a shared practice
target the student then can't continue on themselves.

- **One milestone per invocation.** Declared before running: exactly
  one of `foothold`, `privesc_to_user`, `privesc_to_root` (not "solve
  the rest of the box"). Terminates on first match against the
  declared target state.
- **Hard stops (any fires -> kill the session):** declared milestone
  reached; a wall-clock cap; a command-count cap; an argv policy
  violation (below); explicit student abort.
- **Destructive-command denylist enforced by the runner, not by
  prompting the agent to be careful:** no `rm`/`mkfs`/`dd`, no service
  stop/restart, no `shutdown`/`iptables`, no writes outside a scratch
  path, no credential/password changes on the target. The agent
  proposes, the runner decides whether to actually execute — same
  "propose vs. execute" split recommended for Assimilator's sandbox
  lane (`docs/ASSIMILATOR_PROJECT.md` §5).
- **Target pin:** every command's host argument must equal the box's
  recorded target; refuse anything else.
- No snapshot/revert available here (unlike Assimilator's sandbox,
  this runs against a platform-hosted box Trinity doesn't control) —
  the mitigation is prevention (the denylist above) plus honest
  disclosure that a failed attempt may require a platform-side reset.

## 7. Disclosure and report integrity (unchanged in spirit from v1, tightened)

Per-invocation disclosure, every time, non-skippable, no `--yes` flag,
no env-var bypass, refuses if stdin isn't a real TTY:

```
$ trinity show-me

  Show Me Mode: your agent CLI (claude) will attempt ONE step live,
  in ITS OWN session, against this target — not your terminal. You'll
  watch it work. If it succeeds, you'll get the exact recipe to run
  yourself; that's what counts as your own progress, not this session.

  Continue? [y/N]
```

**Report tagging must be structural, not a suppressible flag** — this
was the sharpest finding from Claude Code CLI's review (§B4): two
existing report templates currently print unconditional claims
("Trinity... does not execute exploits," "never touched an AI model")
that Show Me Mode makes literally false the moment it's used. Fix
required regardless of anything else in this doc:
- A `show_me_runs` table (box, milestone, timestamp, agent used,
  outcome) as the authoritative record, independent of whether any
  single timeline row survives.
- `gather_report_data()` populates an `ai_assisted_steps` list from
  it; both report renderers get a mandatory disclosure block when
  non-empty (`professional.py`'s Limitations section rewritten to be
  conditionally true; `educational.py`'s closing paragraph rewritten
  the same way) — no code path may omit it when the list is non-empty.
- Since progress only enters the student's timeline once THEY run the
  recipe (§5), most individual Finding/loot rows won't need per-row
  tagging the way v1 assumed — but the `show_me_runs` table itself is
  still the mandatory, always-rendered disclosure surface.

## 8. Knowledge feedback loop (unchanged from v1)

After a Show Me Mode step succeeds, the working recipe should feed
Update Framework's review-intake queue (tagged with its own source,
not silently merged into `agent_harness`'s existing source label — see
`findings/design_review_claude.md` §A4.4/§C3 on why source-flattening
on approval is already a live bug worth fixing regardless of this
feature) so the NEXT student on the same box gets normal Instructor
Mode coaching instead of needing Show Me Mode at all. Every use is
evidence of a KB gap; the goal is for the population of boxes needing
this feature to shrink over time. This ties directly into Assimilator
and the community KB sync idea (`docs/TRINITY_2_0_VISION.md` §3) as
the third producer feeding the same review queue — queue capacity
needs a shared answer across all three, not a per-feature one.

## 9. Open questions still unresolved (real, need answers before build)

1. **Anthropic usage-policy / dual-use compliance.** Unchanged from
   v1 — needs a written answer, not an assumption, before broad
   ship. Note this applies per-agent-CLI (Claude, Codex, Gemini,
   Cursor are all valid targets via Agent Harness's existing
   detection), not just one vendor.
2. **HTB/THM's own ToS on automated/agentic attack tooling** against
   their machines, retired or not — a second, separate policy surface
   from #1 that v1 didn't ask about at all.
3. **Cost/rate limiting** on the agent's own session — this is a
   multi-turn, tool-using, potentially expensive invocation, not the
   bounded one-shot Agent Harness call it shares plumbing with. Needs
   its own disclosed budget (turns/wall-clock), separate from Agent
   Harness's existing (also currently unresolved) cost guardrails.

## What changed from v1 (changelog against the two design reviews)

- Dropped the Rabbit Hole Detection stuck-gate entirely (was buggy as
  specified anyway — see `findings/design_review_claude.md` §B1 for
  the code-level trace of why it was a 6-keystroke bypass).
- Dropped the software-enforced target allowlist entirely, replaced
  with authorization attestation (§4) — Alexander's explicit call,
  independent of but consistent with both reviews finding the v1
  allowlist mechanically broken.
- Replaced the false "reuse Shoulder Mode's pty" claim with a real,
  separate execution surface owned by Trinity's agent (§5) —
  Alexander's "her own window" correction, which also directly
  resolves the reviews' B2.1/B2.2 findings.
- Report integrity section rewritten to require structural,
  non-suppressible disclosure (§7) instead of a per-event tag, per
  Claude Code CLI's §B4 findings about the two report templates that
  would otherwise print false claims.
- Left cost/rate-limiting and the two policy-compliance questions
  explicitly open (§9) rather than guessing at answers.

# Show Me Mode — Design (DRAFT for Cursor/Claude Code CLI review)

Status: DESIGN ONLY. Nothing in this document is built yet.

## 1. Where this came from, stated honestly

The CEO (Alexander) asked for a feature where, at any point in a box,
the AI could silently command-inject to solve the next step in the
BACKGROUND, hidden from the student, then feed the result back into
Trinity's coaching so the student appears to have made the progress
themselves. Doc (this project's lead) pushed back hard on the HIDDEN
half specifically — not the underlying need. This document is the
counter-proposal that was accepted in the same conversation: same
underlying goal (nothing should ever be a permanent dead end, even
genuine capability gaps), delivered as a fully disclosed, opt-in,
per-invocation feature instead of a silent one. Recorded here in full
so a future session doesn't "helpfully" quietly reintroduce the hidden
version — see §6.

**Underlying, legitimate need this solves:** Coverage Sim confirms
some real retired boxes require techniques (BloodHound-style AD path
analysis, multi-step RBCD chains, live credential-chaining) that
Trinity's static match/suggest architecture genuinely cannot walk a
student through today, and may never fully cover no matter how much
KB content Assimilator adds (see `docs/ASSIMILATOR_PROJECT.md` §8).
Today those boxes are just dead ends once Instructor Mode's hint
ladder and the Methods Index are exhausted. Show Me Mode is the
escape hatch for that specific, narrow case.

## 2. What it is

An opt-in, fully disclosed, per-step feature: when a student is
genuinely and verifiably stuck (§3), Trinity can offer to have the
operator's OWN agent CLI (same detection/invocation mechanism as
Agent Harness — no new integration, no Trinity-held API key) attempt
the SINGLE next step live, in the SAME terminal pane the student is
already working in, with full real-time visible output — never
hidden, never silent, never spanning more than one step without
fresh consent.

## 3. Trigger conditions (all must hold — this is not a casual button)

1. Rabbit Hole Detection's real stuck signal has already fired (5+
   commands with no new finding, hint ladder maxed) — see
   `docs/RABBIT_HOLE_DETECTION.md`. Not available before this point;
   Show Me Mode is downstream of every existing teaching mechanism,
   not a shortcut around them.
2. Methods Index (citation-index escape hatch) has already been
   offered and either has no matching entry or the student has read it
   and remains stuck.
3. The box is confirmed retired/practice (same allowlist mechanism as
   Coverage Sim / Assimilator — HTB/THM/VulnHub retired only). Show Me
   Mode refuses to activate on anything Trinity cannot confirm is a
   practice target. This check happens in software, not just as
   instruction text — see §7 open question 3.
4. The student explicitly invokes it (a real command, e.g. `trinity
   show-me`, never auto-offered as a default action in a menu the
   student might accidentally select) AND confirms a clear disclosure
   prompt EVERY time (§4), not just once per session.

## 4. UX — the disclosure is the load-bearing part of this design

On invocation:

```
$ trinity show-me

  Show Me Mode: your agent CLI (claude) will attempt ONE live step
  against this target now, in this terminal, and you will watch it
  happen in real time. This is not something you did — the report
  will mark it as AI-assisted, not student-performed. Trinity will
  then explain what happened and why, same as any other coaching.

  Continue? [y/N]
```

Once confirmed:
- The agent CLI runs in the SAME pane (reuses Shoulder Mode's pty
  plumbing, `src/trinity/shoulder.py` — the student is already inside
  a Shoulder Mode session, so this is literally the same recording/
  narration pipe, now with the agent's own commands appearing in the
  live stream instead of the student's).
- Every command the agent runs prints to the visible terminal as it
  runs — no summarization-after-the-fact, no "trust me, it's done."
  Same principle as never letting the coach silently act — the
  student sees the actual argv, actual output, in order.
- Coach narrates AS the agent works, same voice/cadence as Instructor
  Mode narrating the student's own commands ("it's trying an
  anonymous LDAP bind here because port 389 was open and unauth'd —
  watch what comes back").
- Hard cap: ONE milestone step (foothold, OR privesc-to-user, OR
  privesc-to-root — never "solve the whole box" in one invocation).
  After the step lands, the agent stops, hands control back, and a
  fresh `trinity show-me` + fresh disclosure is required for the next
  step if still stuck there too.
- Session/report tagging: every finding and milestone produced during
  a Show Me Mode invocation is flagged `source: "show_me_ai"` in the
  timeline (parallel to Loot's `discovered_at` pattern) — permanently
  distinguishable from student-performed work in `report/data.py`'s
  `gather_report_data()`. Professional-mode reports render this
  explicitly ("Step N was AI-assisted via Show Me Mode, not performed
  by the operator") — this is a hard requirement, not a nice-to-have,
  because a report that doesn't disclose this is a report that lies
  about what was performed and by whom.

## 5. Knowledge feedback loop (the tie back to Assimilator)

After a Show Me Mode step succeeds, Trinity should never need to burn
another live AI call solving the identical step for the next student.
Concretely:
1. Log the exact command sequence + resulting Finding to a queue.
2. Check whether Trinity's local KB already covers this (if
   Assimilator or an earlier Agent Harness cache entry already has it,
   this run should have ideally not needed Show Me Mode at all —
   log that as a signal that something upstream should have caught
   it).
3. If genuinely new, route it into Update Framework's review-intake
   queue exactly like any Agent Harness cache entry, tagged with its
   source box for citation. Once reviewed and landed, this technique
   becomes an ordinary KB/suggest entry — the NEXT student who hits
   this box gets normal Instructor Mode coaching, not a Show Me Mode
   escape hatch, because Trinity now actually knows the technique.

This is the mechanism that makes Show Me Mode self-defeating in a good
way: every use of it is evidence of a KB gap, and every use should
shrink the population of boxes that will ever need it again. Same
"fixes-to-boxes-lifted" leverage framing as Assimilator, just sourced
from live student stuck-points instead of an offline sweep.

## 6. What this explicitly is NOT (the rails that stay up)

1. **Never hidden.** No code path exists where an agent executes a
   command against the student's active target without a fresh,
   explicit, informed confirmation immediately before that specific
   invocation. This is the one non-negotiable line from the original
   pushback — restated here so nobody reintroduces it as a "quality of
   life" toggle later.
2. **Never multi-step autonomous.** One milestone per invocation, full
   stop. Not "solve the rest of the box."
3. **Never silently rewrites the student's own state to hide that AI
   did it.** The report tagging in §4 is mandatory, not configurable
   off.
4. **Never available outside confirmed retired/practice targets.**
   Same allowlist principle as Coverage Sim/Assimilator.
5. **Not a relaxation of Assimilator's boundary.** Assimilator (see
   its own §6) runs sandboxed QA verification completely separately,
   at build time, against boxes Doc/Cursor/Claude Code CLI stand up —
   it does not gain a new code path into a student's live session
   because Show Me Mode exists. These are two different systems that
   happen to share the Agent Harness invocation plumbing; they do not
   share a trust boundary.

## 7. Open questions (real, unresolved, need review answers)

1. **Anthropic usage-policy compliance mechanism.** Alexander mentioned
   he has "cybersecurity verification program access from Anthropic"
   and wants the setup wizard to surface a suggestion/link for this at
   some point. This needs an actual, concrete answer before Show Me
   Mode ships to anyone beyond Alexander's own use: what specifically
   is that program, what does it authorize, and does live agent-CLI
   command execution against even a retired/practice box require it
   explicitly, or is it already covered by ordinary authorized-use
   terms for practice/CTF platforms? Do not assume; get a written
   answer and cite it in this doc before build.
2. **Consent UX for the wizard.** Where exactly does the wizard
   surface this — a one-time optional mention during setup (low
   friction, easy to miss) vs. required acknowledgment before
   `show-me` unlocks at all (safer, but adds wizard friction Hole F
   already warns against)? Needs its own small design decision, not
   just "the wizard should mention it."
3. **Software-enforced target allowlist.** "Confirmed retired/practice
   target" (§3.3) needs a REAL mechanism, not an honor system —
   platform metadata already exists (`platforms.yaml` per
   FEATURES_BACKLOG's difficulty-aware-guidance entry) but nothing
   currently verifies a target IP is actually a retired lab box vs. an
   arbitrary IP the student typed in. What's the actual verification
   step here? (Candidate: require the wizard's platform selection
   plus explicit "yes this is a practice lab" confirmation captured at
   box-creation time, refuse `show-me` if that flag isn't set — needs
   review.)
4. **Cost/rate limiting.** Agent Harness calls already have an
   implicit cost (student's own agent CLI usage/quota). Show Me Mode
   invokes potentially many more turns per call (actual command
   execution + iteration, not a single bounded question). Does this
   need its own budget/rate-limit guardrail so a stuck student doesn't
   burn an unexpectedly large amount of their own agent quota on one
   stuck step?
5. **Destructive-command safety.** Show Me Mode's agent has real
   execution capability against a real target. What stops it from
   running something destructive/irreversible against the practice
   box (crash a service, corrupt target state) in a way that breaks
   the box for the REST of the student's session, including their own
   subsequent manual work? Needs a safety rule (e.g. read-only/
   enumeration-first bias, no destructive commands without an even
   more explicit second confirmation) before this reaches build.

## 8. What we want from review (Cursor + Claude Code CLI)

Do NOT write implementation code yet. Answer, in a written response
file (see dispatch instructions):

1. Is the trigger-condition gate (§3) tight enough, or does it leave
   an easy path to invoke this as a routine shortcut rather than a
   genuine last resort?
2. Is one-step-per-invocation (§4) actually enforceable in code, or
   does an agent CLI's own multi-turn tool use make "one step" fuzzy
   in practice? Propose a concrete definition of "one step" that's
   mechanically checkable, not just narratively true.
3. §7's open questions — do you have concrete proposals for any of the
   five, especially #3 (software-enforced target allowlist) and #5
   (destructive-command safety)?
4. Report-integrity tagging (§4) — is `source: "show_me_ai"` at the
   Finding/timeline level sufficient, or does professional-mode
   reporting need a more prominent/harder-to-miss disclosure
   mechanism?
5. Any way this design, as written, could be quietly abused to
   approximate the ORIGINAL hidden/silent version Doc rejected (e.g.
   a student invoking it once per step, every step, defeating the
   "genuine last resort" intent even though each individual invocation
   is technically disclosed)? If so, propose a mitigation (rate limit,
   cool-down, escalating friction).

Deliverable: a markdown file with numbered answers plus any additional
concerns not covered by the above questions. No code, no new
dependencies — this is a design-review pass only.

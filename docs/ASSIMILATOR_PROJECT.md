# Assimilator — Design (DRAFT for Cursor/Claude Code CLI review)

Status: DESIGN ONLY. Nothing in this document is built yet. This is
the design for a new build-time/QA-time subsystem, scoped and named
by Alexander directly ("Assimilator"). Reviewers: critique this
document. Do not write code against it yet — see "What we want from
review" at the bottom.

## 1. The problem this solves

`docs/COVERAGE_SIMULATION_PROJECT.md` grades Trinity's engine against
122 real, retired HTB/THM/VulnHub boxes. Current tally:
`findings/coverage_sim_log.jsonl` — 19 pass, 95 partial, 8
capability_gap, 0 fail. Coverage Sim is a smoke detector: it tells us
a box is a PARTIAL and (via the per-box `notes`/`bucket` field) roughly
why, but nothing in the tree closes the loop from "diagnosed partial"
to "verified fix, merged, re-scored as PASS." Today that loop is Doc,
by hand, reading a findings file and writing a patch — one box at a
time, no reuse tracking, no systematic bucketing beyond what a human
remembers to write down.

Assimilator is the automation of that closing step: a repeatable
engine that takes a PARTIAL, diagnoses why it stalled, proposes and
verifies a fix (using AI reasoning where a human would otherwise have
to, and real sandboxed exploitation where citation-matching alone
can't confirm correctness), lands the fix through the existing review
gate, and tracks whether that one fix silently lifts OTHER partials
too — leverage is the actual point, not box-by-box grinding.

## 2. Where it sits in the architecture (and what it reuses)

Assimilator is a **build-time/QA-time system only.** It never runs
during a live student session. This is the single most important
architectural boundary in this document — see §6.

It sits alongside, and reuses machinery from, three existing
subsystems rather than duplicating them:

- **Coverage Sim** (`docs/COVERAGE_SIMULATION_PROJECT.md`) supplies
  the input: the corpus, the fixture format, the pass/partial/fail/
  capability_gap scoring rubric, and the re-scoring mechanism.
  Assimilator does not re-invent grading; it consumes and re-triggers
  it.
- **Update Framework** (`docs/UPDATE_FRAMEWORK.md`) supplies the
  landing mechanism: nothing Assimilator proposes reaches the live KB/
  match/suggest tables without going through the same review-gate
  intake queue everything else uses. Assimilator is a new PRODUCER
  into that queue, not a new bypass around it.
- **Agent Harness** (`docs/AGENT_HARNESS.md`) supplies the AI-
  invocation plumbing: agent-CLI detection (Hermes/Claude/Codex),
  bounded one-shot non-interactive calls, response review before
  trust. Assimilator reuses this code path for its "why did this
  stall" and "what's the missing rule" reasoning steps — it does NOT
  get its own separate LLM integration.

New things Assimilator actually adds:

1. A **diagnosis taxonomy** (§3) — turning today's free-text `notes`
   field into a structured, queryable bucket.
2. A **fix-hypothesis-verify loop** (§4) with a **sandboxed live-
   exploitation lane** (§5) for the cases citation-matching against a
   writeup can't confirm.
3. A **leverage ledger** (§7) — tracking which fixes lifted which
   OTHER boxes, so we can see multiplier effects, not just a
   decrementing partial count.

## 3. Diagnosis taxonomy

Every PARTIAL gets classified into exactly one primary bucket (a box
can be re-classified if a fix reveals a deeper secondary cause).
Buckets are not invented from scratch — they're the real categories
already appearing organically in `findings/coverage_sim_summary.md`
across three checkpoints, formalized:

| Bucket | Meaning | Example (real, from batch 3) |
|---|---|---|
| `missing_kb_entry` | The technique category has no explain/error/suggestion entry at all | IDOR/PCAP, Lua cmdi, WP-config.save, SQLi/SSTI |
| `searchsploit_routing` | KB entry exists, but service/product-name extraction fails to route to the right searchsploit query | HTTP-title-only products (Voting System, Drupal via title, not banner) |
| `missing_suggest_coverage` | Finding is correctly detected, but no suggestion rule fires the right next command | ES-behind-nginx, SNMP->Pandora chains |
| `capability_gap` | The real solve path requires a subsystem Trinity doesn't have at all (BloodHound-style graph reasoning, multi-step RBCD, live credential chaining) | AD+PaperCut, AD UserInfo.exe/RBCD |
| `parser_gap` | Raw tool output isn't parsed into a Finding at all (new tool, new output shape) | (reserved; not yet hit in corpus but AutoRecon/rustscan expansion will hit this) |
| `false_negative_bug` | A genuine bug — Trinity had what it needed and still didn't fire | (rare; caught early, see "Notify-storm" style bugs in FEATURES_BACKLOG.md) |

Each bucket has a different fix shape (§4) and a different confidence
bar for what counts as "verified" (§4.3).

## 4. The core loop

For each PARTIAL box, in bucket order (cheapest/highest-leverage
buckets first — `searchsploit_routing` and `missing_kb_entry` tend to
be mechanical and can cross-lift many boxes; `capability_gap` tends to
be one-off and expensive):

### 4.1 Diagnose
Re-run the box's fixture through the real CLI (same discipline as
Coverage Sim: real fixture -> real `trinity` commands -> captured
output), diff the actual output against what the cited writeup says
the correct next step was, and classify into §3's taxonomy. This step
is **deterministic where possible** — many `searchsploit_routing`
cases are a mechanical diff (what searchsploit query WAS generated vs.
what the box's real product name IS). Reach for Agent Harness's
bounded-question flow only when the mismatch reason is genuinely
ambiguous, not as the default first move.

### 4.2 Hypothesize a fix
Depending on bucket:
- `missing_kb_entry` / `missing_suggest_coverage`: draft the new
  explain/error/suggestion entry text, citing the same writeup already
  in the fixture's `MANIFEST.md` (never a new source).
- `searchsploit_routing`: draft the parsing/extraction rule fix (same
  shape as the real fixes already shipped in this project — e.g.
  `987d83c`'s H2/Supervisor/underscore-path routing).
- `capability_gap`: do NOT hypothesize a quick fix. Flag it into a
  separate "needs its own subsystem" backlog (this is intentionally
  the SLOW lane — seeing 8 of these already, e.g. AD/RBCD, tells us
  Assimilator's real ceiling on the current corpus is well short of
  100%, and that's fine, see §8).

### 4.3 Verify
This is where Assimilator earns its name over "just patch it":
- For `missing_kb_entry` / `missing_suggest_coverage` /
  `searchsploit_routing`: verify by re-running the SAME fixture-based
  Coverage Sim harness. If the box now scores PASS against the cited
  writeup's real solve path, and the full test suite is still green,
  the fix is citation-verified.
- For anything Coverage Sim's static fixture replay can't settle
  (ambiguous multi-branch solve paths, anything where "did this
  actually work" can only be answered by running it) — escalate to
  the **sandboxed live-exploitation lane**, §5. This is the piece that
  makes Assimilator more than a smarter search-and-replace: some fixes
  need to be proven against a live target, not just against a
  transcript.

### 4.4 Land
Every verified fix goes through Update Framework's existing review
queue exactly like an Agent Harness cache entry does — nothing
Assimilator produces is auto-merged. Doc reviews (or a human-equivalent
gate if this scales past manual review capacity — see §8's staffing
note) before it reaches the live KB/match/suggest tables.

### 4.5 Re-score and check leverage (§7)
After landing, re-run the FULL coverage corpus (not just the one box)
to check whether the fix also flipped OTHER partials from partial to
pass as an unplanned side effect (this already happened informally —
one routing fix in batch 3 helped two unrelated boxes). Record this in
the leverage ledger regardless of outcome.

## 5. Sandboxed live-exploitation lane

This is the part of Assimilator that is NEW capability for this
project, not a repackaging of something that already exists, so it
gets its own section and its own hard boundary statement up front:

**This lane runs ONLY inside Doc/Cursor/Claude Code CLI's own
build-time QA environment, against boxes WE deliberately stand up,
never against a student's live session, and never against anything
that isn't already a retired/public practice box we have the right to
attack.**

Mechanism (draft, needs review — see open questions below):
- Target boxes are either (a) HTB/THM retired boxes accessible via
  the operator's own paid VPN access (same access model already used
  informally to verify Coverage Sim citations), or (b) locally-hosted
  vulnerable VM images (VulnHub-style OVAs) run in disposable, network
  -isolated VMs/containers with no route to anything but the target.
- Each verification run: snapshot -> attempt the hypothesized fix's
  suggested command sequence -> capture real output -> diff against
  expected Finding/milestone -> ALWAYS tear down the environment after
  (no persistent state, no snowflake boxes that drift from a clean
  baseline).
- The AI's role here is bounded and specific: given "Trinity suggests
  running X, the writeup says Y should happen" it either confirms the
  real output matches, or characterizes the actual mismatch — it does
  NOT freelance a novel exploit path outside what the fix hypothesis
  already specified. This is a verification step, not an open-ended
  autonomous pentest.
- Every live-verification run is logged with full command transcript,
  same durability standard as `findings/coverage_sim_log.jsonl`.

Reuses Shoulder Mode's pty-recording mechanism (`src/trinity/
shoulder.py`) for the transcript-capture half — same "tee every byte
to a session log" pattern, pointed at a disposable QA sandbox instead
of a student's terminal.

## 6. Explicit non-goals / guardrails

Stated as hard lines, not preferences, because this section is the
one most likely to be misread as "well, we already built live
exploitation, why not use it live":

1. **Never runs against a student's active session.** Assimilator has
   no code path that touches `~/.trinity/trinity.db` for a real
   operator's box. It operates on the corpus/fixture tree
   (`test/fixtures/coverage_sim/`), full stop.
2. **Never touches anything but retired/public/owned practice
   infrastructure.** No live client engagements, no unretired boxes,
   no scope creep into "anything on the internet that looks
   vulnerable."
3. **Never auto-merges.** Every fix — mechanical or AI-assisted —
   passes through the same human (Doc) review gate as everything else
   in this project's history.
4. **Not a launcher for the product.** This is tooling that improves
   Trinity's shipped KB; it ships NOTHING that runs autonomous
   exploitation at product runtime. If Show Me Mode (the separate,
   sibling design — `docs/SHOW_ME_MODE.md`) ever needs live
   exploitation against a student's box, that is Show Me Mode's own
   explicit, disclosed, consented mechanism — not Assimilator's, and
   not silently reused from it just because the plumbing exists.

## 7. Leverage ledger — the actual point of the name

A `assimilator_runs` record per attempt:

```
{
  "box": "string",
  "bucket": "missing_kb_entry|searchsploit_routing|missing_suggest_coverage|capability_gap|parser_gap|false_negative_bug",
  "hypothesis": "string (what fix was proposed)",
  "verification_method": "fixture_replay|sandbox_live_exploit",
  "result": "verified_fix|rejected_hypothesis|escalated_capability_gap",
  "fix_commit": "string|null",
  "boxes_lifted": ["box_name", ...],   // includes itself + any others flipped to PASS as a side effect
  "boxes_regressed": ["box_name", ...] // must be empty at land time; full corpus re-run enforces this
}
```

Headline metric for reporting to the CEO isn't "N partials fixed" —
it's **fixes-to-boxes-lifted ratio** (how many boxes a single fix
moves) and **partial rate over time** (currently 95/122 = ~78%;
target stated honestly, not as "100%", see §8).

## 8. Honest ceiling — what this will NOT get to 100%

Some fraction of the 95 partials (today: at least the 8 already
labeled `capability_gap`, likely more once triaged) are not "we're
missing a KB entry" — they're "Trinity's static match/suggest
architecture cannot express this solve path at all" (BloodHound-style
multi-hop graph reasoning, credential-chaining across multiple
services, timing-dependent races). Assimilator's job on those is to
diagnose and DOCUMENT precisely what's missing, feeding a real
"next subsystem" backlog (same shape as the AD engine did last month)
— not to force a bad fix. Recommend an internal target of "partial
rate under 30%" as a first real milestone rather than promising zero
partials.

## 9. Staged rollout

1. **Triage pass** (no code changes): run diagnosis (§4.1) against all
   95 existing partials, populate the bucket taxonomy, produce a
   ranked backlog by (a) bucket cheapness and (b) suspected leverage
   (does this look like it affects more than one box).
2. **Mechanical-fix batch**: work `searchsploit_routing` and
   `missing_kb_entry` items first (cheapest, highest historical
   leverage per batch-3 evidence).
3. **Sandbox-verification pilot**: pick 3-5 boxes where fixture replay
   alone is ambiguous, build and prove out the live-exploitation lane
   end to end before scaling it.
4. **Re-baseline**: full corpus re-run, updated tally, leverage report
   to Doc/Alexander.

## 10. What we want from review (Cursor + Claude Code CLI)

Do NOT write implementation code yet. Answer, in a written response
file (see dispatch instructions), specifically:

1. Is the diagnosis taxonomy (§3) complete? What bucket is this
   design missing, based on patterns you can see across
   `findings/coverage_sim_log.jsonl` and `docs/COVERAGE_SIM_BATCH3_LINUX10_WINDOWS10.md`?
2. Is the sandbox-verification design (§5) safe and buildable as
   described? What's underspecified — snapshotting mechanism, VM vs.
   container choice, VPN-vs-local-VM tradeoffs, cost/time per
   verification run?
3. Data model critique: is the `assimilator_runs` schema (§7) missing
   fields you'd want for real leverage analysis?
4. Is there real redundancy with any existing subsystem (Coverage Sim,
   Update Framework, Agent Harness) that this design fails to reuse
   and should?
5. Anything in §6's guardrails that's underspecified or has a gap an
   attacker (or a careless future contributor) could drive a truck
   through?
6. Rollout critique (§9): realistic ordering, or would you sequence it
   differently?

Deliverable: a markdown file with numbered answers plus any additional
concerns not covered by the above questions. No code, no new
dependencies, no schema migrations — this is a design-review pass
only.

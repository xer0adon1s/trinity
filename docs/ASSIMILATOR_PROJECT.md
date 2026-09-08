# Assimilator — Design (v2, post-review)

Status: QUARANTINED. See docs/SHOW_ME_MODE_QUARANTINE.md. This
supersedes the v1 draft reviewed by Cursor and Claude Code CLI (see
`findings/design_review_cursor.md` and `findings/design_review_claude.md`
in the `design-review-cursor`/`design-review-claude` worktrees/branches).
Both reviews independently re-derived the corpus tally from the raw
JSONL (not the summary doc) and found the taxonomy incomplete, the
sandbox lane underspecified/risky as drafted, and — most importantly —
that the "8 capability_gap" number cited in v1's honest-ceiling
argument was already stale by 4 rows at the time it was written (the
AD engine shipped and fixed Forest/Active/Sauna/AttacktiveDirectory
after those rows were scored). See "What changed from v1" at the
bottom for the full changelog.

## 1. The problem this solves

`docs/COVERAGE_SIMULATION_PROJECT.md` grades Trinity's engine against
122 real, retired HTB/THM/VulnHub boxes. Tally as of the last full run
(NEEDS RE-BASELINE against current `main` before any triage — see §9
step 0; the corpus JSONL is a snapshot scored across three different
builds, not one point-in-time measurement):
`findings/coverage_sim_log.jsonl` — 19 pass, 95 partial, 8
capability_gap, 0 fail. Coverage Sim is a smoke detector: it tells us
a box is a PARTIAL and (via the per-box `notes`/`bucket` field) roughly
why, but nothing in the tree closes the loop from "diagnosed partial"
to "verified fix, merged, re-scored as PASS." Today that loop is Doc,
by hand, reading a findings file and writing a patch — one box at a
time, no reuse tracking, no systematic bucketing beyond what a human
remembers to write down.

**On "0 fail" — this number is more optimistic than it looks.** Per
Coverage Sim's own rubric, output that is "actively wrong or
misleading for this box (cross-service false match, wrong recommended
tool, nonsensical suggestion)" should score FAIL. Several current
PARTIALs (e.g. `devel`'s vsftpd false-positive-on-any-ftp, the
node-serialize CRITICAL wrongly firing on `help`/`node`/`ultratech`,
`tabby`'s misleading Tomcat-PUT hit) fit that description but were
filed as PARTIAL because the recon step itself was right. "0 fail, 95
partial" reads as "no bugs, lots of gaps" — the more accurate read is
"some of these partials are real bugs wearing a gap-shaped label."
This matters concretely for §4.3's confidence bar (see A1.2-equivalent
in the review — the taxonomy needs a bucket for this, §3).

Assimilator is the automation of the closing step: a repeatable
engine that takes a PARTIAL, diagnoses why it stalled, proposes and
verifies a fix (using AI reasoning where a human would otherwise have
to), lands the fix through the existing review gate, and tracks
whether that one fix silently lifts OTHER partials too — leverage is
the actual point, not box-by-box grinding. The real-sandboxed-
exploitation half of this is now DEFERRED — see §5.

## 2. Where it sits in the architecture (and what it reuses)

**Correction from v1: Assimilator is NOT build-time/QA-only.** v1
stated that as "the single most important architectural boundary in
this document." Per Alexander's explicit clarification, Show Me Mode
(`docs/SHOW_ME_MODE.md`) IS Assimilator, triggered live: when a
student invokes `trinity show-me`, that's the exact same
diagnose-hypothesize-verify-land loop described in §4 below, just
triggered on-demand by one student's real stuck-point instead of
batch-triggered by Doc's offline corpus sweep, and running against a
live target instead of a fixture. "Solve the problem, assimilate the
solution and the data that goes with it" — the name describes both
triggers of the same engine, not two separate systems that happen to
share code. Concretely:

- **Offline/batch trigger:** Doc runs Assimilator's loop across the
  122-box Coverage Sim corpus, in bulk, against fixtures. This is
  §§3-9 below, unchanged.
- **Live/on-demand trigger:** a student runs `trinity show-me`, and
  Assimilator's SAME loop runs against ONE box, ONE finding, live,
  with the "verify" step (§4.3) happening against the real target
  instead of a fixture replay, in Trinity's own execution session (see
  `docs/SHOW_ME_MODE.md` §5 for that session's own safety design —
  the guardrails there are additive to everything in §6 below, not a
  replacement for them).

Both triggers feed the SAME leverage ledger (§7) and the SAME Update
Framework intake queue (§4.4) — a fix discovered live via a student's
Show Me Mode invocation is exactly as reusable, and exactly as subject
to Doc's review gate, as one discovered in Doc's offline sweep. This
also means Show Me Mode's self-defeating-loop property
(`docs/SHOW_ME_MODE.md` §8 — "every use should shrink the population
of boxes that will ever need it again") is really just Assimilator's
leverage ledger measured from a different entry point.

It sits alongside, and reuses machinery from, three existing
subsystems rather than duplicating them:

- **Coverage Sim** (`docs/COVERAGE_SIMULATION_PROJECT.md`) supplies
  the input for the OFFLINE trigger: the corpus, the fixture format,
  the pass/partial/fail/capability_gap scoring rubric, and the
  re-scoring mechanism. Assimilator does not re-invent grading; it
  consumes and re-triggers it. The LIVE trigger (Show Me Mode) doesn't
  need Coverage Sim at all — its "verify" step checks against the
  live target directly.
- **Update Framework** (`docs/UPDATE_FRAMEWORK.md`) supplies the
  landing mechanism for BOTH triggers: nothing Assimilator proposes
  reaches the live KB/match/suggest tables without going through the
  same review-gate intake queue everything else uses. Assimilator
  (from either trigger) is a new PRODUCER into that queue, not a new
  bypass around it — alongside Agent Harness and the opt-in community
  KB sync idea (`docs/TRINITY_2_0_VISION.md` §3) as fellow producers;
  queue capacity needs one shared answer across all of them, not a
  per-feature one.
- **Agent Harness** (`docs/AGENT_HARNESS.md`) supplies the AI-
  invocation plumbing for the DIAGNOSIS/HYPOTHESIS reasoning steps
  (§4.1-4.2): agent-CLI detection, bounded one-shot non-interactive
  calls, response review before trust. The LIVE trigger's actual
  EXECUTION against a real target is a separate, new execution surface
  (see `docs/SHOW_ME_MODE.md` §5) — Agent Harness's existing
  `invoke_agent` is a buffered, non-streaming call and cannot host
  live command execution; don't conflate the two.

New things Assimilator actually adds:

1. A **diagnosis taxonomy** (§3) — turning today's free-text `notes`
   field into a structured, queryable set of causes, shared by both
   triggers.
2. A **fix-hypothesis-verify loop** (§4) — offline against fixtures by
   default (§4.3); live against a real target specifically when
   triggered via Show Me Mode. The sandboxed-QA-lane idea from v1 for
   ambiguous offline cases is deferred (§5) — no corpus evidence it
   was needed once fixture gaps were properly diagnosed.
3. A **leverage ledger** (§7) — tracking which fixes lifted which
   OTHER boxes, fed by BOTH triggers, so we can see multiplier effects
   across the whole install base, not just a decrementing partial
   count on Doc's own corpus.

## 3. Diagnosis taxonomy

Every PARTIAL gets classified into a **primary cause** plus optional
**secondary causes** (a single primary bucket was found, in review, to
silently hide real multi-cause boxes — e.g. `devel` is simultaneously
a missing-KB-entry case AND a false-positive case; picking one loses
the other forever). Buckets are not invented from scratch — they're
the real categories already appearing organically in
`findings/coverage_sim_summary.md` across three checkpoints, expanded
per both design reviews' corpus re-derivation from the raw JSONL:

| Bucket | Meaning | Example (real, from corpus) |
|---|---|---|
| `missing_kb_entry` | The technique category has no explain/error/suggestion entry at all | IDOR/PCAP, Lua cmdi, WP-config.save, SQLi/SSTI |
| `searchsploit_routing` | KB entry exists, but service/product-name extraction fails to route to the right searchsploit query | HTTP-title-only products (Voting System, Drupal via title, not banner) |
| `missing_suggest_coverage` | Finding is correctly detected, but no suggestion rule fires the right next command | ES-behind-nginx, SNMP->Pandora chains |
| `capability_gap` | The real solve path requires a subsystem Trinity doesn't have at all (BloodHound-style graph reasoning, multi-step RBCD, live credential chaining) | AD+PaperCut, AD UserInfo.exe/RBCD |
| `parser_gap` | Raw tool output isn't parsed into a Finding at all (new tool, new output shape) | nmap hostscripts still ignored (checkpoint 2 STOP-AND-ASK #7) |
| `false_negative_bug` | A genuine bug — Trinity had what it needed and still didn't fire | (rare; caught early, see "Notify-storm" style bugs in FEATURES_BACKLOG.md) |
| `false_positive_match` **(NEW)** | Trinity fired and was WRONG — a misleading/wrong-service match shown to the student, currently mis-filed as a content gap because the recon step itself was right | `devel` (vsftpd KB false-positive on any ftp), `help`/`node`/`ultratech` (Node.js product-only match wrongly surfacing a CRITICAL node-serialize exploit), `tabby` (misleading default-Tomcat-PUT hit) |
| `fixture_evidence_gap` **(NEW)** | The evidence needed to solve correctly was never in the nmap-only fixture at all — no KB/routing/suggest fix can close this; the fixture itself needs a companion artifact (gobuster/whatweb/vhost/UDP output) | `knife` (no http-header parser in fixture), `valentine` (heartbleed script not in the cited scan), `admirer` (Adminer only visible in downloaded source, not the banner) |
| `ranking_gap` **(NEW)** | The right answer IS retrieved but gets crowded out of the top-N by an overly broad product query — a policy/ordering decision, not a content or extraction fix, and explicitly reserved as a STOP-AND-ASK in Coverage Sim's own rules | `grandpa`/`granny` (generic "Microsoft IIS httpd 6.0" query floods `limit=5`) |
| `upstream_data_gap` **(NEW)** | Trinity's routing is correct; the upstream ExploitDB/searchsploit mirror itself lacks the entry (version-era mismatch) — the fix lives in Update Framework's sync cadence, never in hand-authored KB content | `broker` (routing correctly asks for OpenWire; EDB mirror has no 2023 CVE) |
| `out_of_model` **(NEW)** | The real solve is content discovery/stego/credential reuse — Trinity behaving perfectly still can't close this with KB content, and shouldn't be "fixed." Terminal bucket: diagnose, mark, never retry | `yearoftherabbit`, `wgel`, `picklerick`, `mrrobot`, `bashed` — roughly 10-15 boxes |

Each bucket has a different fix shape (§4) and a different confidence
bar for what counts as "verified" (§4.3). `fix_shape` is tracked as a
SEPARATE field from the cause bucket above (`kb_content` /
`routing_rule` / `suggest_rule` / `parser` / `fixture` / `sync_policy`
/ `match_policy` / `new_subsystem` / `none`) — diagnosis (what's wrong)
and remedy (what kind of change fixes it) are not the same axis, and
conflating them was a v1 mistake.


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
  Coverage Sim harness, AND by re-running a **precision check across
  the full 122-box corpus** (not just the target box) confirming no
  NEW false-positive CRITICAL/HIGH match appeared on any box whose
  writeup doesn't support it. This second check is mandatory, not
  optional — `searchsploit_routing` fixes work by asking MORE queries,
  which monotonically increases false-positive risk, and nothing else
  in this loop catches "still passes, but now noisier" (see §7's
  `boxes_regressed` note). Both checks green + full test suite green =
  citation-verified.
- `fixture_evidence_gap` and `out_of_model` boxes are NOT sent through
  this verification loop at all — see §3, they're closed by adding a
  companion fixture artifact (evidence gap) or marked terminal
  (out-of-model), never by a KB/routing/suggest change.
- The live-exploitation idea for "citation-matching alone can't
  confirm correctness" cases is DEFERRED — see §5. Reading the full
  122-box corpus during review, no row's diagnosis actually required
  live execution to settle; the ones that looked ambiguous were
  fixture-evidence-gap cases, closed far more cheaply by adding a
  companion fixture artifact than by standing up a hypervisor lab.

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

## 5. Sandboxed live-exploitation lane — DEFERRED, not v1

**Status: deferred, not building this in v1.** Per review (both
Cursor and Claude Code CLI independently), reading all 122 corpus
rows' actual root-cause diagnoses found no case where the honest
answer was "this can only be settled by running it" — the cases that
looked ambiguous were `fixture_evidence_gap` cases (§3), closed far
more cheaply by adding a companion fixture artifact (a gobuster/
whatweb/UDP capture alongside the nmap XML) than by standing up
hypervisor infrastructure. Kept below as a reference design in case a
genuinely execution-only case is found later, but §9's rollout no
longer schedules this, and the two things v1 claimed it could reuse
turned out not to work:

- **v1 claimed reuse of Shoulder Mode's pty-recording** for transcript
  capture. This is wrong and must not be revived without redesign:
  `shoulder.py`'s own docstring states it "only ever reads, never
  writes to or filters the pty" — it is architecturally incapable of
  running commands, by design, on purpose. A QA runner needing to
  actually execute a hypothesized command sequence needs its own
  plain `subprocess` tee-to-file, not this module.
- **v1 claimed the AI's role would stay "bounded" via prompt
  instruction alone** ("does NOT freelance a novel exploit path").
  That's not a control, it's a hope. If this is ever built: the fix
  hypothesis must carry an explicit, ordered command list; the runner
  executes THAT list and captures the transcript; the AI only READS
  the transcript and classifies match/mismatch. It never gets live
  shell access itself.

Reference design (unbuilt, deferred):

**This lane would run ONLY inside Doc/Cursor/Claude Code CLI's own
build-time QA environment, against boxes WE deliberately stand up,
never against a student's live session, and never against anything
that isn't already a retired/public practice box we have the right to
attack.**

If ever revived:
- **Local-only, no VPN lane.** v1 proposed HTB/THM VPN access as an
  option; review correctly flagged this as running automated attack
  traffic across a third party's network under a named person's
  account, subject to their ToS — a real authorization question with
  no clear answer, unlike a fully local, isolated VM with no
  third-party surface at all. If this is ever built, local VulnHub-
  style OVA images only.
- Hypervisor-based (libvirt/QEMU or VirtualBox), not containers — the
  corpus is full VM images, not Dockerfiles.
- Real network isolation (`<forward mode='none'/>` or equivalent) —
  enforced in software, not just documented — plus a hard refuse-to-
  start check if any `tun*`/`tap*`/`wg*` interface is up (reusing
  `vpn.py`'s existing interface enumeration), so the sandbox can never
  see the operator's own lab VPN.
- Runs entirely under an isolated `$HOME` (same mechanism Coverage Sim
  already mandates for every run), enforced by a wrapper, not just
  asserted as a property in this document.

## 6. Explicit non-goals / guardrails

**Rewritten from v1** — v1's guardrail #1 ("never runs against a
student's active session") directly contradicted §2's correction
above and cannot stand as written; Assimilator's live trigger IS Show
Me Mode, which runs precisely during a student's active session, on
purpose. The guardrails below reflect the real boundary: not "offline
only," but "never touches the student's own terminal/history/DB
directly, regardless of which trigger fired."

1. **Never writes into the student's own terminal or shell history.**
   Whether triggered offline (batch, against fixtures) or live (Show
   Me Mode, against a real target), Assimilator's execution — the
   actual running of commands — happens either against the fixture
   tree (`test/fixtures/coverage_sim/`, offline trigger) or in
   Trinity's own separate execution session (`docs/SHOW_ME_MODE.md`
   §5, live trigger). It never injects into or reads back from the
   student's own Shoulder Mode pty session. This is the real hard
   line, not "offline vs. live."
2. **The offline trigger never touches anything but retired/public/
   owned practice infrastructure** (the Coverage Sim corpus). No live
   client engagements, no unretired boxes, no scope creep into
   "anything on the internet that looks vulnerable." The live trigger
   (Show Me Mode) is gated by its own authorization attestation, not a
   hardcoded allowlist — see `docs/SHOW_ME_MODE.md` §4 and
   `docs/OPEN_DECISIONS.md`'s "Auto-run scans or exploits" entry for
   why a hardcoded per-box allowlist was explicitly rejected.
3. **Never auto-merges — from either trigger.** Every fix —
   mechanical, AI-assisted, sourced offline or live — passes through
   the same human (Doc) review gate as everything else in this
   project's history, tracked via `intake_candidate_id` (§7).
4. **The live trigger's own execution safety (destructive-command
   denylist, milestone scoping, wall-clock/turn caps) is specified in
   `docs/SHOW_ME_MODE.md` §6, additive to everything above, not a
   separate or looser standard.** There is no code path where
   "Assimilator" is invoked as a looser, unreviewed alias for live
   execution that Show Me Mode's own disclosure/safety rules don't
   apply to — they are the same feature, same rules, regardless of
   which name is used to talk about it.

## 7. Leverage ledger — the actual point of the name

A `assimilator_runs` record per attempt (schema expanded per review —
the field names below fix a real ambiguity: `bucket` already means
two different things in `coverage_sim_log.jsonl`, so this uses
distinct names):

```
{
  "run_id": "string",
  "started_at": "iso8601", "finished_at": "iso8601",
  "trinity_commit": "string",        // SHA the diagnosis+verification ran against --
                                      // without this, records go stale silently
                                      // (exactly what happened to the AD capability_gap
                                      // rows -- see "What changed from v1" below)
  "box": "string",
  "primary_cause": "missing_kb_entry|searchsploit_routing|missing_suggest_coverage|capability_gap|parser_gap|false_negative_bug|false_positive_match|fixture_evidence_gap|ranking_gap|upstream_data_gap|out_of_model",
  "secondary_causes": ["string", ...],
  "fix_shape": "kb_content|routing_rule|suggest_rule|parser|fixture|sync_policy|match_policy|new_subsystem|none",
  "hypothesis": "string (what fix was proposed)",
  "fixture_sha": "string",           // hash of the fixture BEFORE the fix; if the fix
                                      // changed the fixture too, flag for human review --
                                      // this is how the loop could otherwise "fix" its own test
  "verification_method": "fixture_replay",   // sandbox_live_exploit reserved, unused while §5 is deferred
  "verification_evidence": "path/to/transcript",
  "precision_check_passed": true,    // full-corpus false-positive check from §4.3, mandatory
  "result": "verified_fix|rejected_hypothesis|escalated_capability_gap|needs_policy_decision",
  "intake_candidate_id": "string|null",   // FK into Update Framework's queue -- required non-null
                                           // before result can be verified_fix
  "reviewer": "string|null", "reviewed_at": "iso8601|null",
  "fix_commit": "string|null",
  "self_lifted": true,               // did the fix flip ITS OWN box to pass
  "others_lifted": ["box_name", ...],// OTHER boxes flipped as a side effect -- the real leverage number
  "boxes_regressed": ["box_name", ...],  // pass->partial regressions; must be empty at land time
  "new_false_positives": ["box_name", ...],  // still-passing boxes that got NOISIER -- the
                                              // failure mode boxes_regressed alone can't see
  "agent_calls": 0, "wall_clock_seconds": 0
}
```

`needs_policy_decision` is a fourth `result` value for `ranking_gap`-
type cases — a fix that requires a priority/ordering POLICY call (e.g.
changing `limit=5` or match ordering), which Coverage Sim's own rules
already reserve as a STOP-AND-ASK for Doc, not something Assimilator
decides unilaterally.

Headline metric for reporting to the CEO isn't "N partials fixed" —
it's **fixes-to-boxes-lifted ratio** using `others_lifted` (NOT
`self_lifted` folded in — every fix trivially "lifts" its own box, so
counting that as leverage inflates every row by exactly 1 and hides
which fixes are actually high-value) and **partial rate over time**,
measured against a re-baselined tally (see §8, §9 step 0) rather than
the stale snapshot this document originally cited.

## 8. Honest ceiling — what this will NOT get to 100%

**This section's number was wrong in v1 and is corrected here as a
live example of why `trinity_commit` staleness tracking (§7) matters.**
v1 cited "8 capability_gap rows" as the honest floor. Four of those
eight (Forest, Active, Sauna, AttacktiveDirectory) were AD/Kerberos
boxes diagnosed before the AD engine shipped — that engine has since
been built, tested, and passed 19/19 AD boxes in a dedicated
simulation round with clean negative controls
(`findings/ad_sim2_summary.md`). The corpus JSONL is a snapshot scored
across three different builds and was never re-baselined against
current `main` before v1 used it as evidence. This is exactly why §9
now starts with a mandatory re-baseline step before any triage.

The real ceiling is still genuinely below 100% — `out_of_model` alone
(§3) covers roughly 10-15 boxes that no KB content can legitimately
close (content discovery, stego, credential reuse), and true
`capability_gap` cases (architecture Trinity doesn't have at all —
BloodHound-style graph reasoning, live credential-chaining) will
remain after re-baselining, just not the specific stale count v1
quoted. Recommend an internal target of "partial rate under 30%,
measured against a freshly re-baselined denominator" — the honest-
ceiling instinct from v1 was correct, it just needs current data.

## 9. Staged rollout

**Resequenced from v1** — the mechanical-fix batch was originally step
2 with no precision check in place; both reviews independently flagged
that as backwards, since `searchsploit_routing` fixes are exactly the
ones that increase false-positive risk (§4.3).

0. **Re-baseline** (NEW, mandatory first step): run the full 122-box
   corpus against current `main` before triaging anything. Produces
   the honest t=0 tally this document currently lacks, and catches
   staleness like §8's AD example before it corrupts the backlog.
1. **Triage pass** (no code changes): run diagnosis (§4.1) against
   every non-pass box using the FULL taxonomy from §3 (not just the
   original four buckets) — expect this to immediately re-bucket a
   meaningful chunk of `missing_kb_entry` into `fixture_evidence_gap`,
   `false_positive_match`, and `out_of_model`, shrinking the population
   Assimilator can actually fix.
2. **Build the precision/regression harness** (NEW, moved up from
   nonexistent in v1): a "no new CRITICAL/HIGH match appears on any
   box whose writeup doesn't support it" check across all 122 boxes,
   built and passing BEFORE the mechanical-fix batch starts — same
   negative-control discipline the AD engine already used successfully
   (`findings/ad_sim2_summary.md`).
3. **Mechanical-fix batch**: work `searchsploit_routing` and
   `missing_kb_entry` items (the ones that survived re-bucketing in
   step 1), verified against BOTH the fixture and the precision
   harness from step 2.
4. **Re-baseline and leverage report**: full corpus re-run, updated
   tally, leverage report (using `others_lifted`, §7) to Doc/Alexander.

The sandbox-verification pilot from v1's step 3 is REMOVED from this
rollout — see §5, deferred, no corpus evidence it's needed.

## 10. What changed from v1 (changelog against the two design reviews)

- Corrected the core architecture: Assimilator is NOT build-time/QA-
  only (§2) — Show Me Mode is its live trigger, and both triggers are
  real and coexist. v1 stated the opposite as its "single most
  important architectural boundary," which was wrong per Alexander's
  explicit clarification.
- Expanded the diagnosis taxonomy from 6 to 11 causes (§3), adding
  `false_positive_match`, `fixture_evidence_gap`, `ranking_gap`,
  `upstream_data_gap`, and `out_of_model` — all found by re-reading
  the real corpus root causes in review, not invented abstractly.
  Split `fix_shape` out as its own field, separate from cause.
- Added a mandatory full-corpus precision/false-positive regression
  check to §4.3's verification step and moved it earlier in rollout
  (§9 step 2) — `searchsploit_routing` fixes mechanically increase
  false-positive risk and nothing in v1 caught "still passes, but now
  noisier."
- Deferred the sandboxed live-exploitation lane entirely (§5) — no
  corpus row's diagnosis actually required live execution to settle;
  cheaper to close via better fixtures. Removed the false claim that
  it could reuse Shoulder Mode's pty (that module is read-only by
  design and cannot execute commands).
- Corrected §8's stale "8 capability_gap" number — 4 of those 8 were
  AD boxes already fixed by the shipped AD engine, discovered only
  because review re-checked the corpus against current `main` instead
  of trusting the cited snapshot.
- Expanded the `assimilator_runs` schema (§7) with provenance
  (`trinity_commit`), anti-gaming (`fixture_sha`), the missing failure
  mode (`new_false_positives`), review-gate linkage
  (`intake_candidate_id`, `reviewer`), and honest leverage accounting
  (`others_lifted` instead of an inflated-by-1 `boxes_lifted`).
- Resequenced rollout (§9): mandatory re-baseline first, precision
  harness built before the mechanical-fix batch (not after), sandbox
  pilot removed.
- Rewrote §6's guardrails to match the corrected architecture (live
  trigger runs during a student's session, on purpose; the real hard
  line is "never touches the student's own terminal/history directly,
  regardless of trigger," not "offline only").

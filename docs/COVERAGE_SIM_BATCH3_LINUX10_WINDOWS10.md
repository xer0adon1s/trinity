# Project: Trinity Coverage Simulation — Batch 3 (10 Linux + 10 Windows)

Status: PARTIAL. Assigned to Cursor (executes: research, fixtures, real
CLI simulation, scoring, logging, narrow bucket-1 live fixes). Doc
(Claude) reviews the worktree output after completion, bug-fixes as
needed, and reports findings back to Alexander. Same ground rules as
the original `docs/COVERAGE_SIMULATION_PROJECT.md` (read that file
first — this doc only states what's DIFFERENT for this batch, it does
not repeat every rule).

## Why this batch, and what's different from before

Two prior checkpoints already exist on `main` (commits `90c04fa` 20-box,
`ce2cffa` 102-box total — see `findings/coverage_sim_summary.md` and
`findings/coverage_sim_log.jsonl`). This batch is a smaller, sharper
follow-up: exactly **20 NEW boxes, 10 Linux + 10 Windows**, not a fresh
150-box sweep. Alexander wants throughput on real findings/fixes now
that the pattern is proven, not corpus size for its own sake.

**Do NOT re-simulate any box already in the corpus.** The full list of
102 already-covered box names (lowercase) is:

```
access, active, admirer, alfred, anonymous, arctic, armageddon,
attacktivedirectory, bashed, basicpentesting, basicpentesting1,
bastard, beep, blue, blunder, bounty, brainpan, broker,
brooklynninenine, buff, celestial, chatterbox, cronos, dc1, dc2, dc3,
dc4, delivery, devel, doctor, earth, easypeasy, forest, friendzone,
fristileaks, gamingserver, goldeneye, grandpa, granny, haircut, help,
ice, ignite, irked, jarvis, jeeves, jerry, kenobi, kioptrix1,
kioptrix2, kioptrix3, kioptrix4, knife, lame, lazysysadmin, legacy,
magic, mango, mirai, mrrobot, netmon, networked, nibbles, nineveh,
node, openadmin, optimum, overpass, photographer, picklerick, poison,
popcorn, postman, pwnlab, ready, relevant, remote, sau, sauna,
scriptkiddie, sense, servmon, shocker, sickos12, silo, simplectf,
skynet, solidstate, source, stapler, steelmountain, sunday, swagshop,
tabby, tomghost, traverxec, ultratech, valentine, vulnversity, wgel,
writeup, yearoftherabbit
```

Cross-check every candidate box name against this list (case-
insensitive) before researching it. If you accidentally research one
that's already covered, discard it and pick a different box — don't
log a duplicate.

## Corpus construction for this batch

Exactly 10 Linux + 10 Windows (20 total, not "roughly" — hit this
exact split). Same diversity axes as the original project (platform
mix across HTB/THM/VulnHub, Easy+Medium difficulty, vuln-category
spread — don't cluster on SMB RCE or one CMS). Prioritize categories
NOT already well-represented in the 102-box corpus per the checkpoint
summary's "new categories" note (see `findings/coverage_sim_summary.md`
lines ~43) — e.g. avoid another 5th Redis/Jenkins-shaped box if the
corpus already has one; look for genuinely new services/vuln shapes
where practical, while still using only real, citable, RETIRED-box
writeups (same sourcing rule as always — 0xdf, ippsec, official
platform writeups, VulnHub author writeups, TJnull-style lists).

**Windows-specific note:** up to 2 of the 10 Windows boxes MAY be
AD-flavored if a genuinely good, well-documented one fits — these will
likely land in `capability_gap` (expected, still useful signal, same
as the existing 5 AD capability-gap entries). The other 8+ should be
non-AD Windows boxes (service misconfig, outdated software CVE, weak
creds, IIS/web app on Windows, etc.) since that's the more common real
teaching case for a non-AD Windows box and this corpus is currently
light on Windows generally (27 of 102 vs 75 Linux).

Append new rows to the EXISTING
`test/fixtures/coverage_sim/MANIFEST.md` rather than creating a
parallel manifest — keep this project's history as one continuous
ledger, same as the two prior checkpoints did.

## Per-box procedure, scoring rubric, failure bucketing

**Identical to `docs/COVERAGE_SIMULATION_PROJECT.md`'s existing
sections** ("Per-box procedure", "Score", "Failure bucketing", "What
you're authorized to fix live vs. what you log only"). Read and follow
those verbatim — not reproduced here to avoid the two docs drifting out
of sync. Same JSONL schema, same PASS/PARTIAL/FAIL/CAPABILITY_GAP
rubric, same bucket-1-only live-fix authorization (mechanical
searchsploit-routing / FTS-stopword fixes only, always with a
regression test using the real box's data, always full suite green
after).

**One addition for this batch specifically:** before starting new
boxes, skim `findings/coverage_sim_summary.md`'s "Live fixes shipped
this session" table (both checkpoints) so you know what's ALREADY been
fixed (nmap role-suffix stripping, English-word path-segment
skiplist, openwire/express-framework stripping, `/uploads/` skip) —
don't rediscover and re-fix the same pattern; if a new box hits one of
these ALREADY-FIXED patterns, that's a PASS/expected-working case, not
a new finding.

## Append to the SAME findings files (continuity, not a new set)

- `test/fixtures/coverage_sim/MANIFEST.md` — append 20 new rows.
- `findings/coverage_sim_log.jsonl` — append 20 new JSON lines (same
  schema). Do not touch the existing 102 lines.
- `findings/coverage_sim_summary.md` — add a new "Checkpoint 3 (batch
  3: 10 Linux + 10 Windows)" section at the top (above checkpoint 2's
  section, same "newest checkpoint first" convention the file already
  uses), with its own tally table, bucket breakdown, PASS list, live
  fixes shipped this batch, and pytest before/after counts. Do not
  edit or renumber the existing checkpoint 1/2 sections.

## Git / worktree

Work in a NEW git worktree off current `main` (which now includes the
Coach Meterpreter-nesting + AD explain-cache + msfconsole `back` fixes
from `b356c8d`):

```
git worktree add -b coverage-sim-batch3 ../trinity-wt-coverage-sim-batch3 main
```

Commit progress incrementally inside that worktree (same "commit as
you go, don't wait until the end" discipline as the prior checkpoints).
Do NOT merge to main yourself, do NOT push. Doc reviews and merges
after examining the findings, same as every prior batch.

## Deliverable

At completion, the worktree (`../trinity-wt-coverage-sim-batch3`,
branch `coverage-sim-batch3`) containing:
- `test/fixtures/coverage_sim/` — 20 new fixture sets, `MANIFEST.md`
  appended.
- `findings/coverage_sim_log.jsonl` — 102 existing lines untouched, 20
  new lines appended (122 total).
- `findings/coverage_sim_summary.md` — new checkpoint-3 section
  prepended, tally + bucket breakdown + PASS list + live fixes + pytest
  before/after.
- Any live bucket-1 fixes, committed individually with clear messages,
  full suite green after each.

A short final report in the worktree
(`findings/coverage_sim_batch3_cursor_report.md`): what was built, the
final tally, anything logged as a candidate KB entry / suggest branch
proposal for Doc's review, anything genuinely stuck on / needing Doc's
judgment call rather than silently decided.

## What happens after (so Cursor knows the handoff shape)

Doc (Claude) will: read the worktree's findings + diff, spot-check a
sample of the 20 boxes' fixture-vs-real-CLI-output claims, run the full
test suite itself, review any live bucket-1 fixes for correctness and
regression risk, and either (a) merge clean work to main, (b) bug-fix
anything broken directly, or (c) send back specific, narrow follow-up
items — mirroring the existing Claude/Cursor review loop already used
on this project (see `docs/CURSOR_HANDOFF_CONTINUE.md`'s "Cursor log"
section for the established review-and-fix pattern). Report back to
Alexander with the final tally, notable bugs found/fixed, and open
capability-gap items once review is done.

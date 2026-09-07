# Update Framework — Design

Status: DESIGN ONLY. Nothing in this document is built yet. This is
the plumbing layer other design docs (Agent Harness, GTFOBins
ingestion, Methods Index) plug into rather than each building their
own sync/review logic.

## The goal

Alexander's framing, verbatim intent: "trinity should update everything
that makes sense... this includes trinity's very own self-generated
intel that it scrapes as users are using it. we want this thing to
GROW AND BLOSSOM and eventually cast the widest net possible."

Two distinct things are being asked for, and they need two distinct
mechanisms:

1. **Sync FROM the outside world** — pull the latest version of
   external, already-vetted data sources (GTFOBins, ExploitDB via
   `searchsploit`'s own update mechanism, PayloadsAllTheThings,
   platform metadata) so Trinity's local mirrors don't quietly go
   stale. This is a straightforward "is there something newer
   upstream, if so pull it" job — no trust decision needed beyond
   "do we trust this upstream source at all" (already established
   per-source in DESIGN.md's crowdsourcing model).
2. **Grow FROM local use** — knowledge Trinity's own install generates
   during real sessions (via the Agent Harness, see
   `docs/AGENT_HARNESS.md`) needs a review gate before it's trusted,
   because unlike GTFOBins/ExploitDB it hasn't been vetted by anyone
   but this one operator's one session. This is the harder, more
   important half of the framework.

## Part 1: syncing external sources

**Trigger: silent, automatic, on every launch.** Per Alexander's
explicit call — no prompt, no "check for updates? y/n," just checks
and pulls if something's newer. This mirrors how e.g. Homebrew/apt
refresh package indexes automatically, not how a heavier "would you
like to update" installer flow works.

**Mechanism, per source type:**
- **Git-backed sources** (GTFOBins, PayloadsAllTheThings, SecLists if
  ever vendored): a shallow local clone/mirror, `git pull` (or
  equivalent) on launch, capped by a minimum-interval check (don't
  re-pull on literally every single command invocation within the
  same minute — check a last-synced timestamp in `local_state` first,
  same table that already tracks wizard setup state).
- **ExploitDB**: `searchsploit` already has its own update mechanism
  (`searchsploit -u`) — Trinity should just invoke that on the same
  cadence, not reinvent exploit-db syncing.
- **Platform metadata** (if/when HTB/THM API integration ever lands):
  a periodic re-fetch of public, unauthenticated metadata only — this
  framework doesn't change the earlier "no auth-gated scraping"
  decision, just gives it a home.
- **Never network calls mid-session** beyond this launch-time check —
  consistent with the existing "no silent network" principle elsewhere
  in DESIGN.md. The check happens once, at launch, visibly logged
  (even if not interactively prompted), not polled continuously.

**Failure mode:** any sync failure (no network, upstream unreachable,
git conflict) must degrade to "use what's already local" silently —
same defensive pattern as `vpn.py`'s VPN check or `platform_registry.py`'s
Omarchy theme read. A missed update is never a hard failure.

## Part 2: the intake/review pipeline (the important half)

Every piece of knowledge Trinity's own install generates — Agent
Harness answers, live-drafted Methods Index entries, anything else
that isn't a straight mirror of an already-vetted external source —
lands in an **intake queue**, not directly in the real KB/explain
cache/error patterns tables.

**Shape:** a new local table (working name `intake_candidates`):
`id, kind (explanation|error_pattern|kb_entry|method), payload (the
proposed record, structured per its target table's shape), source
(which mechanism produced it — 'agent_harness', 'methods_live_draft'),
box_id (if session-scoped), status (pending|approved|rejected),
reviewed_at, reviewer_note`. Nothing in this table is ever read by
`trinity next`/`explain`/`error`/the coach — only approved records
that have been copied into their real destination table are live.

**Review, per Alexander's explicit call:** "all of these suggestions
for increasing the base knowledge would be reviewed by YOU claude, and
confirmed as worthy to add, before adding. nothing will be manually
merged or added [without review]." Concretely, this means:
- A review command (`trinity intake review` or similar) lists pending
  candidates for a human/Claude review pass.
- Approving a candidate copies it into its real destination table
  (`command_explanations`, `error_patterns`, `kb_entries`, or a
  `methods_index/*.yaml` file) using the EXACT SAME insertion
  functions that already exist for those tables (`save_explanation`,
  `save_error_fix`, etc.) — the intake queue is a staging area in
  front of existing, already-tested write paths, not a new one.
- Rejecting a candidate marks it rejected with a note, kept for
  audit/pattern-recognition (if the same kind of bad suggestion keeps
  showing up, that's useful signal), never silently deleted.
- This review pass does not need to be synchronous with the session
  that generated the candidate — an operator can keep working while
  candidates queue up, review happens later (by Claude, in a
  dedicated pass, the same way code review happens today).

## Part 3: opt-in outbound sharing (the "give back" half)

Once a candidate is APPROVED locally (i.e., already passed review),
the operator can additionally choose to contribute it upstream to a
shared community pool — never before local approval, never silently.

**When asked:** during wizard setup (`prompt_new_project`/`run_intro`),
framed as contribution, not data collection. Alexander's explicit
instruction: "should ask the user in a way that makes them feel like
they're REALLY CONTRIBUTING to help the community and the tool grow,
not that I'm trying to suck their data or anything." Draft copy
direction (refine at build time, not locked): *"Trinity gets smarter
every time someone uses it and confirms a new answer. Want your
confirmed answers to help every other Trinity user too? (Anonymous —
no box names, no IPs, no personal info. You can turn this off any
time.)"* Default: off (opt-in only, per the existing `sharing.py`
precedent — `set_sharing_enabled` already defaults False).

**Format:** a standardized schema so contributed records are easy to
parse/merge later without per-contributor bespoke handling — this
reuses `sharing.py`'s existing `scrub_identifying()` IP-scrubbing
pattern and extends `write_share_bundle`'s JSON shape rather than
inventing a new export format. Every contributed record carries:
`kind`, `payload` (already scrubbed), `source='community_contributed'`,
a content hash (for de-duplication when merging multiple contributors'
bundles upstream), and NO operator-identifying fields whatsoever (no
box name, no target, no username) — the existing share-export
anonymization rules apply here without modification.

**Merge-upstream mechanism**: out of scope for this doc to fully
design (it implies some kind of aggregation point — a shared repo PR
flow to start, matching the existing `platforms.yaml`/KB
crowdsourcing model DESIGN.md already describes, not a hosted service
Trinity talks to automatically). Start with: contributed bundles are
still local files the operator reviews and PRs upstream themselves,
same trust model as `share-export` today, just carrying more/better-
formatted content. A hosted aggregation service is a bigger
conversation (accounts, infrastructure, abuse-prevention) explicitly
NOT decided by this document.

## Non-negotiables

- No knowledge candidate ever reaches a real, live table without
  passing through review. No exceptions, no "trusted source" bypass
  for Agent-Harness-generated content (external sources like GTFOBins
  are handled by Part 1's sync, which is a different, already-vetted
  trust category).
- Outbound sharing is opt-in, off by default, offered once at setup
  (re-offerable via `trinity setup`), never silent.
- Every synced/contributed record is traceable to its source — this is
  the same "everything traceable to a `source` field" principle
  DESIGN.md already states, just applied to a new axis of data.
- A sync failure or unreviewed queue backlog never blocks normal
  Trinity usage — `next`/`hint`/`watch` all keep working exactly as
  well with a stale mirror or a growing intake queue as without one.

## Open questions for whoever builds this

- Where does the review pass actually happen for someone who ISN'T
  running this project through Claude directly (i.e., a random OSS
  user, not Alexander)? The "reviewed by Claude" model works for this
  project's own development loop; a shipped, public version of Trinity
  needs either a documented manual review command flow, a maintainer
  review queue for community contributions, or both.
- Minimum sync interval (daily? weekly? size-of-diff-based?) — not
  specified here, pick something conservative and document it in
  `tools.py`/wherever the sync scheduler lives.
- Whether intake queue size should ever surface to the operator
  ("Trinity has learned 12 new things this week, reviewing later") —
  a nice-to-have, not required for v1 of this framework.

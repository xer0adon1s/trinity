# Methods Index — Design

Status: DESIGN ONLY. Nothing in this document is built yet
(a hand-authored example file, `methods_index/lame.yaml`, exists as a
prototype/reference from an earlier drafting pass — it is not wired
into the CLI). Updated per `docs/CLAUDE_CURSOR_DEBATE.md` and the
2026-09 design pivot (`DESIGN.md`'s Agent Harness / Update Framework
docs) — two changes from the original design below:

1. **Gated as a stuck-escape-hatch, not freely browsable.** Originally
   this was meant to be looked up any time via `trinity methods --box
   <name>`. Per Alexander's explicit call, that risks turning a first
   attempt into "pick from a menu" instead of "figure it out" — the
   whole index now surfaces primarily as the payoff of Rabbit Hole
   Detection's stuck signal (see `docs/RABBIT_HOLE_DETECTION.md`):
   "there are a few known shapes people have used to crack machines
   like this — want to see them?" A direct `trinity methods` lookup
   can still exist as a power-user command, but it is not how a
   first-time operator is meant to discover this feature.
2. **Entries can be drafted LIVE by the Agent Harness during a stuck
   moment**, not only produced by an offline batch pipeline ahead of
   time. Per Alexander: "ideally we could scrub the entire list of alt
   methods with AI in the moment, specifically to identify which
   method is likely easiest and then gently guide the user down that
   path with escalating hints." Same citation/summary-length rules
   apply to a live-drafted entry as to an offline-pipeline one — see
   "Attribution rules" below, unchanged.

## The actual goal (per Alexander, verbatim intent)

Not "scrape and store other people's writeups." The real goal: for
each retired box, many public writeups exist, and they often solve it
via genuinely different methods — different enumeration approaches,
different footholds, different privesc paths. A learner who only ever
sees one canonical path develops a narrower instinct than one who
understands "there were actually 4 different ways in, and here's the
shape of each." The Methods Index captures *that structural fact* —
which distinct methods exist and the one-line shape of each — with a
citation back to the specific writeup for anyone who wants the full
account. It is a citation index, not a copy.

## Why this is legally/ethically sound (not just convenient)

- Facts and methods are not copyrightable — only a specific writer's
  expression of them is. "One path used X technique via Y vector" is a
  fact about what happened on a public, retired machine; it is not a
  reproduction of anyone's prose.
- HTB's own policy explicitly permits writeups once a machine retires
  — the source material this indexes is stuff the platforms themselves
  sanctioned into public existence.
- Mandatory, structural attribution (not optional, not buried) is what
  keeps this squarely on the citation side of the line, and — per
  Alexander's explicit goal — genuinely benefits the original writers
  by directing readers to them, rather than replacing them.
- Never indexes anything behind a paywall/subscription (HTB's own
  Pro-Labs writeups, Patreon-gated content, etc.) — public,
  Google-able, free-to-read sources only.

## Data shape

One record per (box, method):

```
BoxMethodsIndex
  box_name: str              # e.g. "Lame" -- generic across platforms
                              # by design, not tied to one platform id
  platform: str | None       # htb/thm/vulnhub/etc, if known
  methods: list[Method]

Method
  category: str               # 'enumeration' | 'foothold' | 'privesc'
  technique: str               # short label, e.g. "Samba username map
                                # script RCE (CVE-2011-2523)"
  summary: str                 # Trinity's OWN one-to-two sentence
                                # paraphrase of the general shape of the
                                # approach -- never copied text, and
                                # deliberately short: enough to orient,
                                # not enough to substitute for reading
                                # the source
  source_url: str              # REQUIRED, no exceptions
  author: str                  # REQUIRED, no exceptions -- credited
                                # by name/handle every time this method
                                # is ever displayed
  retrieved_at: str            # when Trinity's index last confirmed
                                # this entry (source pages disappear;
                                # staleness should be visible)
```

A box with 4 independently-sourced writeups showing 2 different
enumeration approaches, 3 different footholds, and 2 different privesc
paths produces roughly 7 Method entries, not 4 full writeup summaries
— the index is organized by distinct technique, not by source article.
Multiple writeups agreeing on the same method collapse into one Method
entry citing whichever source explains it best (or citing more than
one source for the same method, if it adds value).

## Attribution rules (non-negotiable, enforced structurally)

- `source_url` and `author` are required fields — a Method record
  without them is invalid, full stop, not just discouraged.
- Every place Trinity ever displays a Method (report, hint output, CLI)
  renders the citation inline, not as a hidden metadata field the
  operator has to go dig for.
- `summary` has a soft length ceiling enforced at generation time
  (roughly 1-2 sentences) — long enough to explain the shape of the
  approach, short enough that it can never function as a substitute for
  reading the actual writeup.
- Never includes verbatim quoted text from a source in `summary` —
    paraphrase only. This is a build-time rule for whatever process
    generates these records, human or AI.

## How records get built: a subagent pipeline, OR a live Agent Harness draft

Two paths now produce a valid Method record — both must satisfy the
exact same attribution rules above; neither gets special trust.

### Path A: offline subagent pipeline (original design, unchanged)

This is explicitly NOT something the live recon-parsing engine does,
and NOT something that happens inline in normal Trinity usage. It's an
offline, batch, human-reviewable pipeline:

1. **Trigger:** either a scheduled job (e.g. "index the next N popular
   retired boxes") or on-demand (`trinity methods-fetch "<box name>"`
   run by an operator who wants a specific box indexed before starting
   it — ties into the earlier "starting a specific box" idea).
2. **Search:** web_search for `"<box name>" writeup htb` (or thm/etc),
   collect the top public, non-paywalled results.
3. **Extract-and-summarize:** for each result, a subagent reads the
   writeup and extracts ONLY: which category (enum/foothold/privesc)
   each described step falls into, a short paraphrase of the technique,
   and the source URL + author. This step should run as a delegated
   subagent task specifically because it involves reading substantial
   external content that shouldn't flow through Trinity's own primary
   context, and because "extract structured facts, discard the prose"
   is exactly the kind of bounded, well-defined subtask that's cheap to
   verify on return.
4. **De-duplicate:** compare extracted methods across all sources for
   this box; collapse matching techniques into one Method entry
   (possibly multi-cited), keep genuinely distinct ones separate.
5. **Route through the Update Framework's intake queue** (see
   `docs/UPDATE_FRAMEWORK.md`) — given the copyright sensitivity, every
   candidate is reviewed before merging, specifically checking that
   `summary` fields read as paraphrase, not near-verbatim lifts, and
   that every record has real, working source_url + author fields.
6. **Store:** once approved, append to a `methods_index/<box_name>.yaml`
   (or per-platform subdirectory) file — same crowdsourcing model as
   `platforms.yaml` and the explain-seed library: shipped defaults,
   locally extensible, PR-able upstream.

### Path B: live Agent Harness draft (new — during a stuck session)

When Rabbit Hole Detection's stuck signal fires (see
`docs/RABBIT_HOLE_DETECTION.md`) and the operator accepts the Methods
Index offer, Trinity can hand the box name + platform to the Agent
Harness (see `docs/AGENT_HARNESS.md`) and ask it to research and draft
Method records live, rather than requiring a pre-existing offline
file. This is the "scrub the entire list of alt methods with AI in the
moment" Alexander asked for. Rules:

- The draft is a Method record candidate like any other — it goes
  through the SAME intake-queue review before it's trusted (Path A and
  Path B converge at the same review gate; a live draft is not
  auto-trusted just because it happened synchronously).
- Because the operator is stuck RIGHT NOW, an unreviewed draft can
  still be shown to them immediately as "unverified, here's what I
  found, treat as a lead not a fact" (clearly labeled as pending
  review) while the durable, reusable version waits for review before
  being saved to `methods_index/`. This is the one place a
  not-yet-approved candidate is allowed to reach the operator
  directly — because the alternative is making them wait on a review
  pass mid-session for something time-sensitive. It must be visually
  distinct from a reviewed/cited entry (e.g. "AI DRAFT — UNVERIFIED,
  same citation-required rules apply once confirmed").
- Once a live draft has genuinely valid `source_url`/`author` fields
  (the Agent Harness found and cited a real writeup, it isn't
  inventing one), the same short-paraphrase/no-verbatim-quoting rules
  from the Attribution section apply without exception.
- The Agent Harness may ALSO be asked to rank/recommend among a box's
  already-approved methods — "which of these looks easiest given what
  the operator has already found" — this is pure ranking over trusted
  data, not new-content generation, and does not need a review gate
  itself (no new facts are being asserted, just a suggested order).
  This ranking then drives the escalating-hint behavior described
  below.

## How it surfaces to the operator

- **Primary path: the Rabbit Hole Detection escape hatch.** When
  genuinely stuck (per `docs/RABBIT_HOLE_DETECTION.md`'s trigger
  conditions), Trinity offers: "There are a few known shapes people
  have used to crack machines like this — want to see them?" Declining
  is the default expectation, same as curiosity unlocks. If accepted,
  Trinity shows the indexed methods for that box (approved ones from
  `methods_index/`, or triggers a live Path-B draft if none exist yet),
  grouped by category, each with its one-line paraphrase and citation.
- **Escalating guidance, not a flat list.** Per Alexander: once methods
  are shown, Trinity (optionally with Agent Harness ranking) can guide
  toward whichever method looks like the best fit for what the
  operator has ALREADY found — via the SAME graduated hint ladder
  Instructor Mode already uses (nudge → stronger nudge → full command),
  not a new, separate mechanism. "Gently guide... with escalating hints
  that go from nodding in the direction all the way to saying 'ok
  here's what command to use.'" This should be understood as Methods
  Index handing its chosen method into the EXISTING hint-ladder
  pipeline as a phase-appropriate suggestion, not a rebuild of that
  ladder.
- **Additive, never reductive.** Per Alexander's explicit framing: any
  AI involvement in this flow should be used to help Trinity get
  BETTER at guiding this specific box over time (tweaking/adding
  attack-vector suggestions as more is learned about it) — new
  suggestions offered in realtime, never removing or overriding
  existing valid leads the operator hasn't tried yet.
- **Power-user direct lookup**: `trinity methods --box <name>` can
  still exist as an explicit, opt-in, always-available command for an
  operator who wants to see the range of approaches before diving in
  (not the beginner default path, but not forbidden either) — this
  matches the earlier open question about whether Methods Index should
  ever be manually browsable; the answer is yes, it's just not how a
  first-timer is nudged toward discovering it.
- Natural pairing with Instructor Mode's hint ladder (see
  INSTRUCTOR_MODE.md): a level-3 hint on a box with an indexed method
  could surface "this is a known technique category for this box (see:
  `trinity methods`)" without Trinity itself teaching the specific
  writeup's exact steps, for operators who never hit the stuck
  threshold but still want the citation trail.

## Explicitly out of scope

- Never stores or displays full writeup text, screenshots, or anything
  that could function as a substitute for the original page.
- Never indexes paywalled/subscription content (HTB Pro Labs writeups,
  Patreon-only posts, etc.).
- Never presents a Method without its citation, under any code path.
- Not a live/on-demand scraper invoked mid-session by the recon engine
  — always a separate, offline, reviewable pipeline.

## Build order (once approved)

1. Data schema + the `methods_index/` file format, with a couple of
   hand-built example entries (`lame.yaml` already exists) to prove
   the shape and the attribution rendering end-to-end.
2. `trinity methods --box <name>` — the read/display side (power-user
   direct lookup), since it can be built and tested against
   hand-authored data before any live-drafting or offline pipeline
   exists at all.
3. Wire the Rabbit Hole Detection escape-hatch offer (depends on
   `docs/RABBIT_HOLE_DETECTION.md`'s rebuild landing first).
4. Path A: the offline subagent fetch pipeline (`trinity
   methods-fetch`), routed through the Update Framework's intake
   queue (depends on `docs/UPDATE_FRAMEWORK.md` landing first).
5. Path B: live Agent Harness drafting during a stuck session
   (depends on `docs/AGENT_HARNESS.md` landing first) — build after
   Path A is proven, since Path B reuses the same review gate and
   attribution rules.
6. Escalating hint-ladder integration (Methods Index's chosen method
   feeding Instructor Mode's existing hint pipeline).

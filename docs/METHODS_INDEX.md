# Methods Index — Design

Status: DESIGN ONLY. Nothing in this document is built yet.

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

## How records get built: a subagent pipeline, not inline scraping

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
5. **Human review gate (at least initially):** given the copyright
   sensitivity, early output should be spot-checked before merging —
   specifically checking that `summary` fields read as paraphrase, not
   near-verbatim lifts, and that every record has real, working
   source_url + author fields. This can loosen once the pipeline's
   output quality is well-established.
6. **Store:** append to a `methods_index/<box_name>.yaml` (or per-
   platform subdirectory) file — same crowdsourcing model as
   `platforms.yaml` and the explain-seed library: shipped defaults,
   locally extensible, PR-able upstream.

## How it surfaces to the operator

- `trinity methods --box <name>` (or a box-name lookup before a
  project even starts) — shows the indexed methods for that box,
  grouped by category, each with its one-line paraphrase and citation.
- Framed explicitly as "here are the different paths people have taken
  on this box" — not "here's the answer," and not a replacement for
  actually working the box. This is closer to "here's the menu of
  approaches that exist" than a walkthrough.
- Natural pairing with Instructor Mode's hint ladder (see
  INSTRUCTOR_MODE.md): a level-3 hint on a box with an indexed method
  could surface "this is a known technique category for this box (see:
  `trinity methods`)" without Trinity itself teaching the specific
  writeup's exact steps.

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
   hand-built example entries (no automation yet) to prove the shape
   and the attribution rendering end-to-end.
2. `trinity methods --box <name>` — the read/display side, since it
   can be built and tested against hand-authored data before any
   scraping pipeline exists at all.
3. The subagent-based fetch pipeline (`trinity methods-fetch`),
   starting with a human-reviewed output gate.
4. Loosen the review gate once output quality is established; consider
   scheduling it for a curated list of popular boxes rather than only
   on-demand.

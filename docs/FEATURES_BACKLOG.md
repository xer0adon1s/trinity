# Features Backlog

Status: IDEAS ONLY. Nothing in this document is built. This is where
discussed-but-not-yet-built ideas get recorded so they survive between
sessions, roughly in the order/grouping they were discussed. Promote an
entry to its own design doc (like docs/RABBIT_HOLE_DETECTION.md,
docs/INSTRUCTOR_MODE.md, docs/METHODS_INDEX.md) when it's actually
being scheduled for build.

**Active Cursor homework is not backlog.** See
[CURSOR_HOMEWORK.md](./CURSOR_HOMEWORK.md) — those three assigned
specs (coverage sim, AD engine, AD sim) are current work, not
ideas waiting to be scheduled.

Vetoed or "maybe later, but this would change what Trinity is"
items — LLM chat, auto-install, launchers, Metasploit RPC, live
writeup scrape, `trinity lab` / hyprctl, shell-history sensors,
and the rest of the debate DO NOT list — are written up for
decision in **[docs/OPEN_DECISIONS.md](./OPEN_DECISIONS.md)**.
Park opinions and implement/never calls there, not here. NOTE: two
of those rails (LLM/chat pane, shell-history sensors) were partially
REVERSED in the 2026-09 pivot — see `docs/AGENT_HARNESS.md` and
`docs/SHOULDER_MODE.md`, and `OPEN_DECISIONS.md`'s updated entries for
those two items specifically.

## 2026-09 Cursor prototype triage — decisions record

Cursor drafted roughly 19 features unprompted-beyond-"keep drafting"
across several overnight passes (see `docs/CURSOR_HANDOFF_CONTINUE.md`
for the full log). Claude + Alexander triaged all of them together;
recorded here so the decisions survive between sessions and nobody
re-litigates them from scratch. "NOW" means build this pass; "LATER"
means shelve the code (already written, don't delete) until its
sequencing dependency lands; "CUT" means don't build/ship at all.

- **shell/milestone** — NOW, with two fixes: (1) reconcile the
  privesc-promotion override against INSTRUCTOR_MODE.md's phase-order
  rule (update the doc, don't leave a silent contradiction), (2) fold
  auto-detection into Shoulder Mode once that lands — manual `trinity
  shell --as` stays as the fallback for operators not running it.
- **unlock cards** — NOW, once per milestone (not stapled onto every
  subsequent `next`/`hint`/`box-status` call — cut the redundant
  mentions Cursor added in three places).
- **loot tracker** — NOW, including the professional-report section
  (Alexander confirmed real, needed functionality).
- **stats** — LATER (docket). Correctly hides until first root, but
  doesn't help anyone finish box 1; not worth CLI surface yet.
- **hash classifier** — NOW. Small, local, real value.
- **GTFOBins** — NOW, but scope changed: ingest the FULL public
  GTFOBins dataset (MIT-licensed, git-clonable) via the Update
  Framework rather than hand-writing entries one at a time, then wrap
  it in a thin Trinity-voice layer starting with whichever binaries
  the coach actually surfaces most (sudo/find/vim/etc.), backfilling
  the rest over time. Also: proactively surfaced by the coach when a
  `sudo -l`/SUID finding names a covered binary — not just a passive
  lookup command. Depends on `docs/UPDATE_FRAMEWORK.md` landing first.
- **Methods Index** — NOW, redesigned (see `docs/METHODS_INDEX.md`'s
  updated status section): gated behind Rabbit Hole Detection's stuck
  signal as an escape hatch, not freely browsable; entries can be
  drafted live by the Agent Harness during a stuck session, with
  AI-assisted ranking driving the existing escalating hint ladder
  toward whichever method fits what's already been found. Additive
  only — never removes/overrides existing untried leads.
- **payloads index** — CUT. Redundant with explain/GTFOBins, nobody
  asked for it, five hardcoded links don't earn a CLI verb.
- **journal/achievements** — CUT. Local-only is fine in principle, but
  this is the exact "gamify before the first win" trap 5.9 warned
  about, worse than `stats` because it's framed as unlockable
  achievements.
- **`trinity read`** — CUT outright, not shelved. Directly undoes
  Hole D's fix (steering people toward `watch`, away from one-shot
  parse commands). Don't rebuild this later without revisiting Hole D
  first.
- **rabbit-hole detection** — NOW, rebuilt with real function per
  Alexander's explicit call ("it's supposed to be more of a guidance
  tool... is there any way we can make it more functional?"): trigger
  on a real signal (5+ commands with no new finding, hint ladder
  maxed), point at a specific untouched lead, and — once genuinely
  stalled — offer the Methods Index escape hatch. Not a message
  stapled onto every `next` call.
- **desktop notifications** — NOW. Low risk, real value for catching a
  critical finding in a scrolling feed.
- **AutoRecon teaching** — NOW, elevated to a primary teaching pillar
  (see the updated section below), not a minor graduation nudge.
- **dead-end permission messages** — NOW. Cheap, only fires on
  `skip`, no downside.
- **difficulty-aware guidance** — CUT the wizard question specifically
  (violates "as few questions as honestly possible"); the quiet
  Hard-box reassurance message itself can stay IF difficulty is
  sourced some other way later (platform metadata, not a mandatory
  wizard prompt).
- **report format seam** (`report/render.py`) — NOW. Pure internal
  cleanup, zero user-facing risk, ships regardless of what happens to
  report content features.
- **notebook report format** — NOW as an explicit, opt-in report mode.
  CUT the auto-write into `share-export` (an existing command silently
  gained an unrequested side effect — that's the actual bug, not the
  format itself).
- **professional-mode growth** (`report/attack.py`,
  `report/remediation.py`, engagement-set extras) — LATER (docket).
  Alexander authorized this despite 1.10's freeze, but per his
  follow-up call, educational-loop focus wins for now — ship as its
  own separable commit when it's actually prioritized, not bundled
  into the educational-focused work.
- **rustscan parser** — NOW. Pure additive parser, zero behavior
  change to anything existing.
- **error-pattern seeds (+10)** — NOW, pending Claude's read-through
  per Alexander's "review and ship if you'd have done it the same way"
  instruction.
- **phrasebook growth** — NOW as pure content growth (a few more WHY
  lines). The BROADER phrasebook conversation turned into the Agent
  Harness pivot — see `docs/AGENT_HARNESS.md`, not a phrasebook change
  at all anymore.
- **watch 15-min silence + clipboard copy** — NOW, both. Contained
  inside the dashboard, no new CLI verbs, real quality-of-life value.
  Note: the 15-min silence idea also feeds directly into Shoulder
  Mode's "are you stuck?" check-in — see `docs/SHOULDER_MODE.md`.
- **beginner-track data field** (`platforms.yaml`) — the inert data
  field is fine to keep; do NOT build coach-capping behavior around it
  without a dedicated design conversation (spoiler-risk, same category
  as Methods Index).

**The structural fix that applies regardless of the above:** RESOLVED
— `src/trinity/advisories.py`, not a flat character cap. `trinity
next`'s output was stacking up to eight advisory lines (difficulty
note, wordlist warning, tool warning, did/skip hint, also-worth-trying,
unlock teaser, rabbit-hole nudge, frustration checkpoint, AutoRecon
nudge) — exactly the "Duolingo guilt"/overwhelm failure mode DESIGN.md
exists to prevent, self-inflicted by good individual features with no
traffic control. Alexander explicitly rejected a flat line/character
cap as a band-aid that truncates the pileup without deciding which
advisory matters most. Built instead: `src/trinity/advisories.py`, a
priority-ranked registry of "advisory providers" (rabbit-hole,
unlock-card teaser, difficulty note, AutoRecon nudge) — `next` asks
every provider for its opinion and shows only the single highest-
priority one that has something to say, composed into the WHY
narration as one flowing sentence (reusing phrasebook.py's data-driven
phrase pattern) rather than a stacked bulleted list. Everything else
is silently deferred to a future `next` call, never lost, never shown
alongside the winner. Zero AI — arbitration between known, pre-written
sentences isn't an ambiguity problem, so this stays fully local/
instant/free.

**Known follow-up bug found during live verification (not fixed, not
in scope for the advisory work):** the suggestion engine can emit a
duplicate `enum4linux-ng -A $TARGET` suggestion when two separate SMB
findings (e.g. ports 139 and 445 both being SMB) each independently
trigger the same suggestion rule. Confirmed live via
`process_scan_file` against the lame-style fixture -- two distinct
`finding_id`s (3 and 4) produced byte-identical suggestion text. Needs
a content-level dedup (same command text, not just same finding) in
`suggest/engine.py`'s persistence step, separate task from the
advisory-arbitration work above.

**Notify-storm bug, RESOLVED:** `process_scan_file()` fired one
separate `notify-send` call PER critical-severity finding, not one
per scan -- a real box with 2-3 critical matches in a single nmap scan
(a common shape, not an edge case) produced that many desktop
notifications nearly simultaneously. Fixed: critical match titles are
now collected across the whole scan and batched into exactly ONE
`notify_critical()` call per `process_scan_file()` invocation
("Trinity — N critical matches" with up to 3 titles joined, "…" if
more). Regression test added (`test_process_scan_file_batches_
multiple_criticals_into_one_notification`); live-verified against the
real installed `notify-send` and the `lame_style_scan.xml` fixture
(2 real criticals, confirmed exactly 1 call via mock assertion).

## Wizard: hacker name

New, small, fun addition to the onboarding wizard (not part of the
Cursor prototype batch — Alexander's own idea): ask for a "hacker
name" during setup, and have Trinity refer to the operator by it for
the rest of that install's usage (WHY text, milestone messages, wizard
copy). Purely cosmetic, zero schema risk beyond a new `local_state` key
or a column on `boxes`/a new settings table — small enough to bundle
into whatever session next touches `wizard.py`.

---

## Rabbit-hole detection

Promoted to its own full design doc: see
docs/RABBIT_HOLE_DETECTION.md. Recognizing (and teaching how to
recognize) unproductive rabbit holes is one of the actual core skills
of offensive security, and directly serves the "prevent burnout"
mission — real community research (HTB/THM forum threads) confirms
this is one of the most common, most demoralizing struggles for
beginners.

## AutoRecon — a primary teaching goal, not a minor nudge

Status raised from "nice-to-have graduation nudge" to a stated
priority. Alexander, after this exact conversation: "I HAD NO IDEA
THIS AUTO RECON EXISTED AND IVE BEEN DOING BOXES FOR A YEAR OR MORE. I
REALLY WANT TO MAKE USING THIS TOOL FUNDAMENTAL FOR MY STUDENTS."
AutoRecon (github.com/Tib3rius/AutoRecon) already exists and does
exactly what Trinity deliberately does NOT do — auto-launches the full
battery of follow-up scans the instant a service is found. Alexander's
framing: "we're trying to invite the calculator, not teach long
division" — i.e. once someone understands WHY you run gobuster after
finding HTTP, Trinity should actively teach them a real, well-known
tool that automates that pattern, rather than leaving it as trivia
they might never stumble onto.

Kept fully compatible with the "I do / we do" philosophy by treating
AutoRecon as an available TOOL Trinity teaches about and parses output
FROM — never a tool Trinity invokes on the operator's behalf. Three
independently-buildable pieces, now prioritized as real, near-term
work rather than backlog:

1. **Teach it properly, not as a one-line mention.** A real ELI5
   explain-cache entry set (same mechanism as the existing 86-entry
   library): what AutoRecon is, why it exists, when reaching for it
   makes sense, and how to read its output — written so someone can
   go "as much or as little under the hood" as they want, matching
   Alexander's explicit framing. This should read as an on-ramp into
   a tool that will genuinely make them faster, not a footnote.
2. **Parse its output**, as one more parser alongside nmap/gobuster/
   etc in `parsers/` and `process.py` — AutoRecon's `results/`
   directory has service-broken-out files Trinity could read the same
   way it reads any tool's raw output. Critically, the operator still
   runs `autorecon <target>` themselves in their own terminal pane —
   Trinity reacting to output it didn't generate is identical in kind
   to how it already reacts to nmap/gobuster output.
3. **Graduation nudge, tightened.** RESOLVED. The original one-line
   "you've done this manual pattern N times, try AutoRecon" nudge was
   over-firing (repeated on every `next` call once the threshold was
   crossed) AND was counting completions across ALL boxes globally
   instead of the current box. Both fixed in `graduation.py`:
   `gobuster_completions()` now takes an optional `box_id` to scope
   the count correctly, and `autorecon_nudge()`/`mark_nudged()` track
   a `timeline` event so the nudge fires exactly once per box
   lifetime. `advisories.py`'s `pick_advisory()` only calls
   `mark_nudged()` on the actual winning advisory, never at mere
   detection time -- so a nudge that was eligible but got outranked by
   something more urgent (e.g. a rabbit-hole stuck-signal) stays
   eligible to fire on a later call instead of being silently burned.
   Live-verified: two consecutive `trinity next` calls on the same
   box, nudge shown once, silent on the second call.

This preserves the calculator metaphor correctly: Trinity still never
does the "long division" (running tools) FOR the operator; it becomes
an enthusiastic teacher of a bigger calculator once the operator
understands the arithmetic underneath it — directly serving DESIGN.md's
"get people genuinely excited about hacking" mission, not just its
teaching mission.

## Achievements / gamification system

"Gold star" achievements for each distinct box type / CVE / foothold
method encountered — 100% completion would mean every publicly known
technique category has been hit at least once. Star rating tied to box
difficulty: 1 star = easy box, 2 = intermediate, 3 = hard.

This should be UNIFIED with the earlier "technique journal" idea
(cross-box list of techniques encountered, from the original
brainstorm) rather than built as two separate systems — they're the
same underlying data (which techniques/categories has this operator
been exposed to), just two different presentations of it (a plain list
vs. a gamified completion tracker).

Real dependency to resolve before this can be "100%" in any meaningful
sense: achievements need a finite, canonical taxonomy of known
technique/CVE/foothold categories to measure completion against.
Trinity's existing 7 explain-seed categories (nmap, web enum, SMB/FTP/
SSH, Linux privesc, Windows privesc, reverse shells, searchsploit/
Metasploit) are a reasonable starting skeleton for this taxonomy, but
it should be treated as its own small design task (a canonical
`achievement_categories` list, versioned so new categories can be
added later without invalidating past completion state) rather than
assumed to fall out of existing data for free.

Explicitly confirmed by Alexander: this is a LOCAL, SINGLE-PLAYER,
OFFLINE feature — no leaderboard, no network/social component, no
account system. Shelved for a future build pass (not needed now,
flagged explicitly as avoiding feature creep in the current build),
but when it IS built, it stays local-only, consistent with Trinity's
no-accounts/no-telemetry principles.

## Attack-surface reasoning in the coach's WHY text

Approved as-is, no changes requested. When `coach.py`'s `get_recommendation()`
is next revisited, make the phase-ordering reasoning more concrete and
teach-y — e.g. explicitly explaining why HTTP typically outranks SSH as
a first move ("HTTP gives you dozens of avenues — files, forms,
headers, tech fingerprinting — SSH gives you almost none without
credentials already in hand") rather than only citing phase order in
the abstract. Small, additive change to existing WHY text generation,
not a new subsystem.

## Loot / evidence tracker

Every project (box) needs a proper place to store discovered data as
it's found — credentials, hashes, tokens, flags, anything an operator
uncovers mid-box — accessible throughout the session AND correctly
flowing into the final report/walkthrough, not treated as an
afterthought bolted on post-hoc. Confirmed as real, needed
functionality (not scope creep) — every comparable pentest note tool
(CherryTree, Obsidian OSCP templates, PentestPath) treats this as
first-class, and Trinity currently has nowhere to put it at all.

Needs, when built:
- A `loot` table (box_id, kind [credential/hash/token/flag/other],
  value, context/note, discovered_at) — small, straightforward
  addition to the existing schema shape.
- `trinity loot add`/`trinity loot list` CLI commands.
- `report/data.py`'s `gather_report_data()` extended to include loot,
  and BOTH report templates updated to render it — see the "Report
  depth by mode" entry below for how heavily each mode should treat
  this.
- Logged to the timeline too (event_type: 'loot'), so it's naturally
  chronological alongside everything else, consistent with the
  "timeline is the one shared spine" principle.

## Frustration checkpoints

Approved. After detecting a sustained stuck/frustrated pattern (see
Rabbit Hole Detection above for the actual detection mechanics),
surface genuine encouragement — not empty positivity, but the same
real, specific reassurance found in the actual HTB/THM community
research for this project ("even people with security master's
degrees get stuck for hours on 'easy' boxes — this is normal, not a
sign you're bad at this"). Directly serves the explicit "keep learners
from feeling overwhelmed or burning out" mission. Mechanically, this
is a presentation layer on top of Rabbit Hole Detection's trigger
condition — not a separate detection system.

## Difficulty-aware guidance — unblocked, simpler than first assumed

Originally flagged as depending on the (not-yet-built) platform API
integration. Corrected by Alexander: box difficulty ratings (easy/
medium/hard, or platform-specific equivalents) are PUBLIC, self-rated
by the platform and the community, and easily human-readable/
Google-able — this does NOT require authenticated API access. This
means difficulty-aware guidance ("this one's rated Hard — maybe try an
Easy box first if you're newer") can be built independently and sooner
than previously assumed: either as a simple operator-supplied field at
project-creation time (`trinity`'s wizard could just ask), or later
enriched by a lightweight public-page lookup if that ever becomes
worth automating. No longer gated on platform API/auth work.

## Report depth by mode — professional = full pentest notebook, educational = lighter

Clarified scope split, worth recording precisely: for PROFESSIONAL
mode, Trinity's report is explicitly meant to function as a full
pentest notebook/deliverable — loot, evidence, full findings, the
works — this is now confirmed in-scope, not scope creep, for that
mode specifically. For EDUCATIONAL mode, a polished end-of-session
report matters much less than the live teaching journey itself; it
should stay lighter-weight by design, not attempt notebook-grade
completeness.

Architecture note for whenever the report system is next revisited:
rather than continuing to hardcode exactly two report generators,
consider a small report-plugin interface (`gather_report_data()`'s
output as the stable contract, pluggable renderers consuming it) so
third-party output formats (docx export, a Typst/PDF pipeline, an
Obsidian-vault export, etc — directly inspired by real requests seen
in comparable tools like Obsidian4OSCP wanting Pandoc integration)
could be added later without Trinity's core needing to know about
each one. Not urgent, but worth designing the seam now rather than
retrofitting it once two hardcoded generators have grown into several.

## Omarchy / `trinity lab` tile spawning

Raised in Trinity_suggestions.md 2.10; Claude pushed back; Cursor
agreed this stays out of the main sequencing. Parked here on
purpose rather than given a design doc. Full argument and a
"printed recipe only, no hyprctl" cousin: see
docs/OPEN_DECISIONS.md (`trinity lab` / hyprctl).

## 2.0 GUI — local webserver, not a hosted website

Raised when Alexander asked whether Trinity could become a standalone
website. Answer, recorded here so it isn't re-litigated: **no, not as
a multi-tenant hosted site** — Shoulder Mode needs a real local pty,
Agent Harness invokes the operator's own agent CLI as a local
subprocess, and the whole DB/no-accounts/no-telemetry model assumes
one local SQLite file. All of that requires Trinity to run ON the
student's own machine; a browser tab alone can't do any of it.

The right shape for 2.0's GUI ambition: `trinity web` (or similar)
spins up a local-only webserver (binds `127.0.0.1`, nothing leaves the
machine) and opens `localhost:<port>` in whatever browser is already
installed, rendering the same dashboard/coaching data the Textual TUI
shows today, just as HTML/CSS/JS. Zero backend, zero accounts, same
local-first principles — just a friendlier, more polished rendering
layer than a terminal.

Bonus: this is MORE cross-platform than the current TUI, not less.
Terminal rendering (true color, box-drawing glyphs, pty behavior)
varies a lot across OS/terminal-emulator combos, especially Windows
(ConPTY vs. native cmd/PowerShell vs. WSL). A local web server
rendered in an ordinary browser sidesteps that entirely — the browser
is the most universally cross-platform rendering target available.
Caveat that stays true regardless of UI layer: Shoulder Mode's raw pty
capture (`src/trinity/shoulder.py`) is genuinely OS-coupled today
(Python's `pty` module is Unix-shaped) — porting live terminal capture
cleanly to native Windows is its own separate problem, independent of
whether the UI is a TUI or a local web page.

Also floated: a hosted marketing/docs site (landing page, install
instructions, embedded terminal-recording demo) is fine and separate
from the product itself — that's not the same thing as the product
running remotely, and doesn't conflict with any of the above.

## Social/multiplayer features (leaderboards, shared sessions)

Explicitly NOT pursuing any network/social component at this stage.
Raised only as a brainstorm tangent, not requested by Alexander — kept
here only so it's on record as "considered and declined for now"
rather than silently forgotten, in case it's worth revisiting far in
the future. Would require real backend/network infrastructure Trinity
currently has none of, and cuts against the local-first/no-accounts
design principle unless built very deliberately as opt-in.

# Features Backlog

Status: IDEAS ONLY. Nothing in this document is built. This is where
discussed-but-not-yet-built ideas get recorded so they survive between
sessions, roughly in the order/grouping they were discussed. Promote an
entry to its own design doc (like docs/RABBIT_HOLE_DETECTION.md,
docs/INSTRUCTOR_MODE.md, docs/METHODS_INDEX.md) when it's actually
being scheduled for build.

## Rabbit-hole detection

Promoted to its own full design doc: see
docs/RABBIT_HOLE_DETECTION.md. Recognizing (and teaching how to
recognize) unproductive rabbit holes is one of the actual core skills
of offensive security, and directly serves the "prevent burnout"
mission — real community research (HTB/THM forum threads) confirms
this is one of the most common, most demoralizing struggles for
beginners.

## AutoRecon — teach it, support it, but Trinity itself never runs it

Raised alongside rabbit-hole detection: AutoRecon (github.com/
Tib3rius/AutoRecon) already exists and does exactly what Trinity
deliberately does NOT do — auto-launches the full battery of follow-up
scans the instant a service is found. Alexander's framing: "we're
trying to invite the calculator, not teach long division" — i.e. once
someone understands WHY you run gobuster after finding HTTP, is there
value in making them keep hand-typing that reasoning forever, or
should Trinity teach them a real tool that automates the pattern once
they've earned the understanding?

Recommended resolution (not yet built, worth discussing before
committing to it): keep this fully compatible with the "I do / we do"
philosophy by treating AutoRecon as an available TOOL Trinity can
teach about and parse output FROM — never a tool Trinity invokes on
the operator's behalf. Concretely, this would mean three
independently-buildable pieces:

1. **Teach it as a topic**, same mechanism as the existing ELI5 cache
   — explain what AutoRecon is, when reaching for it makes sense
   ("once you've manually run this pattern a few times and understand
   why, AutoRecon does the same reasoning automatically, faster"), and
   how to read its output.
2. **Parse its output**, as one more parser alongside nmap/gobuster/
   etc in `parsers/` and `process.py` — AutoRecon's `results/`
   directory has service-broken-out files Trinity could read the same
   way it reads any tool's raw output. Critically, the operator still
   runs `autorecon <target>` themselves in their own terminal pane —
   Trinity reacting to output it didn't generate is identical in kind
   to how it already reacts to nmap/gobuster output.
3. **Possibly surface it as a graduation nudge** — after an operator
   has manually run the same enumeration pattern (e.g. HTTP found ->
   gobuster suggested and run) across several boxes, Trinity could
   mention "you've done this manual pattern N times now — AutoRecon
   automates exactly this, worth trying once you're comfortable with
   why it works" — framed as an option, never a replacement.

This preserves the calculator metaphor correctly: Trinity still never
does the "long division" (running tools) FOR the operator; it just
becomes willing to also teach about a bigger calculator once the
operator understands the arithmetic underneath it. Needs a real design
pass before building, similar to Instructor Mode/Methods Index,
particularly around scoping #3 so it doesn't feel like nagging.

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

## Social/multiplayer features (leaderboards, shared sessions)

Explicitly NOT pursuing any network/social component at this stage.
Raised only as a brainstorm tangent, not requested by Alexander — kept
here only so it's on record as "considered and declined for now"
rather than silently forgotten, in case it's worth revisiting far in
the future. Would require real backend/network infrastructure Trinity
currently has none of, and cuts against the local-first/no-accounts
design principle unless built very deliberately as opt-in.

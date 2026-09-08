# Trinity — Design Document

Trinity is a local-first recon copilot for CTF/HTB/THM-style offensive
security practice, **designed to be used alongside an agentic
operating system** (Omarchy/Hyprland is the reference environment,
paired with whatever coding-agent CLI the operator already runs —
Hermes, Claude Code, Codex, or similar). It watches your recon tool
output, matches findings against a local knowledge base, suggests next
commands, and explains anything in plain English — the deterministic
80% of that work for free and instantly, with the operator's own agent
CLI as the ONLY path Trinity ever uses to fill a genuine knowledge gap
(never a hosted API key of its own, never a chat pane — see
`docs/AGENT_HARNESS.md`).

Trinity exists for three reasons, in this order:

1. **Teach.** Let someone crack their first box, with their own hands,
   and build real instincts about how machines get compromised.
2. **Get people genuinely excited about hacking.** Most tools in this
   space read like an RFC had a baby with a compliance checklist.
   Trinity's job is to make the first box feel like a win worth
   chasing another one for — Alexander watched a year of box-cracking
   experience go by without ever hearing about AutoRecon; that gap is
   exactly the kind of thing Trinity should close, with enthusiasm,
   not just accuracy.
3. **Propel the next generation of security professionals into a
   world where agent-vs-agent is the default, not the exception.**
   The next real adversaries will use AI tooling against their
   targets. Someone who learns offensive security fundamentals
   side-by-side with an AI agent from day one — instead of bolting AI
   on after years of manual habits — is better prepared for that
   world than someone who never touches agentic tooling until it's
   forced on them. Trinity is a deliberate on-ramp into agent-assisted
   security work, not a tool that pretends agents don't exist.

Free, open source, MIT licensed. No accounts, no licensing, no paid tier.
Just another tool in a budding cybersecurity person's toolbelt — one
built for the era they're actually entering.

## Core philosophy: drive the car before you build the car

You don't need to understand an engine to enjoy driving — curiosity
about what's under the hood comes later, once the fun has already
hooked you. Trinity is built on the same idea: let someone crack their
first box and feel the win *before* they have to understand TCP
handshakes, HTTP methods, or CVE databases. The knowledge is all still
there, available the moment curiosity kicks in — Trinity just refuses
to make understanding-the-engine a precondition for driving-the-car.
Every design choice below (the wizard's minimal first-run questions,
graduated hints instead of instant answers, mode as a lens rather than
a gate) exists in service of this one idea.

## The problem this solves

Working a CTF/HTB box today means constant context-switching out to
Google or an AI chat window for things that are actually deterministic —
"this exact FTP version has a known backdoor" is the same answer every
single time someone hits it. That costs money (if you're pasting scan
output into an AI) and breaks flow (if you're Googling). Trinity moves
the deterministic 80% of that lookup work onto your own machine, for
free, instantly, so AI only gets involved for the genuinely novel 20%.

## Core architecture principles

**Local-first, agent-assisted, never a chat pane.** Every finding gets
checked against a local SQLite knowledge base (with full-text search)
and a live, offline ExploitDB lookup (via `searchsploit`) before
anything is ever considered for escalation. When a genuine knowledge
gap remains, Trinity hands a tight, specific question to the
operator's own agent CLI (see `docs/AGENT_HARNESS.md`) — never a
hosted API call of its own, never an in-app chat box. The answer gets
reviewed once, then cached permanently, so the same gap is never paid
for twice. This is a deliberate escalation path, not a fallback we're
ashamed of: an agent-assisted tool used by an agent-fluent generation
should use its agent well, just never as a crutch that replaces local
lookups Trinity can already do for free.

**Mode is a lens, not a fork.** Trinity has two output modes —
`educational` (a narrated walkthrough, written to teach) and
`professional` (kept only because pentest-report formatting is a useful
muscle, even without a commercial angle). Both read from one shared,
chronological `timeline` table that every part of the system writes
through. Mode only changes *how* that timeline is formatted at report
time — never what gets collected. This keeps the two modes from
drifting apart into two different codebases over time.

**Everything traceable to its source.** Every KB entry, every cached
command explanation, every match carries a `source` field
(`user_curated`, `trinity_preseed`, `searchsploit`, `ai_escalation`,
...) and — where meaningful — a severity rating. Nothing is presented
with false confidence; fuzzy searchsploit matches are visibly fuzzy, not
dressed up as certainties. Note the two "not-from-the-operator"
sources aren't interchangeable: `user_curated` means a person (project
maintainer or contributor) wrote and vouches for this specific entry;
`trinity_preseed` means it was bulk-authored as part of a themed batch
(e.g. the 86-entry ELI5 library) — both are still hand-written, not
AI-generated, but `user_curated` implies a closer, one-at-a-time review.

## The "I do / we do" philosophy — dual-pane by design

Trinity deliberately does **not** run your recon tools for you. The
student runs `nmap`, `gobuster`, `searchsploit`, etc. themselves, in
their own terminal, with their own hands — building the real muscle
memory of what a live scan actually looks like. Trinity's job is to sit
in a second terminal pane, watch the output land, and narrate what it
means, live — "I do" (Trinity explains and shows) running alongside "we
do" (the student runs the real thing) in real time, side by side.

This maps directly onto a tiling window manager (Omarchy/Hyprland is
the reference environment, though nothing about Trinity is
Omarchy-specific): one tile is the student's real terminal, the
adjacent tile is Trinity's live-updating dashboard, both visible at
once. Watch-mode (see Roadmap) reacts to new scan files the moment
they're saved. **Full terminal-session visibility** (see
`docs/SHOULDER_MODE.md`) goes further: in the dual-pane setup, Trinity
records the student's own working pane the same way `script` does,
so it can genuinely watch privesc attempts, shell landings, and
foothold progress happen — "looking over your shoulder," not just
reacting to files dropped in a directory. This is an intentional,
explicit reversal of an earlier, more cautious design decision (see
`docs/OPEN_DECISIONS.md`'s "Shell-history sensors" entry) — Alexander
decided the hand-holding value of Trinity genuinely seeing what's
happening outweighs the more conservative posture we started with.
The recording only ever happens in the pane the operator explicitly
started `trinity watch`/`shoulder` against; Trinity never reaches into
unrelated terminals or reads persistent shell history files.

This shapes every future feature decision: anything that would replace
the student doing the actual work, INVISIBLY OR BY DEFAULT (auto-
running exploits, auto-solving a box) is explicitly out of scope.
Trinity teaches and assists — up to and including watching closely and
reacting in real time — but it does not silently do the box *for* you.

**2026-09 update — a narrow, explicit, disclosed exception exists.**
Show Me Mode (`docs/SHOW_ME_MODE.md`) reverses part of this for
genuine capability-gap cases: Trinity's own agent may execute a
solve attempt live, in ITS OWN separate session/window against the
target — never the student's own terminal — then hands the student
the exact working recipe to run themselves. Nothing counts as
progress, and nothing enters the student's own report/timeline, until
the STUDENT runs it in their own window. This is "watch a worked
example, then do it yourself," not "AI silently does your homework" —
the rail this section protects is against invisible/automatic
solving, not against a disclosed, always-available, opt-in worked-
example feature the student explicitly invokes. See
`docs/OPEN_DECISIONS.md`'s "Auto-run scans or exploits" entry for the
full reasoning and the explicit Decision.

## Platform-agnostic by design

HTB and TryHackMe are the most visible platforms, but they are two of a
large field — PortSwigger Web Security Academy, OverTheWire,
PentesterLab, VulnHub, picoCTF, Root-Me, CyberDefenders, Proving
Grounds, and any number of university-run CTFd instances. Trinity does
not hard-code platform identity as a fixed enum. Instead:

- A **platform registry** (`platforms.yaml`, shipped with Trinity) —
  one entry per known platform: id, display name, theme colors, an
  optional API endpoint for pulling box metadata, and a scope-hint
  describing how that platform defines "in scope" (HTB/THM: VPN + a
  specific target IP; PortSwigger: web-only against their own domains;
  OverTheWire: SSH to named wargame hosts; etc.).
- A **local override file** lets anyone add a platform Trinity doesn't
  ship with — a university's private CTFd instance, a personal lab —
  without touching Trinity's own source.
- New platforms can also be contributed upstream via a normal PR,
  exactly like the KB and explain-seed libraries below.

## Themed CLI presentation

A small, colored Rich panel/rule shows the active platform's theme
(colors pulled from the platform registry) when working a box — HTB
green-on-black, THM dark red, unrecognized platforms fall back to
Trinity's own neutral palette. Deliberately simple: a colored banner
line, not a splash screen. Trinity does **not** reproduce any
platform's actual logo or wordmark in the repo — color-palette-inspired
theming only, to stay clear of trademark issues in a public OSS project.

## Crowdsourcing model

The knowledge base, the explanation library, and the platform registry
are all just structured data files. Like GTFOBins or
PayloadsAllTheThings, they're meant to grow through community
contribution — a PR adding "here's the technique for X" or "here's our
university's CTFd platform entry" is a low-friction, high-value way for
the community to extend Trinity faster than any single maintainer could.

## What's built so far

- **Parsers** (local, zero-token): nmap (XML), gobuster (dir-mode text),
  ffuf (JSON), nikto (JSON), whatweb (JSON Lines), enum4linux-ng (JSON).
- **Local knowledge base**: SQLite + FTS5, hand-curated seed entries,
  live `searchsploit` integration as a match-engine stage (verified
  against real ExploitDB data — correctly surfaces CVE-2011-2523 for
  vsftpd 2.3.4, the real Samba `username map script` RCE, etc.).
- **Severity rating**: deterministic keyword heuristic + a CVSS-score-
  to-band mapper for when a real CVE/CVSS feed is wired in.
- **Suggestion engine**: deterministic next-command suggestions based on
  what's open on a box (HTTP → gobuster, SMB → enum4linux-ng, etc.),
  deduped per box.
- **ELI5 explanation cache**: `command_explanations` table, 86
  pre-authored entries across 7 categories (nmap, web enum, SMB/FTP/SSH,
  Linux privesc, Windows privesc, reverse shells, searchsploit/
  Metasploit usage) front-loaded so the cache is useful from a fresh
  install, not just after weeks of organic use.
- **Reports**: educational (narrated walkthrough) and professional
  (structured findings report), both reading off one shared `timeline`.
- **Watch-mode TUI dashboard** (`trinity watch`): a Textual app that
  watches a working directory and auto-parses/matches new scan output
  the moment it's saved — the technical mechanism behind the dual-pane
  workflow. Proven live against a real fixture scan.
- **Onboarding wizard** (`trinity` with no arguments): first-run intro,
  then a startup menu (resume active project / start new / re-run
  setup). Mode (educational/professional) is chosen per-project. Real
  VPN detection (`tun`/`tap`/`wg` interfaces) rather than trusting the
  operator's word, platform-aware so non-VPN platforms aren't told to
  run OpenVPN.
- **Platform registry** (`platforms.yaml` + local override support):
  HTB, THM, PortSwigger, OverTheWire, VulnHub, picoCTF, Root-Me,
  generic CTF, and "other" shipped by default. Each carries theme
  colors and a VPN-need flag. `trinity theme` previews a platform's
  colors or (`--omarchy`) the operator's live Omarchy desktop theme.
- **Box lifecycle**: `trinity box-status` marks a project active/
  rooted/abandoned; rooting a box correctly clears it from the
  wizard's "resume" state.
- **Opt-in data sharing scaffold** (`trinity share-export`): exports a
  box's AI-escalation-sourced explanations and unmatched findings as
  an anonymized local file for manual review/contribution — never an
  automatic network push.
- **LICENSE (MIT), CONTRIBUTING.md** — real, not just promised.
- **Tool-availability checks**: `tools.py` registry checks whether a
  suggestion's required binary is actually installed before the coach
  recommends it, and surfaces real per-platform install guidance
  (apt/pacman/brew) if not — the operator installs it themselves, then
  the exact same recommendation reappears automatically on the next
  `trinity next`, no state lost.
- **227 unit tests**, all passing.

## Roadmap

**Active Cursor homework (filed 2026-09-07, not started):**
[docs/CURSOR_HOMEWORK.md](./docs/CURSOR_HOMEWORK.md) — coverage
simulation, AD engine prototype, then AD-specific simulation.
Those three specs are the assigned build/test work. They do not
replace the design-doc queue below.

**Built: Instructor Mode.** [docs/INSTRUCTOR_MODE.md](./docs/INSTRUCTOR_MODE.md)
describes and remains the reference for the coach layer that closes
the gap between "wizard hands off a box" and "operator has no idea
what to type next": a ranked `trinity next` recommendation (not just a
flat suggestion list), graduated hints (`trinity hint`: nudge →
stronger nudge → full answer), and an error-diagnosis cache (`trinity
error`/`trinity cache-error`) that makes "why didn't this work" free
and instant over time, the same way the ELI5 cache already did for
"what does this command do." Professional mode gets the same
recommendations with the teaching narration stripped.

**Next, three foundational design docs — build in this order, each
gates the next:**

- **[Update Framework](./docs/UPDATE_FRAMEWORK.md)** — the plumbing
  underneath everything else below: silent, automatic sync of every
  external data source (GTFOBins, ExploitDB, PayloadsAllTheThings,
  platform metadata, and Trinity's own reviewed self-generated
  knowledge) on every launch, plus the intake/review pipeline that
  gates anything before it's trusted. Build first — GTFOBins
  ingestion, the Agent Harness's knowledge growth, and Methods Index's
  live-drafted entries all plug into this rather than each inventing
  their own sync logic.
- **[Agent Harness](./docs/AGENT_HARNESS.md)** — the core mechanism
  that makes Trinity's local knowledge base *grow*: when a genuine gap
  exists, Trinity hands a tight question to the operator's own agent
  CLI (Hermes/Omarchy's default agent first, any detected agent CLI
  otherwise, manual copy-paste as the fallback with no agent present),
  reviews the answer through the Update Framework's intake queue, and
  caches it permanently. This is also the mechanism behind Methods
  Index's live-drafted method entries and GTFOBins' proactive coach
  integration.
- **[Shoulder Mode](./docs/SHOULDER_MODE.md)** — full terminal-session
  visibility into the operator's own working pane (not just file
  watching), so Trinity can genuinely notice shell landings, privesc
  attempts, and foothold progress instead of asking the operator to
  self-report every milestone.

**Then, revised in light of the above:**
- **[Methods Index](./docs/METHODS_INDEX.md)** — a citation-based
  index of the *different* enumeration/foothold/privesc methods used
  across public writeups for a given (retired) box. Originally
  freely-browsable; now gated behind Rabbit Hole Detection's
  stuck-signal as an escape hatch (protects the first-attempt
  experience), and entries can be drafted live by the Agent Harness
  during a stuck moment (with citation/review safeguards) rather than
  only pre-authored offline.
- **[Rabbit Hole Detection](./docs/RABBIT_HOLE_DETECTION.md)** —
  recognizing (and teaching how to recognize) unproductive rabbit
  holes. Rebuilt to actually DO something on trigger (point at a
  specific untouched lead, offer the Methods Index escape hatch) —
  not just print a reassuring message.

**After that, roughly in priority order:**
- GTFOBins full local dataset (ingested via the Update Framework, thin
  Trinity-voice wrapper layer, proactively surfaced by the coach when
  a `sudo -l`/SUID finding names a covered binary) — see
  `docs/OPEN_DECISIONS.md` for the sequencing note.
- `trinity stats` — progress/streak tracking read straight off the
  existing timeline data (boxes rooted, techniques hit, current streak)
  — held until a real prioritization pass; hidden until the operator's
  first rooted box either way, so it never reads as a scoreboard for
  a game not yet won.
- Real packaging (PyPI) so installation is `pip install` instead of a
  git clone + `uv run`.

See **[docs/FEATURES_BACKLOG.md](./docs/FEATURES_BACKLOG.md)** for
further discussed-but-unscheduled ideas — recorded there so they
aren't lost between sessions, promoted to their own design doc once
actually scheduled.

## Explicitly out of scope

- Any paid tier, account system, or licensing gate.
- Auto-running exploits or auto-solving boxes BY DEFAULT OR SILENTLY —
  Trinity assists, the student does the work. **Narrow, explicit
  exception:** Show Me Mode (`docs/SHOW_ME_MODE.md`) lets Trinity's
  own agent attempt one step live in ITS OWN session against the
  target, always visible, always operator-invoked, never the
  student's own terminal, never counted as the student's own work
  until they run it themselves. See `docs/OPEN_DECISIONS.md`.
- Reproducing any platform's trademarked logo/branding.
- Hard restrictions on what platforms can be used — the registry is
  meant to be extended, not to gatekeep.
- Scraping/storing full third-party writeup text, or indexing anything
  paywalled/subscription-gated — see Methods Index above for the
  citation-based alternative that's actually planned.

The *why* behind each rail, the constrained cousins that might
still be discussable, and blank decision/notes fields for later
review live in
**[docs/OPEN_DECISIONS.md](./docs/OPEN_DECISIONS.md)**. That file
is a working memo, not a change to this list.

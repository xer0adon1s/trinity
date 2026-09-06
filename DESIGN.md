# Trinity — Design Document

Trinity is a local-first recon copilot for CTF/HTB/THM-style offensive
security practice. It watches your recon tool output, matches findings
against a local knowledge base, suggests next commands, and explains
anything in plain English — almost all of it for free, without ever
calling an AI model, because it's not guessing: it's looking things up.

Free, open source, MIT licensed. No accounts, no licensing, no paid tier.
Just another tool in a budding cybersecurity person's toolbelt.

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

**Local-first, AI as last resort.** Every finding gets checked against a
local SQLite knowledge base (with full-text search) and a live, offline
ExploitDB lookup (via `searchsploit`) before anything is ever considered
for AI escalation. When escalation genuinely is needed, Trinity builds a
tight, specific question — never a full scan dump — to keep the token
cost as small as the question actually is.

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
once. Watch-mode (see Roadmap) is the technical feature that makes this
work — a filesystem watcher on the working directory that notices a new
scan file the moment it's saved and reacts automatically, with no
command needed to tell Trinity to look.

This shapes every future feature decision: anything that would replace
the student doing the actual work (auto-running exploits, auto-solving
a box) is explicitly out of scope. Trinity teaches and assists; it does
not do the box *for* you.

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
- **175 unit tests**, all passing.

## Roadmap

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

**Next, with its own design doc:**
- **[Methods Index](./docs/METHODS_INDEX.md)** — a crowdsourced,
  citation-based index of the *different* enumeration/foothold/privesc
  methods used across public writeups for a given (retired) box, so
  learners see the range of valid approaches instead of fixating on
  one. Built from short, Trinity-authored paraphrases with mandatory
  author + source-URL attribution — never scraped/stored writeup text.

**After that, roughly in priority order:**
- **[Rabbit Hole Detection](./docs/RABBIT_HOLE_DETECTION.md)** —
  recognizing (and teaching how to recognize) unproductive rabbit
  holes, one of the biggest real skills and pitfalls named in actual
  HTB/THM community discussion. Read-only pattern analysis over the
  existing timeline, surfaced as a gentle nudge from `trinity next`.
- `trinity stats` — progress/streak tracking read straight off the
  existing timeline data (boxes rooted, techniques hit, current streak)
  — directly serves the "keep learners from feeling overwhelmed or
  burning out" goal.
- HTB/THM (and other platforms', where available) API integration to
  auto-pull box metadata instead of typing `--box`/`--platform` by hand.
- Deeper KB coverage: GTFOBins and PayloadsAllTheThings ingestion for
  privesc/technique matching beyond what `searchsploit` covers well.
- Real packaging (PyPI) so installation is `pip install` instead of a
  git clone + `uv run`.

See **[docs/FEATURES_BACKLOG.md](./docs/FEATURES_BACKLOG.md)** for
further discussed-but-unscheduled ideas (achievements/gamification,
AutoRecon teaching integration, loot/evidence tracking, frustration
checkpoints, and more) — recorded there so they aren't lost between
sessions, promoted to their own design doc once actually scheduled.

## Explicitly out of scope

- Any paid tier, account system, or licensing gate.
- Auto-running exploits or auto-solving boxes — Trinity assists, the
  student does the work.
- Reproducing any platform's trademarked logo/branding.
- Hard restrictions on what platforms can be used — the registry is
  meant to be extended, not to gatekeep.
- Scraping/storing full third-party writeup text, or indexing anything
  paywalled/subscription-gated — see Methods Index above for the
  citation-based alternative that's actually planned.

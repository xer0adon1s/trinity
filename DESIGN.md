# Trinity — Design Document

Trinity is a local-first recon copilot for CTF/HTB/THM-style offensive
security practice. It watches your recon tool output, matches findings
against a local knowledge base, suggests next commands, and explains
anything in plain English — almost all of it for free, without ever
calling an AI model, because it's not guessing: it's looking things up.

Free, open source, MIT licensed. No accounts, no licensing, no paid tier.
Just another tool in a budding cybersecurity person's toolbelt.

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
dressed up as certainties.

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
- **65 unit tests**, all passing.

## Roadmap

**Next: watch-mode TUI dashboard.** The technical centerpiece of the
dual-pane workflow — a Textual app that watches a working directory,
auto-parses any new/changed scan output the moment it lands (no manual
`trinity parse-*` invocation needed), and live-updates a suggestion feed
next to the student's real terminal pane. Built around the platform
registry and theming above.

**Then, roughly in priority order:**
- Platform registry + theming (small foundation piece, built just before
  or alongside watch-mode since the dashboard displays it).
- Graduated hints in educational mode — nudge → stronger nudge → full
  answer, instead of today's all-or-nothing `trinity explain`.
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
- LICENSE (MIT), CONTRIBUTING.md, public GitHub repo.

## Explicitly out of scope

- Any paid tier, account system, or licensing gate.
- Auto-running exploits or auto-solving boxes — Trinity assists, the
  student does the work.
- Reproducing any platform's trademarked logo/branding.
- Hard restrictions on what platforms can be used — the registry is
  meant to be extended, not to gatekeep.

# Open decisions — DO NOT list and adjacent prototypes

Status: **UNDECIDED.** Cursor wrote the understanding below so
Alexander can review it later, add thoughts, and say what (if
anything) to implement. Nothing in the "might prototype" column
is approved. Nothing in the "still a rail" column should be
coded unless this file is updated to say so.

Source of the original vetoes:
`docs/CLAUDE_CURSOR_DEBATE.md` Part E (MUST / SHOULD / DEFER /
DO NOT) and `~/Downloads/Trinity_suggestions.md` §4.3.

This is not a replacement for DESIGN.md's "Explicitly out of
scope." That list stays the public product rails. This file is
the working memo for *why* each rail exists, what a constrained
cousin would look like, and where Alexander's call still sits.

How to use this file: under each item, add a **Decision** line
(`implement / adjacent only / never / revisit`) and any notes.
Do not treat Cursor's "I would not" as final — it is one side
of the argument, written so the other side can answer it.

---

## How to read the categories

**Rail.** Implementing the thing as described changes what
Trinity is (tokens, surveillance, Trinity-runs-the-box,
Trinity-runs-the-WM). Cursor's standing advice: do not
prototype these even as drafts.

**Adjacent.** Same *need* as the banned idea, different
mechanism, already partly in the tree or cheap to draft
without crossing the rail. Still needs an explicit yes.

**Net-negative.** A small alias or toggle that looks harmless
and makes Hole F or a fixed bug worse.

---

## LLM / chat pane

**Reversed in part — see `docs/AGENT_HARNESS.md`. The narrow adjacent
below is now the actual design, not just a fallback.**

The temptation after Instructor Mode is “just let them talk to
it.” In this project that means Trinity itself calling a model,
or growing an in-app chat that does. The whole local-first bet
is that explain, error, KB, and hints are lookups, not guesses.
The moment a chat box is the path of least resistance, people
stop filling the caches and the product becomes a thin wrapper
around tokens.

**Decision: implement, as designed in `docs/AGENT_HARNESS.md`, not as
originally vetoed.** Alexander's 2026-09 pivot: Trinity is explicitly
designed to be paired with an agentic OS, and the Agent Harness is the
mechanism that lets Trinity's local knowledge base grow by calling out
to the OPERATOR's OWN agent CLI (Hermes/Claude Code/etc.) for a
bounded, specific question on a genuine cache miss — never a hosted
API key Trinity holds itself, never a free-form in-app chat pane. The
answer is reviewed via the Update Framework's intake queue before it's
trusted, then cached permanently. See `docs/AGENT_HARNESS.md`'s "What
this is NOT" section for the precise line that's still held: no
Trinity-owned API key, no chat UI, no silent trust of a returned
answer. This is a narrower reversal than "add AI" — it's "let the
operator's own already-running agent do the escalation Trinity already
did manually, and make the result permanent."

**Alexander's notes:** "everything you describe seems in line with
what i want... this is the NEXT GENERATION of hacking. is agent v
agent and we need to get people excited about how these tools work."

---

## Auto-install

**Rail for Trinity running the package manager. Adjacent is
mostly already shipped.**

Today Trinity can say “gobuster is missing; on Arch run `sudo
pacman -S gobuster`.” Auto-install would be Trinity running
that (or `apt` / `brew`) on their behalf, maybe behind
`--yes`. That is a different trust class from parsing a scan
file or shelling out to read-only `searchsploit`. It mutates
the system, needs privileges, and can install the wrong
package if the registry is stale.

The constrained cousin is not silent install. It is a
confirmation that *prints* the exact command and waits for
them to run it in their pane, then re-checks `PATH` — which is
almost what `trinity next` already does when `tool_missing` is
set. A real `sudo` spawned by Trinity is the rail.

**Decision:** still a rail. Unchanged by the 2026-09 pivot — Agent
Harness/Shoulder Mode reversed the AI-involvement and
terminal-visibility rails specifically; system mutation via package
managers was not part of that conversation and stays vetoed.

**Alexander's notes:**


---

## Auto-run scans or exploits

**Reversed in part — see `docs/SHOW_ME_MODE.md`. Trinity's own agent
may execute a live solve attempt, but in ITS OWN separate session,
never the student's terminal, and never counted as the student's work
until they run the resulting recipe themselves.**

Trinity recommending `nmap -sC -sV -oX scan.xml $TARGET` is
in scope. Trinity starting that nmap, or firing an exploit
module, is Trinity doing the box. The imagined prototype is
“watch is up, no file in 15 minutes, so just run the pending
command.” That is exactly the silence reminder already in the
watch dashboard — except the dangerous half (exec).

A dry-run that shows argv and refuses to exec is just
`trinity next` again. Cursor would not prototype a runner.

**What changed:** the original veto was written before Trinity was
explicitly conceived as pairing with an agentic OS (see DESIGN.md's
2026-09 rewrite). Alexander's call: some retired boxes genuinely
require live exploitation Trinity's static match/suggest engine cannot
walk a student through (BloodHound-style AD path analysis, multi-step
credential chains) — those boxes are permanent dead ends without SOME
escape hatch, and the honest fix is a disclosed one, not silently
telling a stuck student "sorry, can't help." Alexander's explicit
framing, verbatim: Show Me Mode should be **break-glass in philosophy,
but always accessible in the tool** — not gated behind proving you're
"stuck enough" first, because that gate doesn't stop a determined
cheater (they'd just ask their own AI directly, bypassing Trinity
entirely) and only adds friction for legitimate use. "We're trusting
people to use this the right way. If they were going to cheat they'd
just use AI to solve everything anyway."

**The key mechanical distinction that makes this a narrower reversal
than "Trinity solves boxes":** the agent's live execution happens in
its OWN session/pane against the target, never injected into the
student's own terminal. Nothing is added to the student's own
timeline/report as their own work until the STUDENT runs the resulting
recipe themselves, in their own window. This is "watch a worked
example, then do it yourself" — closer to a textbook worked example
than to an autograder solving the homework. The rail this entry
protects against is invisible/automatic/default solving; a disclosed,
always-available, operator-invoked worked-example feature is a
different thing, same as Agent Harness (below) was found to be a
narrower reversal than "add AI chat" once precisely specified.

**Also explicitly decided:** no hardcoded per-box "is this a legit
practice target" allowlist. Every comparable offensive-security tool
(Metasploit, Burp, nmap, Cobalt Strike) relies on the operator's own
authorization/ToS agreement, not a built-in target bouncer — a
hardcoded allowlist would hold Trinity to a stricter standard than the
industry it models itself on, and it's mechanically defeatable anyway
(Trinity's platform registry is user-extensible by design). Show Me
Mode instead requires an explicit authorization attestation (same
legal shape as any pentest tool's terms-of-use acknowledgment, logged
once), not a curated box list.

**Decision: implement, as designed in `docs/SHOW_ME_MODE.md`** — own-
session execution, always-available (no stuck-detection gate), full
per-invocation disclosure, report tagging that cannot be suppressed,
authorization-attestation gate (not a hardcoded target allowlist).
Auto-run into the STUDENT's own terminal remains a hard rail; that
part of the original veto stands unchanged.

**Also decided: Show Me Mode IS Assimilator (`docs/ASSIMILATOR_PROJECT.md`),
triggered live.** These are not two features — one engine
(diagnose/hypothesize/verify/land a fix), two triggers: Doc's offline
batch sweep of the Coverage Sim corpus, and a student's live
`trinity show-me` invocation against a real box. Both feed the same
leverage ledger and the same Update Framework review queue. Recorded
here so a future session doesn't treat them as separate systems that
happen to share code.

**Alexander's notes:** "its break glass in philosophy, but always
accessible in a tool. We're trusting people to use this the right way.
if they were going to cheat they would just use AI to solve
everything. thats my thinking." / "we're trusting that people are
using our terms not hard coding a preventitive. just like every other
cybersec tool." / "trinity would run those commands in HER OWN
WINDOW, not the user window. once it works, user would do it in their
window."

---

## Nuclei / AutoRecon / nmap-automator launchers

**Rail for launchers. Adjacent is teach + parse; teach is
already drafted.**

Those tools *are* the “do the whole battery” calculators.
FEATURES_BACKLOG already framed AutoRecon correctly: invite
the calculator after the operator understands the arithmetic;
never run it for them. An ELI5 seed and a graduation nudge
after N manual gobusters are drafted. A launcher would be
`autorecon $TARGET` or `nuclei -u …` from Trinity.

If more of this *family* is wanted, the next honest prototype
is an AutoRecon *parser* (read `results/` files they produced),
not a spawn. Nuclei-as-parser is the same pattern. Nuclei-as-
launcher is auto-run with a flashier binary.

**Decision:** _unset_

**Alexander's notes:**


---

## Metasploit RPC

**Rail for session ownership. Adjacent is another parser.**

RPC means Trinity opening msfrpcd, setting RHOST, and owning
the session list. DESIGN already teaches `searchsploit` and
has ELI5 for `msfconsole` / `sessions -i`. RPC is Trinity
driving the framework.

The bounded cousin: the operator pastes `msfconsole` output or
a session list and Trinity narrates it — a parser, no socket.
Cursor would not prototype a connection to Metasploit.

**Decision:** _unset_

**Alexander's notes:**


---

## Scrape writeups / live `methods-fetch`

**Rail for unattended fetch-and-summarize, especially
mid-session. Adjacent is the Methods Index read-side, already
drafted.**

`docs/METHODS_INDEX.md` is a citation index of *retired*
boxes: Trinity-authored one-to-two sentence paraphrases,
mandatory author + URL, no stored prose, no paywalled
sources. The banned half is the live pipeline: search the
web, fetch writeups, extract in-session. That is both a
copyright problem and a spoiler problem (box 1 protection).

The read side against hand-authored YAML (`trinity methods`,
`methods_index/lame.yaml`) is the allowed shape. A further
adjacent that stays legal is still not a scraper: more
hand-authored YAML, or an offline human-gated import that
refuses to save anything without `author` + `source_url` and
never runs during `watch`. Unattended fetch-and-summarize of
third-party pages stays a rail. Same rail covers HTB official
writeup APIs and scraping HackTricks / IppSec transcripts
(suggestions §4.3).

**Decision:** _unset_

**Alexander's notes:**


---

## `trinity lab` / hyprctl / tile spawning

**Rail for spawning tiles. Adjacent is a printed recipe or
detect-only.**

The idea: one command opens watch on the right and a shell on
the left, maybe with nmap in the clipboard; Hyprland-native
with tmux/zellij fallback. Vetoed because Trinity does not
orchestrate the operator's environment — dual-pane is a
habit, not a feature. Detect-don't-require does not save it;
`hyprctl dispatch` is issuing WM commands. Claude pushed back
in the debate; Cursor agreed and asked this stay out of the
main sequencing.

If insisted on, the only cousin Cursor would consider is
documentation plus a printed recipe (“split your tiles like
this; here is the nmap line”), or detecting that two tiles
already exist and saying so. Not spawning windows. Debate
also said park this in FEATURES_BACKLOG rather than
design-doc it as if it were scheduled.

**Decision:** _unset_

**Alexander's notes:**


---

## Shell-history sensors

**Reversed, but via a DIFFERENT mechanism — see
`docs/SHOULDER_MODE.md`. Reading persistent shell history files is
STILL rejected; live pty session capture in an explicitly-started
pane is the new, approved mechanism.**

Read `~/.bash_history` / zsh history to notice they ran the
suggested command and auto-`did` it. That would close Hole A
without `d` / `did`, but it is surveillance-shaped, fragile
across shells, and easy to lie about (history off, another
user, timestamps). This specific mechanism (reading a persistent
history FILE after the fact) remains rejected — it's a genuinely bad
signal regardless of the broader visibility question below.

**What changed:** Alexander explicitly asked for Trinity to "see over
our shoulder" in the operator's own working pane, in real time —
"that's the whole point... i want it to spy though." `docs/
SHOULDER_MODE.md` designs this as a live `pty`-based session capture
(same category as `script(1)`) in the ONE pane the operator explicitly
started Trinity's watch/shoulder mode against — not a read of
persistent history files, not a reach into unrelated terminals. This
is a hard requirement in the dual-pane setup per Alexander's call, not
an opt-in toggle.

**Decision:** implement, as designed in `docs/SHOULDER_MODE.md` —
live pty capture of the explicitly-watched pane, milestone/finding
extraction feeding the existing timeline/coach pipeline. Persistent
shell-history-file reading remains explicitly out of scope; that part
of the original veto stands.

**Alexander's notes:** "I thought we were making Trinity be able to
'see' everything happening in the 2nd terminal... trinity can see
'over our shoulder' the whole time... i want it to spy though. that's
the whole point is that it's holding our hand by watching what we do
and noticing things throughout."

---

## Re-rank `next` around missing tools

**Net-negative / rail. The allowed surface is already built.**

If gobuster is the right move and missing, skip to whatever
is on `PATH`. That trains “work around a hole in the kit”
instead of “install the tool and come back.” Circle-back
without new state is one of the best designs in the tree
(coach re-reads the same un-accepted row).

The allowed surface: keep gobuster on top, show install
guidance on `next`, still list `also_worth_trying` with
`(tool not installed)`. Cursor does not think this item has
a good prototype. The nearby useful work is richer install
copy, not reordering.

**Decision:** _unset_

**Alexander's notes:**


---

## Install guidance on hint L1/L2

**Net-negative. Would reopen a fixed leak.**

`next` may name the tool. `hint` is Socratic: L1 and L2 must
not name gobuster or say “install gobuster,” because that
*is* the answer. Current code shows install at L3, or
immediately in professional mode (mode is a lens). Putting
install copy on L1/L2 reopens the same principle-5 hole as
dumping `rationale` into L2.

Professional mode already shows install immediately. That is
the correct place, not a ladder bug.

**Decision:** _unset_

**Alexander's notes:**


---

## `trinity stuck`

**Net-negative alias. Hole F.**

Proposed as a third verb meaning “give me a hint.” `hint`
already means I’m stuck. An alias looks cheap and grows the
verb list the wizard must not teach. The *feeling* of stuck
is rabbit-hole copy on `next` (drafted) or a watch key, not
a twentieth command.

**Decision:** _unset_

**Alexander's notes:**


---

## Social / leaderboards / shared sessions

**Rail for network/accounts. Adjacent is local journal/stats,
already drafted.**

Accounts, a server, other people’s streaks. Explicitly
declined in FEATURES_BACKLOG. Fights local-first /
no-telemetry.

The local cousin is `trinity journal` / `trinity stats`:
single-player, offline. The only extra Cursor would even
discuss is *opt-in* share-export of achievement IDs with no
names — still a local file, still not a network. No backend.
No multiplayer session.

**Decision:** _unset_

**Alexander's notes:**


---

## Teach the whole CLI in the wizard (Hole F)

**Product rule, not a feature ticket.**

Wizard teaches watch + one nmap line, not `did` / `skip` /
`loot` / `methods`. “More helpful wizard copy” that names
twelve verbs is how box 1 dies. The safe cousin is grouping
`--help` for power users, which is still not scheduled as a
must.

**Decision:** _unset_

**Alexander's notes:**


---

## Strip professional mode

**Rail in the opposite direction. Already overridden the
other way.**

Debate 5.2 / 5.10: shrink what we *talk about*, do not delete
what exists. Alexander later authorized professional-mode
*growth* (document control, exec summary, ATT&CK drafts,
remediation drafts). Do not strip the mode from the tree.

**Decision:** keep the mode (already the standing call)

**Alexander's notes:**


---

## Coherent adjacent set (if anything from this file is
scheduled)

These are the only DO NOT-adjacent prototypes Cursor thinks
are even coherent. Still not approved — listed so a later
session does not “helpfully” invent a launcher.

1. AutoRecon / nuclei / msf as **parsers**, not launchers.
   (AutoRecon *teach* is drafted; parser is not.)
2. Methods Index as **more hand-authored YAML**, no live
   fetch. (Read-side + Lame example is drafted.)
3. Lab as **print a layout recipe**, no `hyprctl`.
4. Stuck as **rabbit-hole on `next`**, no new verb. (Drafted.)
5. Social as **local journal only**. (Drafted.)
6. LLM as **tighter copy-paste escalation prompts**, no pane
   and no API key.

---

## Related files

- `docs/CLAUDE_CURSOR_DEBATE.md` — original MUST/SHOULD/DEFER/DO NOT
- `docs/METHODS_INDEX.md` — citation index, gated behind Rabbit Hole
  Detection's stuck signal, now with a live Agent Harness draft path
- `docs/AGENT_HARNESS.md` — the operator's-own-agent-CLI escalation
  mechanism (reverses part of the LLM/chat-pane rail above)
- `docs/UPDATE_FRAMEWORK.md` — sync + review-gate plumbing everything
  knowledge-growth-shaped plugs into
- `docs/SHOULDER_MODE.md` — live pty session capture (reverses part of
  the shell-history-sensors rail above)
- `docs/FEATURES_BACKLOG.md` — AutoRecon teach/parse (now a stated
  primary teaching goal, not a minor nudge — see FEATURES_BACKLOG.md's
  updated AutoRecon entry); social declined
- `DESIGN.md` — public out-of-scope list, rewritten 2026-09 opening
  mission statement
- `docs/CURSOR_HOMEWORK.md` — filed 2026-09-07: the three assigned
  Cursor projects (coverage sim, AD engine, AD sim). Not a rail
  change; docket only.
- `docs/CURSOR_HANDOFF_CONTINUE.md` — what was actually drafted this
  week
- `~/Downloads/Trinity_suggestions.md` — §2.10 lab, §2.14 no chatbot
  (superseded in part by the Agent Harness pivot — see above),
  §4.3 do-not-integrate

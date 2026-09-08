# Trinity 2.0 — vision notes (GUI, access, community, sustainability)

Status: IDEAS, captured for a future build phase. Nothing here is
scheduled against 1.0. Recorded now, in detail, so the reasoning
survives between sessions rather than getting re-litigated from
scratch. See `docs/FEATURES_BACKLOG.md`'s "2.0 GUI — local webserver"
entry for the short version; this is the fuller writeup.

## 1. Local webserver, not a hosted multi-tenant website

Already recorded in `docs/FEATURES_BACKLOG.md`. Summary: `trinity web`
spins up a `127.0.0.1`-only server and opens a browser tab, rendering
the same dashboard/coaching data the Textual TUI shows today as
HTML/CSS/JS instead of terminal glyphs. Zero backend, zero accounts,
same local-first principles. More cross-platform than the current TUI
(browser rendering sidesteps terminal-emulator/ConPTY variance),
though Shoulder Mode's raw pty capture remains its own, separate,
OS-coupled problem regardless of UI layer.

**Hard line to hold as this gets built out:** the actual tool (CLI,
local webserver, Shoulder Mode, Agent Harness) must keep working
fully, forever, with zero account and zero internet connection
required — exactly as today. Any account/signup system described below
gates the WEBSITE/community layer, never the tool itself. If a
donor gets a better Trinity than a non-donor, that breaks both the
open-source identity and the "reach anyone regardless of ability to
pay" education mission this whole project exists to serve.

## 2. Bringing your own AI: API keys (locked in for 2.0) + OAuth (later)

Raised because Mac/Windows aren't "agentic operating systems" by
default the way an Omarchy/Linux box with CLI tools already installed
is — Agent Harness's current mechanism (`src/trinity/agent_harness.py`)
only shells into an agent CLI already on PATH (hermes/claude/codex/
gemini/cursor-agent). A stock Mac/Windows install with none of those
installed silently falls back to manual copy-paste escalation. This is
a real, load-bearing gap outside the Omarchy assumption.

**API key support — approved for 2.0.** A student pastes their own
Anthropic/OpenAI/etc key once; Trinity makes its own bounded, one-shot
HTTP calls for the exact same narrow Agent-Harness purpose (cache-miss
escalation only, never a persistent chat). Two requirements before
this ships:
- **Key storage via the OS keychain** (macOS Keychain, Windows
  Credential Manager, Linux Secret Service — the `keyring` Python
  library wraps all three), never a plaintext file in `~/.trinity/`.
  A plaintext key would be a real security regression against
  everything else in this project's careful local-first design.
- This does **not** violate "Trinity never holds its own API key" —
  that rule is about a Trinity-owned hosted key/quota baked into the
  product. An operator supplying their OWN key for their OWN bounded
  use is the same trust class as them running their own CLI; it's a
  new transport (HTTP+SDK) for the same contract, not a new trust
  boundary.
- New maintenance surface, stated honestly: Trinity now owns direct
  API client code per vendor (auth shape, error handling, rate limits)
  instead of getting that for free by shelling into someone else's
  already-maintained CLI.
- Architecture note: this becomes a new tier in Agent Harness's
  detection priority — CLI-on-PATH first, then a configured API key,
  then the existing manual copy-paste fallback last. Document as an
  addendum to `docs/AGENT_HARNESS.md` when built (changes that doc's
  trust-boundary description).

**OAuth login — real idea, deprioritized, not rejected.** Mostly
redundant with what already exists: several of the 5 agent CLIs
Trinity already shells into do their own browser OAuth today the
moment they're installed (`claude auth login`, etc.) — Trinity
inherits that for free. The actual remaining gap OAuth would close is
narrow: "won't install any CLI AND doesn't want to paste a raw key."
Vendors also don't make broad third-party OAuth easy the way "Sign in
with Google" is — this means real per-vendor OAuth app registration,
a loopback HTTP server or device-code flow (same shape as `gh auth
login`), and token refresh handling — meaningfully more engineering
than a text field. Revisit if real demand shows API keys aren't enough.

## 3. Community KB sync — opt-in, not default

Extends Update Framework's "grow FROM local use" mission
(`docs/UPDATE_FRAMEWORK.md`) from one operator's local cache to a
shared, crowdsourced knowledge base — sourced from real students
hitting real novel gaps in the wild, arguably higher-signal than Doc's
offline Coverage Sim sweep of 122 retired boxes.

**Must be OPT-IN, asked once, plainly worded, off by default.**
Sending any data off the operator's machine is a genuinely new
category of reversal versus Agent Harness/Shoulder Mode (both stay
100% local, zero bytes leave the machine) — it needs its own explicit
`OPEN_DECISIONS.md` entry, recorded in Alexander's own words, the same
treatment the prior two real reversals got, before it ships. Not
something that should ride in silently as a side effect of building
the webserver.

Design, once approved:
1. **Local scrub before anything leaves the machine.** A real Agent
   Harness escalation prompt can carry a target IP, hostname, VPN
   identifier, or incidental local paths. Redaction happens locally,
   before submission — same principle as Coverage Sim's "facts from
   public writeups only, no target-identifying data."
2. **GitHub itself as the queue — no custom backend infra.** Fits
   Trinity's open-source identity: an opted-in install bundles its
   approved local cache entries and opens a PR against a public
   `trinity-knowledge` repo, citation attached. Same intake/review-gate
   discipline Update Framework already enforces locally, GitHub as the
   shared surface instead of local SQLite.
3. **Agents do the first-pass review, not the final merge.** Same
   pattern already proven on this project (Cursor/Claude Code CLI do
   the heavy lifting, Doc reviews and merges): dedup, obvious-junk
   rejection, and — since crowdsourced input is adversarial in a way
   single-operator local use never was — flagging anything that looks
   like a prompt-injection attempt buried in a submitted note field.
   Curated shortlist reaches Doc/Alexander for actual sign-off.
4. **This is the THIRD producer feeding the same review queue**
   (Agent Harness escalations, Assimilator's offline sweep, this).
   Queue capacity/rate-limits need solving once, centrally — flagged
   independently by Claude Code CLI's Assimilator/Show Me Mode design
   review (see `findings/design_review_claude.md` in the review
   worktrees) as a real gap in the current Update Framework design.
5. **Distribution loop closes with what already exists:** scrubbed
   PRs -> Doc/agent review -> merged into the next Trinity KB seed
   release -> pulled by every install via Update Framework Part 1's
   existing sync-from-outside-world mechanism. No new distribution
   mechanism needed.

Recommend its own doc (`docs/COMMUNITY_KB_SYNC.md`) with the privacy-
scrub design spelled out in full, plus the required `OPEN_DECISIONS.md`
entry, before any build.

## 4. Nonprofit / pay-what-you-want sustainability model

Website carries an optional account (for install convenience, a
personal dashboard of community-KB contributions if opted in, and a
donate button) tied to a pay-what-you-want subscription (including
$0) supporting a nonprofit overseeing the project — modeled on
Wikipedia/Signal Foundation-style funding, not a paywall.

**The one hard line: signup/payment must gate the website/community
layer only, never the tool.** Restated from §1 because it's the load-
bearing constraint on everything else in this section.

Practical build recommendations:
- **Don't roll custom payment/account infra.** Open Collective is
  purpose-built for pay-what-you-want open-source project funding and
  can act as a fiscal host before real 501(c)(3) status exists.
  GitHub Sponsors + Stripe Checkout is a lower-friction alternative if
  Open Collective's expense-transparency features aren't needed.
- **Nonprofit status (or a fiscal sponsor) is a real legal/financial
  process, separate from and prior to wiring any of this up** — Open
  Collective specifically exists to let this start before
  incorporating, which may be the pragmatic first step.
- **New compliance surface once there's a signup + payment flow:**
  email addresses, donor/payment records, possible tax-deductible
  receipt recordkeeping, a mailing list now requiring real security —
  this is genuine operational scope beyond software design.

## 5. Community/competitive layer — leaderboards, rankings, speed records

Directly inspired by HTB/THM's own community features. Compelling and
worth building, with two things that need to be right before it ships
— not adjustments to make later, prerequisites:

**Legal — COPPA (and likely FERPA) apply if kids are using this, full
stop.** COPPA governs collecting data from under-13s; a per-school/
per-city leaderboard is exactly the kind of identifying-by-association
data collection it regulates, even without a real name attached. If
schools participate as an entity, FERPA (student education records)
can also apply depending on how data ties to enrollment. Concretely:
verified parental consent for under-13 accounts, handles/aliases only
on any public leaderboard (never real names), and a real privacy/legal
review — specifically, someone who does ed-tech compliance, not a
guess — before "per school" ships in any form.

**Pedagogical — protect the reason gamification was already cut from
the LOCAL tool.** `docs/FEATURES_BACKLOG.md`'s achievements/
gamification entry was explicitly CUT for the core product: "gamify
before the first win" risks making a stuck beginner feel worse, not
motivated — directly against the burnout-prevention mission Rabbit
Hole Detection and frustration checkpoints exist to serve ("even
people with security master's degrees get stuck for hours — this is
normal"). Keep leaderboards/speed-records scoped to the
website/community layer, opt-in, and structurally separate from the
everyday learning flow: a student grinding their first box should
never see a leaderboard unless they go looking for it. Competitions/
speed-runs are their own separate mode for people who want that
framing, not the default lens on learning.

Once these two are handled: per-school/city/state rankings, speed
records, and community stats are genuinely good engagement mechanisms
and worth building at the website tier.

## 6. Original boxes, CTFs, and competitions — funded future phase

Correctly sequenced as a "once there's real funding to hire" item, not
a near-term build. Real operational difference worth remembering when
that day comes: hosting live exploitable VMs at scale (as HTB/THM
actually do) is a fundamentally different, ongoing burden — uptime,
abuse prevention, isolation between competitors, security of the
hosting platform itself — versus everything Trinity does today, which
never hosts a target, only coaches against boxes the student already
has independent access to. Good long-term goal; needs a real
infrastructure hire, not a side feature.

## Related docs

- `docs/FEATURES_BACKLOG.md` — the short-form "2.0 GUI" entry this
  document expands on.
- `docs/AGENT_HARNESS.md` — will need an addendum once API key support
  is built (new detection-priority tier, new trust-boundary language).
- `docs/UPDATE_FRAMEWORK.md` — the review-gate/sync plumbing the
  community KB sync design (§3) plugs into.
- `docs/OPEN_DECISIONS.md` — needs a new entry for community KB sync
  (§3) before build, following the same explicit-decision precedent as
  the Agent Harness / Shoulder Mode reversals.

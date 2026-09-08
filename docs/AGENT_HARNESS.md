# Agent Harness — Design

Status: BUILT AND TESTED. Implemented in `src/trinity/agent_harness.py`
(agent-CLI detection + bounded one-shot invocation) and
`src/trinity/intake.py` (review-gate queue), with dedicated tests in
`test/unit/test_agent_harness.py`, `test/unit/test_cli_agent_harness.py`,
and `test/unit/test_intake.py`. This doc retains its original design
rationale below; it is no longer a proposal. This supersedes the
earlier "no chat pane, no API key, ever" framing in
`docs/CLAUDE_CURSOR_DEBATE.md` and `docs/OPEN_DECISIONS.md`'s "LLM /
chat pane" entry — that veto is now understood more precisely (see
"What this is NOT" below), not simply reversed wholesale.

## Why this exists

Trinity's founding bet was: local lookups handle the deterministic 80%
of "what does this mean," and a genuine cache miss escalates to
whatever AI assistant the operator already uses, via a copy-paste
prompt they carry over by hand. That's real and it works, but it has
two problems once Trinity's actual audience is people running an
agentic OS (see DESIGN.md's rewritten opening):

1. **The round trip is manual and lossy.** The operator has to copy a
   prompt, paste it somewhere else, get an answer, and manually run
   `trinity cache-explanation`/`cache-error` to save it. Most people
   won't bother for anything short of a real blocker, so the cache
   grows far slower than it could.
2. **It ignores what's actually already running on the machine.**
   Someone using Omarchy already has an agent CLI sitting right there
   — the same tool they used to build/run Trinity itself. Making them
   leave Trinity, open a separate chat, and hand-copy things back is
   friction Trinity doesn't need to impose.

The Agent Harness closes that loop: Trinity hands a specific, bounded
question directly to the operator's own agent CLI, gets a real answer,
and — after passing through the Update Framework's review gate (see
`docs/UPDATE_FRAMEWORK.md`) — folds it permanently into the local
cache. Alexander's framing: "like machine learning, but for our tool."

## What this is NOT (the line that keeps the original veto's spirit)

The original "no LLM/chat pane" veto was protecting one specific
thing: **Trinity itself never becomes a chatbot with its own API key,
where talking to it replaces looking things up locally.** That
principle is unchanged and still absolute:

- Trinity never holds its own API key. It never calls a hosted model
  directly, on its own account, on the operator's behalf.
- Trinity never grows an in-app "just ask me anything" chat pane where
  free-form conversation becomes the default interaction mode.
- The agent Trinity talks to is always the OPERATOR's own tool — one
  they already run, already pay for (or run locally), already
  control, and could inspect or kill at any time. Trinity is a
  caller INTO that tool for one bounded job, never a wrapper AROUND
  a model of its own.
- Local lookups always run first. The Agent Harness only ever fires
  on a genuine cache miss — the exact same trigger condition the
  manual copy-paste escalation already used. This is the same
  trigger, automated, not a new, lower bar for reaching for AI.

The difference from the original veto is narrow but real: the veto
assumed "any AI involvement is the same product in a trench coat."
What actually matters is WHO holds the model relationship (the
operator, via their own tool, not Trinity) and WHETHER the answer
becomes a permanent, reviewed, free local asset afterward (yes) rather
than a disposable chat reply (no). An agent-harness call that ends in
a cached KB entry is closer in spirit to `searchsploit` (a real local
lookup, sourced, reviewed) than to a chatbot.

## Which agent Trinity talks to

Priority order, checked at first use (and re-checked if the previous
choice is no longer available):

1. **The Omarchy default agent**, if running on Omarchy. Concretely:
   whatever `omarchy-launch-tui`/the desktop's configured default
   agent entry point resolves to (Alexander's own setup: Hermes,
   itself running Claude as the underlying model). Trinity should
   read this the same defensive way `theme --omarchy` already reads
   the live desktop theme — try, fall back cleanly, never crash on a
   non-Omarchy or misconfigured system.
2. **Any detected agent CLI on PATH**, if not on Omarchy or the
   default agent isn't resolvable. Check for known agent CLI binaries
   (Claude Code, Codex, Gemini CLI, Cursor CLI, etc.) the same way
   `tools.py` already checks for gobuster/enum4linux-ng — a small,
   hand-maintained registry, `shutil.which`-based, PR-able for new
   agent tools as they show up.
3. **Manual copy-paste fallback**, unchanged from today, if neither of
   the above resolves to anything. This is not a degraded experience
   Trinity apologizes for — it's the same reliable path that already
   exists, just not the first thing tried.

Trinity's first-run intro/README should say plainly that Trinity is
*designed* to be paired with an agentic OS (Omarchy recommended) and
works best that way, without refusing to run at all in its absence —
per Alexander: "if it doesn't believe there's an agent CLI, it should
fall back to manual copy-paste, but the opening statement should make
clear this tool is intended to be paired with Omarchy or the like."

## How a harness call actually works

1. A genuine local-cache miss occurs (same trigger as today's
   `trinity explain`/`trinity error` "not in the local cache yet"
   path, plus new call sites: GTFOBins proactive nudges without a
   local entry, Methods Index live-drafting on a stuck signal — see
   those docs).
2. Trinity builds the same tight, specific prompt it already builds
   for manual escalation (`build_escalation_prompt()` /
   `build_error_escalation_prompt()` — reused, not replaced).
3. Instead of printing it and waiting for the operator to paste it
   elsewhere, Trinity invokes the detected agent CLI directly
   (non-interactively — same pattern already used for dispatching
   `cursor-agent` reviews in this project's own build process, see
   the `claude-code`/`codex`/`cursor-cli`-family skills for the
   subprocess-invocation shape) and captures the response.
4. The raw response does NOT get silently trusted or auto-merged.
   It's written to the Update Framework's intake queue (see
   `docs/UPDATE_FRAMEWORK.md`) exactly like any other candidate
   knowledge addition — Claude (or whoever is doing the review pass
   for this install) reviews and confirms before it becomes a real
   `command_explanations`/`error_patterns`/KB row.
5. Once approved, it's cached forever, same trust model
   (`source='ai_escalation'`) as today's manually-cached entries.
   Nothing about the schema changes — this only automates STEPS 2-3
   of a flow that already exists end to end.

## Where this plugs into other docs

- **Update Framework** (`docs/UPDATE_FRAMEWORK.md`) is the review gate
  and the eventual opt-in upstream-sharing mechanism for anything the
  Agent Harness produces. The Agent Harness never merges its own
  output directly.
- **GTFOBins** (see `DESIGN.md` roadmap / `docs/OPEN_DECISIONS.md`):
  once the full dataset is ingested, the Agent Harness is the
  mechanism for "Trinity doesn't have this binary covered yet, ask the
  agent for a summary, review it, add it."
- **Methods Index** (`docs/METHODS_INDEX.md`): the Agent Harness is
  now an alternate path to producing a Method record, live during a
  stuck session, alongside the original offline subagent pipeline —
  same citation/summary-length rules apply regardless of which path
  produced the draft.

## Non-negotiables (unchanged from the original veto, restated precisely)

- No API key Trinity holds itself.
- No in-app chat pane / free-form conversation UI.
- No silent trust of anything an agent call returns — always through
  the intake/review gate.
- Never invoked as a substitute for a local lookup that would have
  worked — always cache-miss-gated, same as today.
- The operator can always see exactly what question was sent and what
  came back (no hidden prompts, no silent background calls the
  operator can't inspect).

## Open questions for whoever builds this

- Exact subprocess invocation shape per agent CLI (flags for
  non-interactive/one-shot mode differ per tool — needs its own
  small per-agent adapter, similar in shape to `tools.py`'s
  per-platform install-command registry).
- Timeout / cost guardrails for a harness call that hangs or the
  underlying agent itself burns a lot of its own tokens on.
- Whether a harness call should be visible in the watch-mode dashboard
  feed in real time (probably yes — same "nothing hidden" principle as
  the rest of Trinity) or only in the CLI's synchronous output.

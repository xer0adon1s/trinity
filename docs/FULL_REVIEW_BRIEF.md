# Full program review — report card request (Cursor / Claude Code CLI)

You are doing an independent, thorough code review of the entire
Trinity codebase, with special emphasis on everything built since (and
including) commit `abbdb4b` through `HEAD` — the Assimilator/Show Me
Mode design docs, the Assimilator core loop, Show Me Mode's live
trigger, the report-integrity fixes, and the new Tools/Advanced TUI
menus. Run `git log --oneline e42592c..HEAD` in this worktree to see
the exact commit range; `git diff e42592c..HEAD` for the full diff.
This is the FIRST review pass these newer systems have had (the
Assimilator/Show Me Mode DESIGN docs were reviewed once, before any
code existed — see `findings/design_review_cursor.md` and
`findings/design_review_claude.md` in the sibling review worktrees
from that earlier pass, if you want prior context on what was already
flagged at the design stage). This pass reviews the ACTUAL CODE for
the first time.

Read-only review. Do not write, edit, or delete any implementation
code, do not touch `src/` or `test/`. This is a review pass, not a fix
pass — findings get triaged and actioned afterward by Doc.

## Scope

1. **Whole-program review** — the full `src/trinity/` tree, not just
   the new commits. Alexander wants an honest report card on the
   codebase as it stands today, not just the diff.
2. **Newer-systems deep dive** — everything in the `abbdb4b..HEAD`
   range gets its own dedicated section, since this is its first real
   review:
   - `src/trinity/assimilator.py` — the leverage ledger
   - `src/trinity/show_me.py` — Show Me Mode's live execution loop
   - `src/trinity/tui/show_me_screens.py` — the Tools/Advanced TUI menus
   - The `assimilator_runs`/`show_me_runs`/`show_me_attestation`
     tables in `src/trinity/db.py`
   - The report-integrity changes in `src/trinity/report/data.py`,
     `educational.py`, `professional.py`
   - The `intake.py` provenance fix (source flattening on approval)
   - `src/trinity/recap.py`, `src/trinity/doctor.py` (also new this
     pass, lower stakes than the above but still unreviewed)
   - `docs/ASSIMILATOR_PROJECT.md` and `docs/SHOW_ME_MODE.md` (v2) —
     does the SHIPPED CODE actually match what these v2 design docs
     say it does? Flag any drift between doc and implementation.

## What we want — two full report cards

### Report card 1: the overall program

Grade Trinity's codebase as a whole (`src/trinity/` in full) on
whatever metrics genuinely constitute "good code" for a project like
this — you choose the categories, but at minimum address:
- **Architecture/structure** — module boundaries, separation of
  concerns, is the "local-first, KB before AI" principle actually
  enforced in the code or just in prose?
- **Code quality** — readability, consistency, error handling,
  Pydantic model usage, type hints, docstring quality/accuracy (do
  docstrings describe what the code ACTUALLY does, or has drift crept
  in anywhere?).
- **Test coverage and quality** — not just "how many tests" but
  whether they test real behavior vs. trivial assertions, whether
  critical paths (safety guardrails, destructive-command denylists,
  report-integrity logic) have dedicated tests or just incidental
  coverage.
- **Security posture** — anywhere user/agent-controlled input reaches
  a shell, a file path, or a DB query without validation. Pay real
  attention to `show_me.py`'s command execution path specifically —
  this is the one place in the codebase that runs live subprocess
  commands based on AI-agent output.
- **Consistency with the project's own stated design principles**
  (`DESIGN.md`, `docs/OPEN_DECISIONS.md`) — does anything in the
  actual code contradict a rail the project says it holds?

Assign whatever grade format makes sense (letter grades, 1-10, whatever
you think communicates clearly) per category, with concrete evidence
(file/line references) for every grade, not vibes.

### Report card 2: the newer systems specifically

Same rigor, focused entirely on the `abbdb4b..HEAD` range described
above. In particular:

1. **Does `show_me.py`'s destructive-command denylist and target-pin
   logic actually hold up?** Try to find a bypass. This is a real
   security-relevant question, not a formality — the whole safety
   story in `docs/SHOW_ME_MODE.md` depends on the runner (not the
   agent) enforcing this correctly.
2. **Is the "agent proposes, Trinity executes" loop in `run_show_me()`
   actually safe against a misbehaving or adversarial agent response?**
   What happens if the agent's response is malformed, empty, contains
   shell metacharacters, or tries to break out of the single-command
   assumption?
3. **Does the report-integrity fix actually close the gap the design
   review found?** Re-read `docs/SHOW_ME_MODE.md` §7's requirements
   and check the actual `educational.py`/`professional.py`/`data.py`
   changes against them line by line.
4. **Is the `assimilator_runs` leverage ledger schema/API actually
   usable for the offline batch sweep this is meant to eventually
   support**, or does the v1 scope (live-trigger-only) leave gaps that
   will require a rewrite rather than an extension later?
5. **TUI menu code (`show_me_screens.py`)** — Textual-specific
   concerns: are the modal screens' state management, thread-safety
   (the `@work(thread=True)` background worker calling back into the
   UI thread), and error handling solid? What happens if
   `run_show_me()` raises an unexpected exception inside that
   background thread?
6. **Is `check_already_known()`'s KB lookup actually going to catch
   real "you already had this" cases**, or is the match criteria (only
   service/product/version, no port/host) too narrow to be useful in
   practice given how Show Me Mode is actually invoked (which doesn't
   pass real service/product/version today — check the actual call
   site in `show_me.py`)?

## Deliverable

A single markdown file, `findings/full_review_<cursor|claude>.md`
(use your own name), committed on this worktree's branch (`full-review-cursor`
or `full-review-claude` respectively) with a clear commit message. Do
NOT merge or push.

Structure:
1. Report Card 1 (whole program) — grades + evidence
2. Report Card 2 (newer systems) — grades + evidence, answering the 6
   numbered questions above explicitly
3. Top 5-10 concrete, prioritized recommendations — ranked by
   severity/impact, each with a specific proposed fix, not just "this
   could be better"
4. Anything else you think Alexander/Doc should know before this goes
   into a live user test session

Be thorough, be specific, cite real file/line references, and be
genuinely helpful — the goal is catching real problems before a live
test, not a rubber stamp.

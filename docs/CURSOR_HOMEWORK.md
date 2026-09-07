# Cursor homework — filed 2026-09-07

Status: FILED, not started. Assigned by Doc (Claude) on main
(`bd81f92`). Cursor does not merge or push. Doc reviews both.

These three items are the only authorized Cursor work until
Alexander says otherwise. Specs are the source of truth — this
file is the docket, not a rewrite.

## The three items

| # | Spec | Branch / worktree | Depends on |
|---|------|-------------------|------------|
| 1 | [COVERAGE_SIMULATION_PROJECT.md](./COVERAGE_SIMULATION_PROJECT.md) | `coverage-sim-findings` → `../trinity-wt-coverage-sim` | none |
| 2 | [AD_ENGINE_PROTOTYPE_PROJECT.md](./AD_ENGINE_PROTOTYPE_PROJECT.md) | `feat/ad-enumeration-prototype` → `../trinity-wt-ad-engine` | none |
| 3 | [AD_SIMULATION_PROJECT.md](./AD_SIMULATION_PROJECT.md) | `ad-sim-findings` → `../trinity-wt-ad-sim` (create when #2 lands) | **#2 must exist first** |

1 and 2 can run in parallel. 3 is blocked on 2. Neither 1 nor 2
touches the other's work: coverage-sim logs AD boxes as
`capability_gap` and does **not** build AD capability; the AD
engine is the only place that code is allowed.

## Worktree note (do this before writing code)

Both existing worktrees are parked at `12ba806`, **two commits
behind main**. They are missing the AD specs (`49ccc5b`) and the
handoff sharpening (`bd81f92`). Rebase/reset each onto `main`
before starting. Do not work in `/home/alexander/Work/trinity`
(the main checkout).

## What each item actually is

**1. Coverage simulation.** Scale Doc's 6-box live-CLI sweep to
~100–150 boxes (first checkpoint; 150–250 is the eventual
target). Real writeups only, isolated `$HOME`, real CLI output.
Fix live **only** mechanical `searchsploit` routing / FTS
stopword bugs (bucket 1). Log KB/suggest/capability gaps; do
not implement them. Known first fix to attempt: path-finding
searchsploit routing (Nibbles/Netmon class).

**2. AD engine prototype.** Trinity currently has zero AD/domain
code. Narrow first slice: DC-signature detection (must not fire
on Blue/Legacy), ldapsearch + GetNPUsers + GetUserSPNs parsers,
3–5 suggestion rules, 3–5 ELI5 seeds, 2–3 KB entries, wire into
existing `parse-nmap` plus one dispatcher command if needed.
Scope creep goes in `docs/AD_ENGINE_OPEN_QUESTIONS.md`, not
into code. No BloodHound, no auto-run, no new phases, no report
changes.

**3. AD simulation.** 15–25 AD-flavored boxes against the engine
from #2. Mechanical regex/crash bugs may be fixed; missing
coverage is logged, not silently patched. Negative controls
(Blue, Legacy) are the most important rows.

## Rails that still apply on all three

No auto-install, no auto-run, no launchers, no Trinity-owned
API key, no chat pane, no `trinity lab`/hyprctl, no persistent
shell-history reads, no new CLI verbs beyond what the spec
lists, no push, no merge to main.

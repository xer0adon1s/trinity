# Project: AD/Windows-Specific Simulation — Testing the AD Engine Prototype

Assignment: ACTIVE. Assigned to Cursor. Run this AFTER
`docs/AD_ENGINE_PROTOTYPE_PROJECT.md` has landed (in worktree
`../trinity-wt-ad-engine`) — this project tests THAT engine
specifically. Do not start this before the engine prototype exists;
there's nothing to test yet.

## Why this is a separate doc from COVERAGE_SIMULATION_PROJECT.md

`docs/COVERAGE_SIMULATION_PROJECT.md` is a broad Linux/Windows sweep
testing Trinity's EXISTING match/suggest engine against single-host
boxes (the kind Trinity already has code for) — it deliberately logs
AD boxes as "capability gap" and moves on, since Trinity had zero AD
code when that doc was written.

This doc is the opposite: narrow, AD-only, and specifically exists to
stress-test the NEW AD engine prototype once it exists. Where the
coverage sweep asks "does Trinity's existing engine handle this box,"
this doc asks "does the brand-new AD engine actually recognize real
AD attack surface, or does it only work against the one example the
engine's own author tested while building it." That's a meaningfully
different, more skeptical question, and it deserves its own corpus and
its own scoring rubric.

## Ground rules (same discipline as every other simulation project)

1. **Real facts only, always verified.** Same sourcing standard as
   `docs/COVERAGE_SIMULATION_PROJECT.md` and
   `docs/METHODS_INDEX.md`: public, non-paywalled, RETIRED boxes only.
   AD-flavored HTB boxes have excellent, plentiful public writeup
   coverage (0xdf covers nearly every one) — there's no excuse for
   guessing a port/domain/technique instead of citing a real writeup.
2. **Isolated `$HOME` per simulation run** — never touch the real
   operator's `~/.trinity/` data, same as every prior simulation
   project.
3. **Work in its own worktree**: `git worktree add -b
   ad-sim-findings ../trinity-wt-ad-sim <branch-the-AD-engine-landed-on>`
   — branch this off the AD engine's own branch/worktree state (NOT
   off `main`, since main won't have the AD engine code yet at the
   time this runs), so the simulation can actually exercise the new
   code. If Doc has already merged the AD engine to main by the time
   you start this, branch off main instead — check `git log
   --oneline -5` on main first to see if the AD engine commits are
   already there.
4. **You are NOT authorized to fix bugs found here by adding new AD
   capability** (new parsers, new suggestion rules, new KB entries) —
   that would blur this project back into being the engine-building
   project. Bugs found in THIS pass fall into two categories:
   - **Mechanical bugs in code the engine project already built**
     (a regex that doesn't match a real-world variant, an off-by-one
     in port detection, a crash on malformed input) — these you MAY
     fix directly, with a regression test, same "fix mechanical bugs,
     log everything else" rule as
     `docs/COVERAGE_SIMULATION_PROJECT.md`.
   - **Missing coverage** (a real AD technique/tool the prototype
     doesn't recognize at all, e.g. it detects AS-REP roasting but
     not Kerberoasting, or doesn't recognize a legitimate DC signature
     variant) — these get LOGGED as findings for Doc to fold into the
     next AD-engine iteration, not fixed live. The whole point is an
     honest gap assessment, not you quietly patching over gaps as you
     find them and hiding how incomplete the prototype actually is.
5. **Do not scope-creep this into re-litigating the engine's design.**
   If you think the engine's whole APPROACH to something is wrong
   (not just missing a case), log it clearly as a design question in
   `findings/ad_sim_design_questions.md` — don't rewrite the engine
   mid-simulation-run.

## Corpus: 15-25 AD-flavored boxes, small and focused on purpose

Unlike the 150-250-box broad sweep, this corpus is deliberately SMALL
— AD engine coverage is narrow by design (see the prototype doc's
"What to build" — signature detection + anonymous LDAP + AS-REP
roasting awareness ONLY), so a large corpus would mostly just prove
the same narrow slice works repeatedly. 15-25 well-chosen boxes is
enough to find real gaps without wasting a token budget re-confirming
the same three code paths forty times.

Target mix:
- **5-8 "pure DC discovery" boxes**: the AD port-cluster signature
  (88/389/445/etc together) should fire cleanly, domain name
  extractable from nmap script output. Include some EASY, well-known
  examples (e.g. HTB Forest, Sauna, Active — verify via real writeups,
  don't assume these are exactly right) since these are the most
  likely to have clean, well-documented nmap output showing the
  domain name.
- **5-8 "AS-REP roastable" boxes**: real writeups where the actual
  attack path includes a AS-REP-roastable account found via
  `GetNPUsers.py` with no prior credentials (this is specifically
  what the prototype claims to detect — find real examples, don't
  assume any AD box has this specific technique).
- **3-5 "anonymous LDAP bind succeeds" boxes**: real writeups
  confirming an unauthenticated LDAP bind was part of the actual
  recon path.
- **2-4 "should NOT trigger AD detection" negative-control boxes**:
  reuse a few boxes from the earlier 6-box exercise or the coverage
  sweep (Blue, Legacy — single-host Windows boxes with SMB/RPC but NO
  real domain) specifically to confirm the AD signature detector does
  NOT false-positive on a lone Windows box just because it has SMB/RPC
  open. This is a real, specific risk given how the 2026-09-07
  session's whole hardening theme was cross-matching false positives
  — the prototype MUST be tested against boxes that look superficially
  similar but aren't actually AD, not just against true positives.

Maintain `test/fixtures/ad_sim/MANIFEST.md`, same row shape as the
coverage sweep's manifest, plus a `should_detect_ad: true|false` column
for the negative-control rows.

## Per-box procedure

Same shape as `docs/COVERAGE_SIMULATION_PROJECT.md`'s per-box
procedure:
1. Research real facts from a cited writeup.
2. Build real-shaped fixture(s) — nmap XML at minimum; ldapsearch/
   GetNPUsers/GetUserSPNs output fixtures for boxes testing those
   specific parsers (match the REAL tool output format, verified via
   web search, same as the engine project's own requirement).
3. Simulate in an isolated `$HOME`:
   ```
   uv run trinity init
   uv run trinity parse-nmap <fixture> --box "<name>"
   uv run trinity next --box "<name>"
   uv run trinity suggest --box "<name>"
   uv run trinity explain "<whatever AD-related command was suggested>"
   ```
   Plus, for boxes testing the ldapsearch/GetNPUsers/GetUserSPNs
   parsers specifically, whatever CLI entry point the engine project
   built for those (check its final report / the code for the actual
   command).
4. Score:
   - **PASS**: the engine correctly detects the real AD signal
     (DC signature / AS-REP roastable account / anonymous LDAP bind)
     that the real writeup confirms was present, and surfaces an
     appropriate suggestion.
   - **MISS**: the real signal was present in the fixture but the
     engine didn't detect/suggest anything for it.
   - **FALSE POSITIVE**: the engine detected an AD signal that isn't
     actually there (critical for the negative-control boxes —
     any false positive here is a real bug, log it clearly and
     prominently, don't bury it).
   - **OUT OF PROTOTYPE SCOPE**: the box's real technique is something
     the engine project explicitly said it wasn't building yet (e.g.
     BloodHound path analysis, full Kerberoasting exploitation past
     detection, anything requiring credentials already in hand) — not
     a bug, just confirms the scope boundary is where it should be.
5. Log to `findings/ad_sim_log.jsonl` (same JSONL discipline as the
   coverage sweep) and `findings/ad_sim_summary.md`. Schema:
   ```json
   {
     "box": "string",
     "platform": "htb|thm",
     "difficulty": "easy|medium",
     "ad_technique": "dc_discovery|asrep_roast|anon_ldap|negative_control",
     "should_detect_ad": true,
     "writeup_urls": ["..."],
     "result": "pass|miss|false_positive|out_of_scope",
     "real_output_excerpt": "string",
     "notes": "string"
   }
   ```

## Deliverable (in ~3 hours per the user's own timeline — keep this tight)

Given the tight timeline, this doesn't need a large checkpoint
structure like the broad sweep — just complete the full 15-25 box
corpus in one pass if time allows, or as many as fit, and report
honestly on how far you got. In the worktree
(`../trinity-wt-ad-sim`, branch `ad-sim-findings`):
- `test/fixtures/ad_sim/` — fixtures + `MANIFEST.md`
- `findings/ad_sim_log.jsonl`
- `findings/ad_sim_summary.md` — tally at the top: pass/miss/
  false_positive/out_of_scope counts, and a SPECIFIC callout of any
  false positives (these matter most) and any mechanical fixes shipped
- `findings/ad_sim_design_questions.md` if anything came up per rule 5
  above
- Any live mechanical-bug fixes, committed individually, full test
  suite passing

Do not push to origin. Do not merge to main. Doc reviews both this and
the AD engine prototype together.

# Project: AD/Windows Enumeration Engine — Rough-Draft Prototype

Status: ACTIVE. Assigned to Cursor. Doc (Claude) reviews after this
lands — expect real revision, this is explicitly a rough draft to
chisel from, not a final design.

## READ THIS FIRST — scope discipline is the actual point of this doc

Trinity currently has ZERO code for Active Directory / domain
enumeration. Every existing capability (suggest engine, KB, parsers) is
built for single-host Linux/Windows boxes. This project adds a NEW,
narrow, well-bounded slice — not a rewrite, not a "while I'm in here"
expansion of anything else.

**You are explicitly NOT authorized to:**
- Touch `advisories.py`, `rabbit_hole.py`, `graduation.py`, `wizard.py`,
  `hints.py`, or any CLI command not listed in "What to build" below.
- Add new CLI verbs beyond the ones explicitly specified.
- Change `_PHASE_ORDER` in `coach.py` or any existing phase-ordering
  logic — AD findings plug into the EXISTING phase vocabulary
  (`recon`/`enum`/`foothold`/`privesc`/`post`), they don't invent a new
  one.
- Add config options, feature flags, settings tables, or "while I'm at
  it" conveniences not explicitly requested.
- Touch the Update Framework, Agent Harness, GTFOBins, Methods Index,
  or anything in `docs/OPEN_DECISIONS.md`'s rail list (auto-install,
  auto-run, launchers — same rules apply to any new AD tooling: Trinity
  parses output FROM tools like BloodHound/Impacket, NEVER invokes them).
- Invent new report formats, new report sections, or touch
  `report/*.py` at all.
- Add ANY new third-party Python dependency to `pyproject.toml`
  without flagging it explicitly in your final report for Doc's
  approval — stdlib + pydantic + what's already a dependency only,
  unless there is truly no other way (and even then, ask first via a
  clearly marked note in your findings/progress file, don't just add it).

**If you find yourself wanting to build something not explicitly listed
below "What to build," STOP and write it up as a proposal in
`docs/AD_ENGINE_OPEN_QUESTIONS.md` (create this file) instead of
building it.** This file exists specifically so ideas don't get lost
AND don't get silently implemented. Doc will read it.

This project is scoped as a PROTOTYPE deliberately — the goal is a
working skeleton Doc can review, critique, and refine, matching the
SAME code shape/quality/test-discipline as the rest of this repo. Not
a finished feature. Do not over-build; a correct, narrow, well-tested
40% is worth more here than a sprawling, half-tested 150%.

## Background: read these files fully before writing any code

- `DESIGN.md` — the whole project's philosophy (local-first, zero
  auto-run/auto-install, deterministic-lookup-before-AI, teach the
  WHY). Everything you build must follow the same rules that already
  govern nmap/gobuster/SMB handling.
- `src/trinity/parsers/nmap.py` — the `Finding` pydantic model every
  parser in this repo produces. AD parsers MUST produce the same
  `Finding` shape (extend it minimally if genuinely needed — see
  "Finding model" below — never invent a parallel data model).
- `src/trinity/parsers/enum4linux_ng.py` and
  `src/trinity/parsers/gobuster.py` — read both fully as the reference
  shape for "parse this tool's real output format into Findings."
  Match this exact style: pure functions, defensive parsing (missing
  sections don't crash), one parser per tool/format.
- `src/trinity/suggest/engine.py` — read the WHOLE file. This is the
  most important reference: `_suggest_for_port()`'s per-service rule
  pattern (predicate + Suggestion builder, `phase`/`command`/
  `rationale`/`nudge`/`required_tool`/`finding_id` fields) is EXACTLY
  the pattern new AD suggestion rules must follow. Do not invent a
  different suggestion shape.
- `src/trinity/coach.py` — read fully, especially `_PHASE_ORDER` and
  `get_recommendation()`. Understand how phase ordering already works
  before adding anything that plugs into it.
- `src/trinity/match/engine.py` — read fully, INCLUDING the two fixes
  from 2026-09-07 (`_FTS_STOPWORDS`, `_ms_bulletin_terms`) — these are
  the most recent real bugs found in this exact subsystem; understand
  them so AD-related KB/searchsploit additions don't reintroduce
  similar cross-matching bugs.
- `src/trinity/kb/seed.py` — the shape of a hand-curated KB entry.
- `src/trinity/boxes.py` — the `Box` model. Read this before deciding
  whether AD needs new Box fields (see "Box/schema" section below).
- `docs/COVERAGE_SIMULATION_PROJECT.md` — the sibling project (may be
  running in parallel in a different worktree) that does a broad
  Linux/Windows coverage sweep using searchsploit routing. This
  project is DIFFERENT and NARROWER: it's specifically about giving
  Trinity AD/domain-awareness it currently has none of at all, not
  about routing more searchsploit queries. Don't duplicate that
  project's work.

## What "AD enumeration" actually means (context so you build the right thing)

A real AD-flavored HTB/THM box's recon looks structurally different
from a single-host Linux/Windows box:

1. **Distinctive port/service fingerprint**: DNS (53), Kerberos (88),
   RPC (135), NetBIOS (139), LDAP (389), SMB (445), Kerberos kpasswd
   (464), LDAPS (636), Global Catalog (3268/3269), WinRM (5985/5986) —
   several of these open together on one host is the single strongest
   "this is a domain controller" signal, distinct from a lone SMB/RPC
   Windows box like Blue/Legacy.
2. **A domain name** typically appears in nmap script output (e.g.
   `ldap-rootdse` NSE script output, SMB OS discovery's "Domain:"
   field, Kerberos SPN responses) — this is a real, extractable fact,
   not something Trinity has to guess.
3. **Common enumeration TOOLS whose OUTPUT Trinity should be able to
   read** (never launch — same "teach + parse, don't run" rule as
   AutoRecon): `ldapsearch` (anonymous LDAP bind dumping users/
   computers/groups), `crackmapexec`/`netexec` (SMB/LDAP/WinRM
   enumeration, often the actual tool real operators use first),
   Impacket's `GetNPUsers.py` (ASREPRoasting — pulls Kerberos hashes
   for accounts with pre-auth disabled) and `GetUserSPNs.py`
   (Kerberoasting — pulls service-account hashes), BloodHound's
   `SharpHound`/`bloodhound-python` collectors (produces JSON describing
   attack paths).
4. **Common early findings/techniques** a real teaching-focused tool
   should recognize and narrate: anonymous/null LDAP bind succeeding,
   AS-REP roastable accounts, Kerberoastable service accounts, a
   domain name being discoverable, SMB signing disabled on a DC
   (relay-attack setup), zone transfer succeeding on DNS.

This is genuinely a big domain. THE PROTOTYPE SCOPE IS DELIBERATELY
SMALL — see "What to build" below. Do not try to cover all of this in
one pass.

## What to build (the actual scope — nothing beyond this list)

### 1. Finding model: minimal extension, not a rewrite

Look at `src/trinity/parsers/nmap.py`'s `Finding` model. If AD data
genuinely doesn't fit the existing fields (`host`/`port`/`service`/
`product`/`version`/`path`/`detail`/etc), propose the SMALLEST possible
addition (e.g. a generic `extra: dict[str, str] | None = None` field
for structured facts like `{"domain": "CORP.LOCAL"}`) rather than
adding many new AD-specific fields to a model every other parser also
uses. If existing fields (especially `detail`, which already carries
free-text script output per the nmap parser's existing pattern) are
sufficient, use those instead of touching the model at all. Explain
your choice in your final report either way.

**False-positive discipline, non-negotiable**: the two most recent
real bugs found in this codebase (2026-09-07, `match/engine.py`'s
`_FTS_STOPWORDS` and `_ms_bulletin_terms` fixes) were BOTH
cross-matching false positives — something Trinity confidently told an
operator that was actually wrong for their box. DC-signature detection
is a HIGH false-positive-risk feature by nature: a lone Windows box
with SMB+RPC open (e.g. HTB Blue/Legacy — single-host, NOT a domain
controller) looks superficially similar to a real DC's port cluster
unless the detector requires a genuinely strong, multi-signal
combination. Do not fire `detect_ad_signals()` off a single port
(e.g. port 445 alone, or even 445+135 alone — Blue has both and is
NOT a DC). Require either (a) a real domain name actually extracted
from script output (the strongest possible signal), OR (b) a
sufficiently large combination of AD-specific ports together (LDAP 389
or Global Catalog 3268/3269 SPECIFICALLY, not just SMB/RPC/NetBIOS
which any Windows box has) before considering it a positive detection.
Write a unit test proving Blue's and Legacy's real port sets (SMB/RPC/
NetBIOS only, no LDAP/Kerberos/DNS) do NOT trigger AD detection, using
those two boxes' REAL nmap facts (already in
`test/fixtures/lame_style_scan.xml`-adjacent territory from earlier
projects — check `docs/COVERAGE_SIMULATION_PROJECT.md`'s corpus or
just re-derive Blue/Legacy's real port facts via web search, same as
that project did) as your negative-control test fixtures BEFORE
building the positive-detection tests. This should not be an
afterthought caught later by `docs/AD_SIMULATION_PROJECT.md`'s
negative-control boxes — build it in from the start.

### 2. New parser: `src/trinity/parsers/ad_recon.py`

A single new module (same file-per-tool-family pattern as the rest of
`parsers/`) that can parse:
- **nmap XML AD-signal extraction**: given an already-parsed nmap XML
  scan (reuse `parse_nmap_xml()` from `parsers/nmap.py` — do NOT
  duplicate nmap XML parsing), detect the AD/DC port-cluster signature
  (see list above) and, if `ldap-rootdse`-style script output is
  present, extract the domain name from it. This can be a function
  like `detect_ad_signals(findings: list[Finding]) -> Finding | None`
  that takes the ALREADY-PARSED findings from a normal
  `parse_nmap_xml()` call and returns one additional synthetic Finding
  (`kind="ad_domain_controller"` or similar) if the signature is
  present — this keeps it additive and testable in isolation, not a
  fork of the existing nmap parser.
- **ldapsearch anonymous-bind output**: real `ldapsearch -x -H
  ldap://<target> -s base namingcontexts`-style output (verify the
  REAL format via web search — do not guess) → Findings for
  users/computers/groups discovered, same shape as
  `enum4linux_ng.py`'s user/share extraction.
- **Impacket `GetNPUsers.py` output** (ASREPRoasting): real tool output
  format when it successfully retrieves a hash → a Finding
  (`kind="asrep_hash"` or similar) noting which account was roastable.
  Do NOT parse/store the actual hash value if you can avoid it, or if
  you do, treat it exactly like `loot.py` already treats sensitive
  values — check that file for the existing pattern before deciding.
- **Impacket `GetUserSPNs.py` output** (Kerberoasting): same idea,
  `kind="kerberoastable_account"`.

Verify EVERY tool's real output format via web search before writing
a parser for it — a wrong assumed format silently parses nothing, same
lesson as the AutoRecon parser project. Cite what you verified in your
final report.

### 3. New suggestion rules in `src/trinity/suggest/engine.py`

Follow the EXACT existing pattern (`_suggest_for_port`-style predicate
+ Suggestion builder, reusing the `fresh()` no-repeat-suggestion
helper already in that file). Add rules for:
- **AD signature detected** → suggest `ldapsearch -x -H
  ldap://<target> -s base namingcontexts` (anonymous LDAP bind check)
  as the natural first AD-aware enum step, phase=`enum`.
- **Port 88 (Kerberos) open + a domain name is known** → suggest
  `GetNPUsers.py <domain>/ -usersfile <userlist> -no-pass` (or the
  correct real Impacket invocation — verify via web search) framed as
  "check for AS-REP roastable accounts," phase=`enum`.
- **LDAP anonymous bind succeeded (from the parser above)** → suggest
  enumerating users via `ldapsearch`/`crackmapexec` (whichever is the
  more standard real-world next step per your research — cite your
  source), phase=`enum`.
- Keep this to 3-5 new rules MAX for the prototype. Do not attempt to
  cover every technique in the "what AD enumeration means" list above
  — pick the highest-value, most common early steps (anonymous LDAP,
  AS-REP roasting) since those require no credentials at all and are
  the most common real "box 1 of an AD chain" starting points.

### 4. ELI5 explain-seed content: `src/trinity/explain_seed/ad_seed.py`

Follow the EXACT existing pattern (see `autorecon_seed.py` from the
2026-09-07 AutoRecon project as your closest, most recent template).
3-5 entries covering: what Active Directory is / why boxes look
different once a domain is involved (aimed at someone who's only ever
done single-host boxes), what Kerberoasting and ASREPRoasting are in
plain terms, what an anonymous LDAP bind is and why it matters. Wire
into `explain_seed/combine.py`'s `_MODULES` list, same as every other
seed module.

### 5. KB entries: 2-3 MAX, in a NEW file `src/trinity/kb/ad_seed.py`

Do not touch the existing `src/trinity/kb/seed.py` — add a sibling
file and wire it into whatever seeds on `trinity init`/
`seed-explanations` the same way `kb/seed.py` already does (check
`cli/main.py`'s `init`/`seed-explanations` commands for exactly how
`kb/seed.py`'s entries get inserted, and mirror that, don't invent a
new loading mechanism). Only entries for things with NO clean
CVE/searchsploit mapping (per
`docs/COVERAGE_SIMULATION_PROJECT.md`'s reasoning about where KB
content actually earns its keep) — e.g. "SMB signing disabled + domain
context = relay attack setup" is a real misconfig-shaped KB candidate;
a specific product CVE is NOT (that's searchsploit's job).

### 6. CLI: reuse `parse-nmap`, do not add a new command

Wire `detect_ad_signals()` into the EXISTING `parse-nmap` command's
flow in `cli/main.py` (same box, same command, additive) rather than
adding a new `parse-ad` verb — an AD box's nmap scan should just
surface AD-aware suggestions automatically once parsed, no new CLI
surface needed for that piece. If you build a parser for ldapsearch/
GetNPUsers/GetUserSPNs output that operators would run separately from
nmap (parts 2c/2d above), THEN add ONE new command mirroring the
`parse-autorecon` shape (see `cli/main.py`'s existing `parse-autorecon`
command from the 2026-09-07 AutoRecon project) — do not add three
separate commands, one per tool; a single command that dispatches by
recognized file/content shape is the right pattern (same "walker/
dispatcher" idea as `parsers/autorecon.py`). If you genuinely can't
make one command clean, STOP and write the tradeoff up in
`docs/AD_ENGINE_OPEN_QUESTIONS.md` rather than shipping three ad-hoc
commands.

## What NOT to build (explicit, because Cursor tends to keep going)

- No BloodHound JSON parsing/visualization in this pass — flag it in
  `docs/AD_ENGINE_OPEN_QUESTIONS.md` as a clearly-scoped follow-up
  instead. It's a much bigger, graph-shaped problem than the rest of
  this list and deserves its own design pass.
- No automatic tool invocation of ANYTHING (ldapsearch, Impacket
  scripts, crackmapexec) — Trinity parses output the operator produces
  themselves in their own terminal, exactly like every other tool
  Trinity already supports. If you catch yourself writing
  `subprocess.run(["ldapsearch", ...])` anywhere outside a TEST
  fixture, stop — that's the auto-run rail from
  `docs/OPEN_DECISIONS.md` and it applies here without exception.
- No hash cracking, no credential storage beyond what `loot.py`
  already does for any other credential type.
- No new report sections.
- No wizard changes.
- No new phase names — AD findings use the EXISTING
  recon/enum/foothold/privesc/post vocabulary.
- No attempt to build a "full AD engine" — this is explicitly the
  first ~20% slice (signature detection + anonymous LDAP + AS-REP
  roasting awareness). Say so plainly in your final report; do not
  imply more is covered than actually is.

## Testing requirements (same bar as every other project in this repo)

1. Unit tests for every new parser function using REAL-shaped fixture
   text (verified against actual tool output via web search, cited in
   test docstrings/comments — same discipline as the AutoRecon parser
   project's `test_parsers_autorecon.py`).
2. Unit tests for every new suggestion rule (same pattern as existing
   `test/unit/test_suggest_engine.py` — check that file's existing
   style before adding to it).
3. Full test suite (`uv run pytest -q`) must pass with ZERO
   regressions before you consider this done. Report the before/after
   count.
4. At least one END-TO-END live verification: build ONE real-shaped
   synthetic nmap XML fixture for an actual, citable AD-flavored HTB/
   THM box (use `docs/COVERAGE_SIMULATION_PROJECT.md`'s sourcing rules
   — real, public, retired box writeup, cited) showing the DC-signature
   detection firing and an AD-aware suggestion appearing in real
   `uv run trinity parse-nmap` / `next` output. Paste the actual real
   captured terminal output in your final report, not a description.

## Work location and process

- Worktree: `git worktree add -b feat/ad-enumeration-prototype
  ../trinity-wt-ad-engine main` — work there, not in the main checkout,
  not in the coverage-simulation worktree.
- Commit incrementally with clear messages as pieces land.
- Do NOT push to origin. Do NOT merge to main. Doc reviews and handles
  both.
- Create `docs/AD_ENGINE_OPEN_QUESTIONS.md` as described above and use
  it liberally — every "should this also..." impulse goes there
  instead of into code.
- Final report must include: what was built (mapped against the six
  numbered sections above, explicitly noting anything skipped/reduced
  from spec and why), the real live-verification output, test pass
  count, and the full contents (or a summary) of
  `docs/AD_ENGINE_OPEN_QUESTIONS.md`.

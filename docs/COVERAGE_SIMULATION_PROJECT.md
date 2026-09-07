# Project: Trinity Coverage Simulation — Scaled Run

Status: ACTIVE. Assigned to Cursor. Doc (Claude) reviews the output file
after each batch. Do not skip the "stop and ask" conditions below —
this project produces a LOT of surface area for silent scope creep.

## Why this exists

On 2026-09-07, Doc ran a 6-box hand-built simulation (3 Linux Easy, 3
Windows Easy: Lame, Shocker, Nibbles, Blue, Legacy, Netmon) against the
real Trinity CLI using synthetic-but-real-fact nmap fixtures. It found
and fixed two live bugs in `src/trinity/match/engine.py` (see git log:
"match/engine: fix cross-service KB false-positives, add MS-bulletin
searchsploit lookup") from just 6 boxes. The clear conclusion: Trinity's
matching/routing logic has real gaps that only show up against real
box data, and finding them at scale (not one hand-built box at a time)
is the fastest way to harden the tool before it's used for real
teaching. This project scales that exact exercise up to ~150-250 boxes.

**The actual goal is NOT "write a KB entry per CVE."** `searchsploit`
already mirrors ~40,000+ real ExploitDB entries locally, for free, no
network call. Most CVE-driven boxes should be solved by Trinity routing
the RIGHT query terms to searchsploit, not by hand-authoring content
that already exists elsewhere. Reserve new KB entries for the minority
of cases with no clean CVE mapping (default creds, chained misconfigs,
app-specific logic bugs like Nibbleblog's upload flow or PRTG's command
injection). This distinction matters — see "Failure bucketing" below.

## Ground rules (read before starting)

1. **Real facts only, always verified.** Every box's "ground truth"
   (open ports, service versions, script output, the actual solve
   path) must come from a real, citable, public writeup — same
   sourcing standard `docs/METHODS_INDEX.md` already enforces:
   public, non-paywalled, RETIRED boxes only (0xdf, ippsec transcripts,
   official platform writeups, TJnull-style OSCP-prep lists,
   VulnHub author writeups). Never invent port numbers, versions, or
   solve paths — web_search + read the actual writeup before building
   a fixture. If you can't find a citable writeup for a box, skip it.
2. **Never touch the real operator's `~/.trinity/` data.** Every
   simulation run MUST happen under an isolated `$HOME` (e.g.
   `HOME=/tmp/trinity_sim_batch_NNN`), same pattern as Doc's 2026-09-07
   session. Never run simulations against the default HOME.
3. **Do work in a git worktree, not the main checkout.** Create
   `git worktree add -b coverage-sim-findings ../trinity-wt-coverage-sim main`
   before starting. Commit progress incrementally inside that worktree.
   Do NOT merge to main yourself — Doc reviews and merges after
   examining the findings file.
4. **Fixtures are synthetic but REAL-shaped.** Build nmap XML (and
   gobuster/other tool output where relevant) fixtures using the exact
   real facts from the writeup — same approach as
   `test/fixtures/sim_*.xml` patterns Doc used (now deleted from main,
   recreate the pattern fresh per box in this worktree's own fixture
   dir, e.g. `test/fixtures/coverage_sim/<box_name>.xml`).
5. **Run against the REAL CLI, not by reading source and guessing.**
   Every box's result must come from an actual `uv run trinity
   parse-nmap ... / next / suggest / hint` invocation with captured
   real output. No fabricated/assumed results — same standard as every
   other task in this repo's recent history.
6. **STOP AND ASK Doc (leave a clearly marked entry in the findings
   file, do not silently decide) when:**
   - A box's real solve path requires a capability Trinity doesn't
     have ANY code for yet (e.g. Kerberos/LDAP/AD enumeration,
     Windows-specific privesc chains beyond MS-bulletin RCEs, binary
     exploitation/buffer overflows, Active Directory anything). Log it
     as a "capability gap" (see taxonomy below), do NOT attempt to
     build the missing capability yourself in this project.
   - A fix would change matching/suggestion PRIORITY/ORDERING logic
     (e.g. "should a CRITICAL verified exploit ever outrank the
     phase-based recon-first default in `next`?") rather than pure
     coverage (new query routing, new KB entry). That's a design
     question for Doc, not something to decide unilaterally mid-batch.
   - You've found more than ~5 boxes in a row hitting the exact same
     root cause — stop, log ONE clear finding describing the pattern
     and which boxes reproduce it, then move to a different box
     category rather than grinding out 40 identical findings.

## Corpus construction

Target: ~150-250 boxes total, prioritizing DIVERSITY over raw count
(today's 6-box run found 2 real bugs — patterns cluster fast; more
value comes from covering new territory than re-confirming the same
gap 50 times). Build the corpus across these axes, roughly balanced:

- **Difficulty**: Easy and Medium primarily (skip Hard/Insane for this
  pass — those usually chain multiple novel steps that are lower
  signal-to-noise for a coverage sweep; flag if you disagree after
  seeing early results).
- **Platform**: HTB retired boxes (largest pool, best writeup
  coverage), THM rooms, VulnHub (`vulnhub.com`, all retired/public by
  nature).
- **OS split**: aim for roughly 40% Linux, 40% Windows, 20%
  Active-Directory-flavored (these will mostly land in the "capability
  gap" bucket per rule 6 above — that's expected and useful signal,
  don't skip them just because they'll fail).
- **Vuln category spread**: don't cluster on "SMB RCE" boxes just
  because they're easy to find writeups for. Deliberately include:
  web app CVEs (CMS plugins, known frameworks), file upload RCEs,
  SSRF/LFI/deserialization, default/weak creds, SUID/sudo misconfig
  privesc, Windows service misconfig privesc, Kerberoasting/AD
  (expect capability-gap findings here), classic FTP/SMB backdoors,
  outdated-software CVEs across a range of services (not just
  SMB/SSH — include Redis, Jenkins, Tomcat, phpMyAdmin, etc).

Maintain a running corpus manifest at
`test/fixtures/coverage_sim/MANIFEST.md` — one row per box: name,
platform, OS, difficulty, primary vuln category, writeup URL(s) used,
status (queued/built/simulated/scored).

## Per-box procedure

For each box:

1. **Research.** web_search + read the real writeup(s). Extract:
   exact open ports/services/versions/banners, any nmap NSE script
   output relevant to the vuln (vuln scripts, anon-login confirmations,
   etc), the ACTUAL solve path (foothold method + CVE/technique name if
   applicable, privesc method + CVE/technique if applicable).
2. **Build fixture(s).** Real-shaped nmap XML at minimum (see existing
   `test/fixtures/lame_style_scan.xml` for the exact expected format).
   Add gobuster/other tool output fixtures if the solve path depends on
   web enumeration content, not just port/service info.
3. **Simulate.** Isolated `$HOME`, run in this order and capture full
   output:
   ```
   uv run trinity init
   uv run trinity parse-nmap <fixture> --box "<name>"
   uv run trinity next --box "<name>"
   uv run trinity suggest --box "<name>"
   uv run trinity hint --box "<name>"   # once, to confirm ladder starts sanely
   ```
4. **Score**, per this rubric:
   - **PASS**: Trinity's match/suggest output puts the real solve
     path's key finding/exploit in front of the operator, unprompted
     (in `parse-nmap` output, `next`'s top pick, or `suggest`'s list) —
     doesn't have to be the literal #1 line, but must be clearly
     surfaced, not buried/absent.
   - **PARTIAL**: Trinity correctly identifies the right RECON step
     (the port/service that matters) but has no specific
     match/KB/searchsploit hit for the actual named vulnerability —
     this is a legitimate "AI Harness would close this" outcome, not
     automatically a bug. Still log it (see taxonomy).
   - **FAIL**: Trinity's output is actively wrong or misleading for
     this box (cross-service false match, wrong recommended tool,
     nonsensical suggestion) — this is always a bug, prioritize
     writing these up clearly.
   - **CAPABILITY GAP**: the real solve path needs something Trinity
     has zero code path for (AD/Kerberos, binary exploitation, etc).
     Not a bug — a scoping note for a future project.
5. **Log** to `findings/coverage_sim_log.jsonl` (append-only, one JSON
   object per box) AND to a running human-readable summary at
   `findings/coverage_sim_summary.md`. JSONL schema:
   ```json
   {
     "box": "string",
     "platform": "htb|thm|vulnhub",
     "os": "linux|windows",
     "difficulty": "easy|medium",
     "vuln_category": "string",
     "writeup_urls": ["..."],
     "result": "pass|partial|fail|capability_gap",
     "real_output_excerpt": "string (the actual captured CLI output, trimmed to the relevant part)",
     "root_cause": "string or null (only for fail/partial - your best diagnosis)",
     "bucket": "searchsploit_routing|missing_kb_entry|missing_suggest_coverage|capability_gap|other",
     "notes": "string"
   }
   ```

## Known high-value gap — check this FIRST, before the general sweep

Doc already confirmed a specific, concrete instance of this pattern
during the 2026-09-07 6-box run, but did not fix it (ran out of scope
for that session). Real evidence, verify it yourself before trusting
this paragraph: `searchsploit nibbleblog`, `searchsploit prtg`, and
`searchsploit shellshock` all return real, locally-mirrored exploits
RIGHT NOW — but Trinity found none of them for the Nibbles/Netmon/
Shocker boxes in that session. Root cause: `match_finding()` in
`src/trinity/match/engine.py` only ever calls `searchsploit.search()`
`if finding.product`. A gobuster/ffuf path discovery (`Finding(kind=
"path", ...)`, e.g. `/nibbleblog/`, `/cgi-bin/`) never populates
`.product` — it's a URL path, not a service banner — so the exploit
sitting right there locally never gets queried. This is the SAME
shape of bug as today's two fixes (real signal already present in the
Finding, searchsploit already has the answer, nothing routes them
together), just on `kind="path"` findings instead of `kind="port"`.

Before running the full 150-250 box sweep, spend a focused early pass
(bucket 1, "fix live" territory) on this specific class:
1. For any `Finding(kind="path")` whose `path` contains a plausible
   app/product name (the segment after the last meaningful `/`, e.g.
   `nibbleblog` from `/nibbleblog/`, `phpmyadmin` from `/phpmyadmin/`),
   feed that segment to `searchsploit.search()` as an additional query,
   same pattern as today's `_ms_bulletin_terms` addition — extract,
   don't guess; a bare path segment used naively WILL produce noise
   for generic paths like `/admin/` or `/login/`, so only fire this
   for path segments that look like a specific product/app name, not
   for `_INTERESTING_PATH_MARKERS`-style generic terms (see
   `suggest/engine.py`'s existing `_INTERESTING_PATH_MARKERS` list for
   what generic looks like — do NOT searchsploit-query those).
2. Verify against the real Nibbles/Netmon boxes (build fixtures per
   the per-box procedure below) that this concretely surfaces the
   Nibbleblog file-upload exploit and the PRTG exploits that are
   already sitting in searchsploit's local mirror.
3. Shellshock (Shocker box) is a DIFFERENT shape — it is not a
   product-with-a-version CVE, it's a technique (crafted HTTP header
   against any CGI script on a vulnerable Bash). A path-name query
   alone won't surface it cleanly. This one is better suited to
   `missing_suggest_coverage` (a new suggestion rule: "a `/cgi-bin/`
   path was found → this is specifically worth testing for Shellshock,
   here's how" — phase=`foothold`) plus a short `missing_kb_entry`
   proposal explaining the technique, not a searchsploit-routing fix.
   Log it in that bucket rather than forcing it into bucket 1.

## Quality control on today's stopword fix — watch for regressions, not just wins

Today's `_FTS_STOPWORDS` fix (see git log,
"match/engine: fix cross-service KB false-positives...") is
correct but was tuned against exactly 6 boxes. Confirmed side effect,
verify it yourself: `_fts_query("Windows Server 2003")` now reduces to
the single bare token `"2003"` — a year number specific enough to
survive the length filter but generic enough to risk NEW cross-matches
against anything else that happens to mention 2003. As you run the
broader sweep:
- If you see a NEW cross-service false-positive that traces back to a
  bare/near-bare token surviving `_FTS_STOPWORDS` (numbers, 3-4 letter
  fragments), log it in `searchsploit_routing`-adjacent bucket `other`
  with a clear note, and you MAY extend `_FTS_STOPWORDS` further with
  the same justification/regression-test discipline as today's fix —
  but do not blanket-raise the minimum token length or otherwise
  weaken matching broadly; keep fixes surgical and per-token-justified,
  same as today.
- If you see a FALSE NEGATIVE (a real, legitimate KB/searchsploit match
  that should have fired but got suppressed because its only
  distinguishing words are in `_FTS_STOPWORDS`), log that too — this is
  the opposite failure mode and equally worth knowing about. Do not
  silently remove words from `_FTS_STOPWORDS` to fix this without
  understanding whether that reopens today's original bug for that
  specific case first.

## Failure bucketing (this is the part Doc actually needs)

Every FAIL and PARTIAL must be bucketed as one of:

1. **`searchsploit_routing`** — searchsploit genuinely has a matching
   exploit locally (verify with a real `searchsploit <terms>` call
   before claiming this bucket) but Trinity's query-term extraction
   didn't find it. This is the highest-leverage bucket — a single code
   fix here can resolve many boxes at once, same as today's MS-bulletin
   fix. If you find a clean, mechanical, well-tested fix for a
   `searchsploit_routing` gap (same shape as today's fix — extract a
   different pattern from `detail`/`product`/`version` and feed it to
   `_searchsploit_query_terms`/the new `_ms_bulletin_terms`-style
   helper), you MAY implement + test + commit it in this worktree.
   Always add a regression test using the real box's data (same
   pattern as `test_ms_bulletin_in_detail_surfaces_matching_searchsploit_exploit`).
   Never change matching PRIORITY/ORDERING — only WHICH queries get
   asked.
2. **`missing_kb_entry`** — no CVE/searchsploit mapping exists at all
   (confirm this — don't assume); the vulnerability is a
   misconfig/default-cred/app-logic bug that would need a hand-authored
   KB entry (same shape as the existing 6 in `src/trinity/kb/seed.py`).
   Do NOT author these yourself in this project — just log the
   candidate content (title/summary/detail/match_service/match_version/
   tags/severity, following the existing seed.py shape exactly) as a
   proposal in the findings file for Doc to review/curate in a
   dedicated batch. Authoring KB content needs human judgment on
   accuracy/tone; don't ship it silently mid-simulation-sweep.
3. **`missing_suggest_coverage`** — the suggest engine
   (`src/trinity/suggest/engine.py`) has no branch at all for a
   service/port that the real writeup found meaningful (e.g. no
   Redis/Jenkins/Tomcat-specific suggestion, no DNS/LDAP awareness).
   Log the port/service/what-the-real-operator-did as a proposed new
   `_suggest_for_port`-style branch. Do NOT implement new suggest
   branches yourself in this project unless it's a trivially obvious,
   well-precedented addition (e.g. adding one more well-known service
   name to an EXISTING branch's service-name check) — flag anything
   that requires new phrasing/rationale/nudge text for Doc's review,
   since that's voice/content work, not mechanical routing.
4. **`capability_gap`** — see rule 6 above. Log and move on.
5. **`other`** — anything that doesn't fit cleanly; explain why in
   `notes`.

## What you're authorized to fix live vs. what you log only

**Fix + test + commit live** (bucket 1 only, mechanical routing fixes):
- New regex/extraction patterns in `match/engine.py` that feed
  ADDITIONAL real signal to `searchsploit.search()` calls (same shape
  as `_ms_bulletin_terms`).
- Obvious FTS false-positive fixes if you find another cross-match bug
  like today's (extend `_FTS_STOPWORDS` with well-justified additions,
  same pattern, always with a regression test proving the specific
  cross-match it fixes).
- Always run the FULL test suite (`uv run pytest -q`) after each fix
  and confirm no regressions before committing.

**Log only, never implement**: new KB entries (bucket 2), new
suggest-engine branches with new phrasing (bucket 3), anything
touching AD/Kerberos/capability gaps (bucket 4), anything touching
`advisories.py`'s priority ordering, anything touching the wizard,
anything touching CLI command surface/UX.

## Cadence and checkpoints

This is expected to take multiple sessions/days, not one sitting.
After every ~25 boxes: commit progress in the worktree, update
`findings/coverage_sim_summary.md`'s top section with a running
tally (pass/partial/fail/capability_gap counts, bucket breakdown for
fails/partials, list of any live fixes shipped so far with commit
hashes). This lets Doc check in incrementally without needing you to
finish the whole batch first.

**Target for first checkpoint Doc will review: ~100-150 boxes.** Stop
there and wait rather than pushing to 250 in one go — Doc wants to
sanity-check the bucketing/approach on a mid-size batch before
authorizing the rest.

## Deliverable

At each checkpoint: the worktree (`../trinity-wt-coverage-sim`, branch
`coverage-sim-findings`) containing:
- `test/fixtures/coverage_sim/` — all fixtures built so far, plus
  `MANIFEST.md`
- `findings/coverage_sim_log.jsonl` — full structured log
- `findings/coverage_sim_summary.md` — human-readable running summary
  with the tally and bucket breakdown at the top
- Any live bucket-1 fixes, committed individually with clear messages
  and passing the full test suite

Do not push to origin. Do not merge to main. Doc reviews and handles
both after examining the findings.

# Coverage simulation — checkpoint 1

**Worktree:** `/home/alexander/Work/trinity-wt-coverage-sim`  
**Branch:** `coverage-sim-findings`  
**Boxes simulated:** 20 (honest cited fixtures; not 100–150). Stopped expanding Apache-httpd Easy web boxes after the same product-query noise repeated.

## Tally

| result | count |
|--------|------:|
| pass | 6 |
| partial | 11 |
| fail | 1 |
| capability_gap | 2 |
| **total** | **20** |

### Bucket breakdown (fail + partial + gap)

| bucket | boxes |
|--------|-------|
| searchsploit_routing | grandpa (IIS6 crowding), armageddon (Drupal in http-generator), netmon PRTG-in-title (also fail/other) |
| missing_kb_entry | devel, jerry, bashed, sense, mirai |
| missing_suggest_coverage | shocker, granny, knife, valentine |
| capability_gap | forest, active |
| other | netmon (vsftpd-on-any-ftp CRITICAL) |

PASS: lame, nibbles, blue, legacy, optimum, beep.

## Live fixes shipped

| commit | what |
|--------|------|
| `dc00d8b` | Path findings: last product-shaped segment → searchsploit. Skip generic web segments (incl. cgi-bin). Regression: `/nibbleblog/` surfaces Nibbleblog 4.0.3 file-upload. |
| `7cf4071` | One searchsploit call **per** MS-bulletin. Legacy had ms08-067 **and** ms17-010 in one detail string; AND query returned zero. Also skip-listed `themes`/`javascript`/`classes`/`widgets` after Sense `/themes/` → WordPress-theme exploits. |

**Not changed:** match priority/ordering, default `limit=5`, advisories, wizard, CLI surface, KB seed, new suggest phrasing.

## Path-fix verification (Nibbles / Netmon / Shocker)

All CLI runs: isolated `HOME=/tmp/trinity_sim_<box>`, `PYTHONPATH=src`, `scripts/trinity-cli.py`. Full transcripts in `findings/transcripts/`.

### Nibbles — PASS (path fix worked)

Gobuster `/nibbleblog` (attested path; 0xdf found it via HTML comment, then gobusted inside it):

```
$ trinity parse-nmap .../nibbles_gobuster.txt --box nibbles
  Nibbleblog 3 - Multiple SQL Injections  [HIGH]  (score 0.9, searchsploit)
  Nibbleblog 4.0.3 - Arbitrary File Upload (Metasploit)  [HIGH]  (score 0.9, searchsploit)
  Found in local ExploitDB (EDB-ID 38489), CVE-2015-6967;OSVDB-127059. Verified working.
  PoC: /usr/share/exploitdb/exploits/php/remote/38489.rb
```

`next` still ranks `searchsploit openssh 7.2p2` first (ordering not touched). Exploit is clearly surfaced in parse-nmap.

### Netmon — FAIL / path-fix does **not** apply

Writeups: PRTG is the **root page** (nmap `product=Indy httpd`, extrainfo `Paessler PRTG bandwidth monitor`, `http-title: Welcome | PRTG Network Monitor`). There is no `/prtg/` gobuster hit to invent.

```
$ trinity parse-nmap .../netmon.xml --box netmon
10.10.10.152:21 ftp (Microsoft ftpd)
  vsftpd 2.3.4 backdoor (CVE-2011-2523)  [CRITICAL]  (score 0.9, user_curated)  ← WRONG
  Anonymous FTP login  [MEDIUM]  ← real user foothold
10.10.10.152:80 http (Indy httpd 18.1.37.13946)
  HTTP directory brute-forcing ... [INFO]
  (no PRTG, no CVE-2018-9276)
```

`searchsploit prtg` has local exploits; Trinity never queried `prtg`.

### Shocker — PARTIAL (`missing_suggest_coverage`)

`/cgi-bin/` correctly **not** sent to searchsploit. `/cgi-bin/user.sh` is not product-shaped (dot). No Shellshock.

```
$ trinity parse-nmap .../shocker_gobuster.txt --box shocker
  /cgi-bin  → No local match
  /cgi-bin/user.sh → FTS token "user" cross-matched Anonymous FTP + vsftpd 2.3.4 [CRITICAL]
```

Did **not** add a `/cgi-bin/` → Shellshock suggest rule (new phrasing). Proposal logged.

## Pytest

| when | result |
|------|--------|
| before this worktree's code changes | not re-run on `bd81f92`; original `test_match_engine.py` had 14 tests in the match file |
| after path-fix `dc00d8b` | **348 passed** |
| after bulletin-split `7cf4071` | **349 passed** (full suite, `PYTHONPATH=src`) |

## `_FTS_STOPWORDS` / `2003`

- Confirmed in code: `windows`/`server` are stopwords, so `"Windows Server 2003"` → `"2003"`.
- This 20-box batch had **no** nmap product string `Windows Server 2003`. Grandpa/Granny product is `Microsoft IIS httpd 6.0`.
- Related FTS FPs seen: token `user` from `/cgi-bin/user.sh` → FTP KB; token `anonymous` in FTP detail → SMB null-session KB (score 0.6).
- Did **not** blanket-raise min token length. Did **not** remove stopwords.

## STOP AND ASK

1. **Apache httpd product query noise (5+ boxes, same root cause).** Nibbles, Shocker, Knife, Valentine, Armageddon, Beep: `searchsploit` on `Apache httpd` + a 2.x/2.4 version still returns `Apache + PHP < 5.3.12 cgi-bin RCE` [CRITICAL] and `OpenFuck` (2002). Trinity did not filter version ranges. Logged **one** pattern; stopped adding more Apache Easy web boxes. Design question: filter searchsploit hits by version sanity, or leave as "operator still sees ExploitDB noise"? **Do not change ordering here.**

2. **vsftpd 2.3.4 KB matches any `service=ftp`.** Stage 1 uses `match_service IN (ftp)` and only *boosts* score when version matches. Netmon + Devel (Microsoft ftpd) got CRITICAL vsftpd backdoor. Same class as the original cross-service FTS bug, but it is exact-service matching, not FTS. Fix would be "require product/version for that KB row" — adjacent to match rules, not a new query term. Asking before touching it.

3. **`limit=5` crowding.** Grandpa's intended IIS6 WebDAV RCE is in ExploitDB but DoS titles fill the five slots. Raising limit or re-ranking RCE vs DoS is **priority/ordering**. Not changed.

4. **nmap hostscripts.** Real `smb-vuln-ms17-010` often lands in `<hostscript>`, which `parse_nmap_xml` ignores. Fixtures attached scripts to port 445 so the existing bulletin path can fire. Parser gap logged, not implemented.

5. **http-title / extrainfo / http-generator → searchsploit.** Netmon PRTG, Armageddon Drupal 7, Beep Elastix. Mechanical-ish but fuzzier than path/bulletin regex. Logged as `searchsploit_routing`; not implemented this checkpoint.

6. **AD (Forest, Active).** Capability gap as specified. No AD code in this worktree.

7. **Shellshock suggest rule.** Logged as `missing_suggest_coverage` + optional KB proposal. Not implemented (new phrasing).

## How far this got

Twenty retired HTB Easy boxes, mixed Linux/Windows, with real CLI transcripts. Not 100–150. Diversity is decent for a first checkpoint (SMB RCE, CMS upload, HFS, Tomcat creds, FTP webroot, WebDAV, Shellshock, Heartbleed, PHP backdoor, Drupal, pfSense, Pi default creds, two AD DCs). No THM/VulnHub yet. No Medium boxes yet.

Full transcripts: `findings/transcripts/<box>.txt`  
JSONL: `findings/coverage_sim_log.jsonl`  
Fixtures: `test/fixtures/coverage_sim/`

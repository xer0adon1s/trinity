# Coverage simulation — checkpoint 2 (first Doc-review target)

**Worktree:** `/home/alexander/Work/trinity-wt-coverage-sim`  
**Branch:** `coverage-sim-findings`  
**Boxes simulated:** **102** (cited fixtures + real CLI transcripts). This is the ~100–150 first-checkpoint stop. Do not push or merge — Doc reviews.

Prior checkpoint was 20 HTB Easy (`90c04fa`). This session added THM, VulnHub, Medium, and new vuln categories. Did **not** re-expand the Apache-httpd Easy-web product-noise pattern already logged.

Baseline before new boxes: `.venv/bin/pytest -q` → **355 passed** (after merge with main: KB version-scoping, KB service-scoping in FTS stage 2, explain-cache-key). After live routing fixes this session: **359 passed**.

## Tally

| result | count |
|--------|------:|
| pass | 17 |
| partial | 80 |
| fail | 0 |
| capability_gap | 5 |
| **total** | **102** |

Netmon was FAIL at checkpoint 1 (vsftpd 2.3.4 CRITICAL on Microsoft ftpd). Re-sim after main `3b4bd84` version-scope: that CRITICAL is gone. Rescored to **PARTIAL** (PRTG still unrouted). No remaining FAILs.

### Bucket breakdown (fail + partial + gap)

| bucket | count | what it means in this batch |
|--------|------:|-----------------------------|
| missing_kb_entry | 40 | Default creds, upload filters, SQLi/cmdi/SSTI/NoSQL, content leaks, Jenkins/Tomcat/ColdFusion identity without a banner CVE |
| searchsploit_routing | 19 | ExploitDB has the hit (`searchsploit <terms>` verified) but Trinity did not ask the right query — mostly **http-title / http-generator / extrainfo** (Drupal, Joomla, GitLab, Koken, PRTG, Webmin-as-MiniServ, Bludit-as-Blunder, NSClient++, Fuel CMS in title) |
| missing_suggest_coverage | 17 | No branch for DNS AXFR, NFS/mountd, finger, AJP/Ghostcat, LFI-as-primary, WebDAV PUT on lighttpd, SSTI, `/ping?ip=` cmdi |
| capability_gap | 5 | AD AS-REP/Kerberoast (forest, active, sauna, attacktivedirectory); custom BOF (brainpan) |
| other | 4 | Version-era / product-only ExploitDB noise: Broker (ActiveMQ 2016 vs CVE-2023-46604 not in local EDB), Help/Node/UltraTech (Node.js → node-serialize CRITICAL, wrong app) |

**PASS (17):** lame, nibbles, blue, legacy, optimum, beep, solidstate, irked, traverxec, ice, kenobi, steelmountain, celestial, kioptrix1 (Samba trans2open alt path), basicpentesting1 (ProFTPD 1.3.3c backdoor), access (anon FTP *is* the foothold), brooklynninenine (anon FTP note *is* the start).

## Platform / difficulty mix

| | HTB | THM | VulnHub | total |
|--|----:|----:|--------:|------:|
| Easy | many | 18 | 12 | |
| Medium | first Mediums this project (arctic, postman-era through poison/haircut/mango/magic/node/broker/celestial/cronos/…) | relevant | stapler, goldeneye, brainpan | |
| Linux / Windows / AD | mixed; AD kept to 4 boxes (expected gaps) | | | |

New categories vs checkpoint 1: Redis, James, UnrealIRCd, Nostromo, Icecast, ProFTPD mod_copy + 1.3.3c backdoor, ColdFusion/CFIDE, Jenkins/Jetty, Oracle TNS, Finger, GitLab-in-title, NFS/Umbraco, Fuel CMS, Ghostcat/AJP, ActiveMQ, node-serialize, request-baskets, Koken, Drupal/Joomla-in-generator, Kioptrix OpenFuck-era + LotusCMS + login SQLi, Brainpan BOF, Magento, Bludit, Adminer, HelpDeskZ, Mattermost, NSClient++, Access DB, NFS+LFI/SMB write, SSTI, NoSQL, command injection, WebDAV PUT, WordPress brute, phpLiteAdmin, exposed SSH keys.

## Live fixes shipped this session

| commit | what |
|--------|------|
| `7729518` | Strip nmap role suffixes/phrases (`smtpd\|pop3d\|nntpd\|listener`, `streaming media server`, `key-value store`, `remote admin`). Icecast + JAMES now hit. |
| `9797be8` | Skip English-word path segments that are product-shaped but not products: `fuel`, `simple`, `internal`, `music`, `artwork`, `askjeeves`. |
| `2b95f26` | Strip `openwire transport` / `express framework`. Celestial node-serialize PASS; Broker at least queries ActiveMQ. |
| `ce1914a` | Skip `/uploads/` (plural of already-skipped `upload`). Haircut was querying random file-upload exploits. |

**Not changed:** match priority/ordering, default `limit=5`, advisories, wizard, CLI surface, KB seed, new suggest phrasing, title/generator/extrainfo parsers, version-range filters.

## Pytest

| when | result |
|------|--------|
| after merge with main, before new boxes | **355 passed** |
| after Icecast/JAMES phrase+suffix strip `7729518` | **358 passed** |
| after OpenWire/Express + skip-list + uploads | **359 passed** (`test_match_engine.py` 23) |

## STOP AND ASK

1. **Apache / product-only version-sanity (still the #1 pattern, not re-expanded).** Almost every Apache 2.4.x box still surfaces `Apache + PHP < 5.3.12 cgi-bin RCE [CRITICAL]` and OpenFuck. Same for product-only `OpenSSH`, `vsftpd` with no version (Stapler → 2.3.4 CRITICAL via searchsploit, not KB), `Node.js` → node-serialize on Help/UltraTech/Node (Celestial is the one box where that is correct), `ActiveMQ` → 2016 CVEs (CVE-2023-46604 is **not** in this machine's ExploitDB; `searchsploit 46604` is a different Windows DoS). Design question: filter searchsploit hits by version sanity / RCE-vs-DoS, or leave as operator-visible ExploitDB noise? **Do not change ordering/limit here.**

2. **http-title / http-generator / extrainfo → searchsploit.** Recurs on Netmon (PRTG), Armageddon/Bastard/DC-1 (Drupal), DC-3 (Joomla), Ready (GitLab), Photographer (Koken), Ignite (FUEL CMS title), Blunder (generator `Blunder` ≠ Bludit), Source/Postman (MiniServ vs Webmin in extrainfo), Servmon (title NSClient++), Delivery (title Mattermost). `searchsploit prtg|drupal|joomla|gitlab|koken|fuel cms|bludit|webmin|nsclient` all have local hits. Mechanical-ish but fuzzier than path/bulletin regex. **Not implemented.**

3. **English last-segment skip-list is not a dictionary.** After `themes` then `fuel/simple/internal/music/artwork/askjeeves` then `uploads`, the same FP class hit `/writeup` (WP plugin noise), `/mage` (4Images, not Magento), `/torrent` (BitTorrent client BOF), `/about`, `/department`. Stopped adding one-off English skips. Either accept the noise or design a tighter product-shaped rule. **Do not keep expanding the frozenset.**

4. **`/ona` length ≥ 4.** OpenAdmin's attested path is 3 characters. `searchsploit OpenNetAdmin` works. Lowering the gate to 3 would query other short junk. Do not invent `OpenNetAdmin` from `ona`.

5. **Product-only fallback when versioned AND is empty/wrong.** Redis `4.0.9` misses “4.x” unauth/SSH-key write; Oracle TNS `11.2.0.2.0` ANDs to zero. Adjacent to ordering if we *also* keep the versioned query. Asking before adding a fallback call.

6. **`limit=5` crowding / RCE vs DoS.** Grandpa IIS6 WebDAV; Kioptrix1 OpenFuck (mod_ssl in *extrainfo*, Samba alt path still PASSed). Priority/ordering. Not changed.

7. **nmap hostscripts** still ignored (`smb-vuln-*` fixtures stay on the port). Parser gap logged, not implemented.

8. **AD + custom BOF.** Forest, Active, Sauna, Attacktive Directory, Brainpan. No AD/BOF code in this worktree.

9. **New suggest phrasing (log only):** `/cgi-bin/` → Shellshock; finger → user enum; DNS → AXFR; mountd/nfs → `showmount -e`; ajp13/8009 → Ghostcat; http-methods PUT → HTTP PUT upload; LFI `file=` parameters; `/ping?ip=` → cmdi; message boards → SSTI.

10. **Stapler vsftpd 2.3.4 CRITICAL** is searchsploit product-only (nmap had no version), **not** a regression of main's KB version-scope gate. Confirmed in engine: empty `finding.version` skips the KB row in both stages.

## How far this got

102 retired Easy/Medium boxes across HTB, THM, and VulnHub, with real CLI transcripts under isolated `$HOME`. Diversity is now the point of the corpus (first THM/VulnHub/Medium were zero at checkpoint 1). Ran out of *clearly new* categories faster than raw count — another 50 Apache-shaped web boxes would only reconfirm STOP-AND-ASK #1 and #2.

Full transcripts: `findings/transcripts/<box>.txt`  
JSONL: `findings/coverage_sim_log.jsonl`  
Fixtures: `test/fixtures/coverage_sim/`  
Citation scratch: `findings/coverage_sim_thm_vulnhub_research.md`, `findings/coverage_sim_batch6_research.md`

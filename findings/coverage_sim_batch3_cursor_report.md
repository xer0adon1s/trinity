# Coverage Sim Batch 3 — Cursor report (for Doc)

**Worktree:** `/home/alexander/Work/trinity-wt-coverage-sim-batch3`  
**Branch:** `coverage-sim-batch3` (not merged, not pushed)  
**Date:** 2026-09-07

## What was built

- 20 new retired HTB boxes (10 Linux + 10 Windows), denylist-checked against the existing 102 names.
- Real-shaped nmap (+ gobuster where attested) fixtures under `test/fixtures/coverage_sim/`.
- Isolated-`$HOME` CLI runs (`init` → `parse-nmap` → `next` → `suggest` → `hint`); transcripts in `findings/transcripts/`.
- Appended `MANIFEST.md`, 20 JSONL lines (122 total), checkpoint-3 section prepended to `findings/coverage_sim_summary.md`.
- Research citations: `findings/coverage_sim_batch3_research.md`.

## Final tally (batch 3)

| result | count |
|--------|------:|
| pass | 2 (hawk, conceal) |
| partial | 15 |
| fail | 0 |
| capability_gap | 3 (omni, fuse, support) |
| **total** | **20** |

Corpus continuity: **122** boxes in the JSONL ledger.

## Live fixes shipped (bucket 1 only)

All in `src/trinity/match/engine.py` + regression tests in `test/unit/test_match_engine.py`. Full suite: **421 → 424 passed**.

1. **Strip `http console` / `process manager`** from `_NOISY_PRODUCT_PHRASES`  
   - Hawk: `H2 database http console` → `H2 database` → Alias RCE CRITICAL surfaces.
2. **`_process_manager_terms(detail)`** — extract `X process manager` from nmap extrainfo/detail and query searchsploit  
   - Luanne: extrainfo `Supervisor process manager` → Supervisor XML-RPC RCE surfaces (foothold is still Lua cmdi — scored partial).
3. **Underscore path segments** — `/pandora_console/` → query leading `pandora`  
   - General hardening; Pandora box itself has no public console path (localhost-only per 0xdf — fixture does not invent one).

**Not touched:** priority/ordering, KB seed, suggest phrasing, title/generator parsers, English skip-list, AD/IoT capabilities.

## Open items for Doc's review (log-only — not implemented)

### searchsploit_routing proposals
- **Love:** `http-title: Voting System using PHP` — `searchsploit voting system` has EDB-49445. Same deferred title/generator class as checkpoint-2 STOP-AND-ASK #2. Highest-leverage remaining routing hit this batch.
- **Hawk Drupal `http-generator`:** still unqueried (foothold also has anon FTP, which is why hawk still PASSed).

### missing_kb_entry proposals (candidate seed shape — content for Doc)
- Cap IDOR `/download/<id>` PCAPs  
- Luanne `/weather` Lua `city=` cmdi  
- Seal NGINX/Tomcat `;` path bypass for `/manager/html`  
- Spectra `wp-config.php.save` / nano `.save` leaks  
- GoodGames Werkzeug login SQLi + Jinja SSTI  
- Paper WordPress ≤5.2.3 draft view CVE-2019-17671 (`?static=1`)  
- Previse execute-after-redirect + `file_logs.php` `delim=` cmdi  
- Bastion SMB `.vhd` → secretsdump; mRemoteNG `confCons.xml` decrypt  
- Heist Cisco IOS type 5/7 hashes in support attachments  
- Nest Reporting Service V1.2 (CRLF-sensitive)

### missing_suggest_coverage proposals
- Haystack: `:9200` JSON → Elasticsearch `_cat/indices` (nmap product is nginx — do not invent product)  
- Pandora: `snmpwalk -v2c -c public` when UDP 161 / SNMP is in scope  
- Driver: MFP firmware upload → `.scf` / Responder  
- Sniper: confirms existing LFI-as-primary suggest proposal  
- Conceal prerequisite: SNMP + IPsec VPN before the anon-FTP view (fixture uses post-VPN ports intentionally)

### capability_gap
- **Omni:** Windows IoT SirepRAT  
- **Fuse:** AD DC + PaperCut + Capcom.sys (1/2 allowed AD Windows)  
- **Support:** AD UserInfo.exe → LDAP → RBCD (2/2)

## Judgment calls Doc may want to revisit
1. Hawk scored **PASS** on anon-FTP-as-foothold-start (Access/BrooklynNineNine precedent) even though Drupal generator is still dark.  
2. Conceal scored **PASS** on post-VPN TCP facts; IPsec/SNMP start is logged, not failed.  
3. Title→searchsploit for Love left unimplemented per prior STOP-AND-ASK — implement in a dedicated Doc-reviewed change if desired.

## Git state
Branch `coverage-sim-batch3` has incremental commits for research, fixtures/transcripts/logs, and the live routing fixes. Ready for Doc review; no merge/push from Cursor.

# AD engine prototype — final report

Worktree: `../trinity-wt-ad-engine` (`feat/ad-enumeration-prototype`).
Not pushed, not merged.

This is the first ~20% slice: DC-signature detection, anonymous LDAP,
AS-REP roasting awareness. Not a full AD engine.

## Finding model

No new fields. Domain name, roastable account, and "anonymous bind
succeeded" all fit in existing `kind` + `detail` (same free-text
pattern nmap already uses for script output). Hashes from
GetNPUsers/GetUserSPNs are matched then discarded — not stored.

## Mapped against the six spec sections

1. **Finding model** — no schema change. False-positive discipline:
   Blue/Legacy negative-control tests written first
   (`test_blue_real_ports_do_not_trigger_ad_detection`,
   `test_legacy_real_ports_do_not_trigger_ad_detection`) using real
   port facts from 0xdf / justus.pw. Detector requires (a) a
   namingContext DNS name extracted from script text, OR (b) LDAP/GC
   (389/636/3268/3269) PLUS Kerberos/DNS/kpasswd (53/88/464). SMB+RPC
   alone never fires.
2. **parsers/ad_recon.py** — `detect_ad_signals()`, ldapsearch LDIF,
   GetNPUsers.py, GetUserSPNs.py, plus a one-file dispatcher.
   Formats verified against: OpenLDAP ldapsearch(1) LDIF; nmap
   ldap-rootdse NSE sample output; fortra/impacket
   examples/GetNPUsers.py and GetUserSPNs.py (`$krb5asrep$` /
   `$krb5tgs$`); swisskyrepo Internal All The Things; HTB Forest
   writeup https://joenibe.github.io/htb/forest/ (ports + htb.local).
3. **Suggestion rules (3)** — AD signature → `ldapsearch -x -H
   ldap://$TARGET -s base namingcontexts`; port 88 + known realm →
   `GetNPUsers.py <realm>/ -usersfile users.txt -no-pass -dc-ip
   $TARGET`; ldap_anon → user dump with `(objectClass=user)
   sAMAccountName`. Kerberoasting is parsed but has no suggestion
   rule this pass.
4. **ELI5** — 5 entries in `explain_seed/ad_seed.py`, wired into
   `_MODULES`.
5. **KB** — 2 entries (anonymous LDAP, AS-REP roasting) in
   `kb/ad_seed.py`. Third candidate (SMB signing / relay) was
   drafted then **removed after live Forest parse**: FTS matched
   nmap's DNS service name `domain` on port 53. Parked in
   `AD_ENGINE_OPEN_QUESTIONS.md` until a signing-disabled finding
   exists. Seeded from `_seed_brain` (same path as `kb/seed.py`,
   Hole B) and from `trinity init`.
6. **CLI** — `detect_ad_signals()` hooked into existing `parse-nmap`
   via `process.detect_and_parse` (watch-mode included). One new
   command `trinity parse-ad` dispatches ldapsearch / GetNPUsers /
   GetUserSPNs by content shape.

## Live verification (isolated `$HOME=/tmp/trinity_ad_live_forest2`)

HTB Forest fixture (`test/fixtures/ad_forest.xml`), cited
https://joenibe.github.io/htb/forest/:

```
10.10.10.161:53 domain
  No local match — this would be a candidate for AI escalation.

trinity next --box Forest
  Recommended next
  GetNPUsers.py htb.local/ -usersfile users.txt -no-pass -dc-ip $TARGET
  Also worth trying
  ldapsearch -x -H ldap://$TARGET -s base namingcontexts  (tool not installed)
```

Blue fixture (`test/fixtures/ad_blue.xml`), cited
https://0xdf.gitlab.io/2021/05/11/htb-blue.html — suggested
`enum4linux-ng` only. No ldapsearch, no GetNPUsers, no
`ad_domain_controller` finding.

## Tests

Before this branch (main `bd81f92`): 345 unit tests in tree.
After: **364 passed** (`uv` not on PATH; ran
`PYTHONPATH=src .venv/bin/python -m pytest -q`). 19 new tests in
`test/unit/test_ad_engine.py`.

## Open questions

See `docs/AD_ENGINE_OPEN_QUESTIONS.md` (BloodHound, Kerberoast
suggestion rule, watch-mode for parse-ad, tools.py for ldapsearch,
computer/group ldapsearch objects, SMB-signing detector+KB).

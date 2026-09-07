# AD engine prototype — open questions

Ideas that showed up while building the first slice. None of these
were implemented. Doc reviews.

## Explicitly parked (spec said not this pass)

- **BloodHound JSON parsing / attack-path visualization.** Graph-shaped,
  bigger than this prototype. Needs its own design pass.
- **Kerberoasting as a suggestion rule.** The parser recognizes
  `GetUserSPNs.py` output (`kind=kerberoastable_account`) so a later
  rule has something to hang on, but this pass's 3 suggestion rules
  stop at anonymous LDAP + AS-REP roasting (no-cred starting points).
- **Watch-mode auto-detect of ldapsearch/GetNPUsers/GetUserSPNs files.**
  Only `trinity parse-ad` ingests those formats. `detect_and_parse()`
  was left alone so a random `.txt` notes file containing the word
  `namingContexts` cannot get misidentified. Could be added later with
  the same conservative sniffing as rustscan.

## Should this also… (not built)

- A Finding `extra: dict` field for structured facts like
  `{"domain": "htb.local"}`. Existing `detail` (`domain: htb.local`) is
  enough for the prototype; a structured field would make coach/report
  consumers cleaner later.
- Register `ldapsearch` / `impacket-GetNPUsers` in `tools.py`. Not
  done — spec forbade extra config. Unregistered tools still get a
  PATH check; GetNPUsers.py's binary name varies (`GetNPUsers.py` vs
  `impacket-GetNPUsers`), so `required_tool` is left empty on that
  rule to avoid a false "not installed" warning.
- Computer accounts (`FOREST$`) and groups from ldapsearch. Parser
  currently emits users (sAMAccountName not ending in `$`) plus one
  `ldap_anon` finding when namingContexts are readable. Computers/
  groups would match enum4linux-ng more closely.
- SMB-signing-disabled *detection* from nmap `smb2-security-mode`
  script output, and a KB entry for it. Drafted then **removed from
  seed**: match_service=None plus the word "domain" FTS-matched nmap's
  DNS service (`service=domain` on port 53) during the Forest live
  run. Do not re-seed until a parser synthesizes a signing-disabled
  finding; then the KB can match that kind instead of free text.

- `netexec ldap $TARGET -u '' -p '' --users` as the post-anon-bind
  suggestion instead of ldapsearch. Real operators often reach for
  netexec first; this pass kept ldapsearch so the first two AD steps
  stay in one tool family and don't require a new tools.py entry.

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

## Explain cache still misses real AD commands (found 2026-09-07, Doc review) — FIXED

**Status: fixed in `explain.py` + `explain_seed/ad_seed.py`** (see
`test_real_getnpusers_command_hits_ad_seed_entry` and
`test_real_ldapsearch_dn_command_hits_ad_seed_entry` in
`test/unit/test_explain.py`). Alexander's call (2026-09-07): high
priority, "plan and implement the fix that best aligns with our
project and its goals and use cases."

The systemic `<target>`-vs-real-substitution bug affecting the WHOLE
explain-seed library (not AD-specific) was fixed in `explain.py` --
see the "explain: match real target substitutions against templated
seed keys" commit on main. That fix handled target-host substitution
only (IPv4 literal or `$TARGET`).

It did NOT fix AD's `GetNPUsers.py`/`ldapsearch` seed entries, which
have additional real-vs-template mismatches beyond the target:
`<domain>` vs a real realm (`htb.local`), `<userlist>` vs a real
filename (`users.txt`), and the real suggested command includes a
`-dc-ip <target>` flag the seed key didn't have at all. Confirmed
live: `trinity explain "GetNPUsers.py htb.local/ -usersfile users.txt
-no-pass -dc-ip 10.10.10.161"` still fell through to the AI-escalation
prompt even after the general fix.

**Chosen approach: (a), not (b).** Of the two options logged below,
went with making the seed keys and `_templated()` match the EXACT
real command shape `suggest_for_port` emits (option a), not a general
per-placeholder templating scheme (option b). Reasoning: option (b)
was explicitly flagged as riskier in the original note ("domain/
userlist names are genuinely per-operator, per earlier design note
against guess-normalizing them") -- a general scheme would need to
guess which arbitrary token is a "placeholder" across the whole
86-entry seed library, with real risk of silently mis-normalizing an
unrelated command. Option (a) is a small, explicit, auditable
addition: two new prefix-gated regexes in `explain.py`
(`_GETNPUSERS_DOMAIN_RE`, `_USERSFILE_RE`, `_LDAP_BASE_RE`), each
anchored to a specific flag/command shape (`GetNPUsers.py <x>/`,
`-usersfile <x>`, `ldapsearch ... -b '<x>'`), gated behind a command-
prefix check (`startswith("GetNPUsers.py ")` / `startswith("ldapsearch ")`)
so it can never touch an unrelated command. This only affects the
explain-cache LOOKUP KEY (matching a real command to a cached
explanation) -- it does NOT touch `suggest/engine.py`'s actual
suggestion output, so the "don't guess-normalize per-operator names in
what's shown to the user" principle from the original design note is
untouched. Also updated the two AD seed entries themselves
(`explain_seed/ad_seed.py`) to the exact real command shapes (added
`-dc-ip <target>` to the GetNPUsers entry; added a new entry for the
ldapsearch `-b` follow-up, which had no seed entry at all before).

Verified live via the real `trinity` CLI against a throwaway `HOME`:
both real commands (`GetNPUsers.py htb.local/ -usersfile users.txt
-no-pass -dc-ip 10.10.10.161` and `ldapsearch -x -H ldap://10.10.10.161
-b 'DC=htb,DC=local' '(objectClass=user)' sAMAccountName`) now return
"From local cache" instead of falling through to AI-escalation.

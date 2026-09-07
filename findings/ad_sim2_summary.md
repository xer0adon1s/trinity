# AD Simulation — Round 2 Findings

Ran against the AD engine branch (`feat/ad-enumeration-prototype`) as
of Doc's review pass (KB entries rephrased, synthetic-finding display
fixed, systemic explain cache-key fixed, LDAP domain-suffix stripped).
Corpus dispatched to Claude Code CLI; ran to 19 boxes before hitting
its turn budget and exiting before writing this summary itself — Doc
picked the transcripts back up, verified them directly, found and
fixed one real bug, and wrote this summary from the real evidence.

## Corpus (19 boxes, real writeups, retired/public only)

Absolute, APT, AttacktiveDirectory, Blackfield, Blue (negative
control), Cascade, Certified, Escape, Fuse, Legacy (negative control),
Manager, Mantis, Multimaster, Netmon (negative control), RazorBlack,
Sauna, Scrambled, Sizzle, VulnNetRoasted.

10 of these have real ldapsearch/GetNPUsers/GetUserSPNs-shaped
fixtures beyond just the nmap XML, exercising the full `parse-ad` ->
`next` follow-up cycle, not just detection off nmap alone.

## Verdict: PASS, 1 real bug found and fixed

- **Negative controls held perfectly.** Blue, Legacy, Netmon — zero
  AD-detection false positives, zero LDAP/GetNPUsers/vsftpd
  cross-matches, verified directly against every transcript. All 3
  KB-overclaiming/cross-service risks this project has hit before
  (twice, earlier tonight) did NOT recur here.
- **Every real DC box correctly detected**, synthetic
  "──── Active Directory domain controller detected — domain: X ────"
  header rendering cleanly (Doc's earlier display-bug fix confirmed
  live across all 19 boxes, zero `:None ?` garbage anywhere).
- **Both rephrased KB entries fire correctly and read as intended**:
  "Kerberos open — worth checking for AS-REP roastable accounts"
  (MEDIUM) and "LDAP open on a domain controller — worth checking for
  anonymous bind" (MEDIUM) — "worth checking" framing, not
  overclaiming, confirmed in real output across the corpus.
- **Real bug found: Mantis's genuine "no roastable accounts" GetNPUsers
  output was silently unrecognized.** Impacket prints only
  `[-] User X doesn't have UF_DONT_REQUIRE_PREAUTH set` per checked
  user when nothing is roastable — zero `$krb5asrep$`/`Getting TGT for`
  markers exist in that case, so the dispatcher's marker-sniffing
  discarded the file as unrecognized instead of acknowledging a
  completed, negative check. This is a common, not edge-case, outcome
  per the KB entry's own honest framing ("most domains have zero such
  accounts"). Fixed: `parse_getnpusers()` now recognizes Impacket's own
  negative phrasing and returns a `kind="asrep_check_negative"`
  Finding; dispatcher updated to route on the same marker. Regression
  tests added (`test_getnpusers_negative_result_still_produces_a_finding`,
  `test_dispatcher_recognizes_getnpusers_negative_result`), real Mantis
  fixture preserved as `test/fixtures/ad_getnpusers_negative.txt`.
  372/372 passing.
- **Zero crashes, zero non-zero exit codes**, anywhere across all 139
  transcript files in the corpus.

## STOP AND ASK — nothing escalated this round

No priority/ordering changes, no new KB content authored beyond the
mechanical negative-result recognition above, no scope creep. The one
fix made was a pure "recognize a real-world output shape that was
being silently dropped" bug, same class as prior sessions' mechanical
fixes — not a judgment call on severity, wording, or match logic.

## What's NOT yet covered (for a future round, not blocking)

- GetUserSPNs.py's own negative-result phrasing was not checked this
  round — worth a quick follow-up to confirm/deny the same gap exists
  there (Impacket's kerberoasting tool likely has an analogous "no
  accounts have an SPN" negative case).
- No boxes in this round tested BloodHound-adjacent scenarios
  (explicitly out of scope per `AD_ENGINE_PROTOTYPE_PROJECT.md`'s
  guardrails, not a gap — just noting it's still untested by design).

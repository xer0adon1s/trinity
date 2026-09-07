"""AD/domain recon parsers — prototype slice.

Trinity never launches ldapsearch, Impacket, BloodHound, or netexec.
This module only reads output the operator produced themselves.

Scope (docs/AD_ENGINE_PROTOTYPE_PROJECT.md): DC-signature detection
from already-parsed nmap findings, plus ldapsearch / GetNPUsers.py /
GetUserSPNs.py text. BloodHound JSON is parked in
docs/AD_ENGINE_OPEN_QUESTIONS.md.

Finding-model choice: no new fields. Domain name, account name, and
"anonymous bind succeeded" all fit in existing `kind` + `detail`
(same free-text pattern the nmap parser already uses for script
output). Hashes from GetNPUsers/GetUserSPNs are recognized so we can
name the roastable account, then discarded — not stored, not looted.
"""
from __future__ import annotations

import re
from pathlib import Path

from trinity.parsers.nmap import Finding

# LDAP / Global Catalog — the ports that distinguish a DC from a lone
# Windows box that merely has SMB+RPC (HTB Blue/Legacy).
_LDAP_PORTS = frozenset({389, 636, 3268, 3269})
# Kerberos / DNS / kpasswd — supporting AD-specific ports. 135/139/445
# are deliberately absent: every Windows box has those.
_AD_SUPPORTING_PORTS = frozenset({53, 88, 464})

# ldap-rootdse / ldapsearch: "defaultNamingContext: DC=htb,DC=local"
# or "namingContexts: DC=htb,DC=local". Skip CN=Configuration / Schema
# and the DnsZones partitions — those are not the domain DNS name.
_NAMING_CONTEXT_RE = re.compile(
    r"(?:defaultNamingContext|namingContexts)\s*:\s*(\S+)",
    re.IGNORECASE,
)
_SKIP_DN_PREFIXES = ("CN=", "DC=DomainDnsZones", "DC=ForestDnsZones")

# nmap LDAP/SMB banners: "Domain: EGOTISTICAL-BANK.LOCAL0., Site: ..."
# The trailing `0.` is a NetBIOS-name null pad nmap prints in -sV
# extrainfo (real DNS name is EGOTISTICAL-BANK.LOCAL). 0xdf's Sauna
# and Blackfield scans show this verbatim.
_NMAP_DOMAIN_BANNER_RE = re.compile(
    r"\bDomain:\s*([A-Za-z0-9._-]+)",
    re.IGNORECASE,
)
_NETBIOS_PADDED_DNS = re.compile(
    r"^(.+)\.(local|htb|lan|corp|internal|com|net|org)0$",
    re.IGNORECASE,
)
_NOT_A_DOMAIN = frozenset({"WORKGROUP", "LOCALHOST", "WORKGROUP0"})

# Impacket GetNPUsers.py hashcat format (verified against fortra/impacket
# examples/GetNPUsers.py): $krb5asrep$23$user@DOMAIN:...
# John format omits the etype integer: $krb5asrep$user@DOMAIN:...
_ASREP_RE = re.compile(
    r"\$krb5asrep\$(?:\d+\$)?([^@$\s]+)@([^:\s$]+)",
    re.IGNORECASE,
)
_GETTGT_RE = re.compile(r"\[\*] Getting TGT for (\S+)", re.IGNORECASE)

# Impacket GetUserSPNs.py hashcat format (verified against
# fortra/impacket examples/GetUserSPNs.py outputTGS):
# $krb5tgs$23$*username$REALM$spn*$checksum$data
_TGS_RE = re.compile(
    r"\$krb5tgs\$\d+\$\*([^$*]+)",
    re.IGNORECASE,
)
_SAM_RE = re.compile(r"^sAMAccountName:\s*(\S+)\s*$", re.IGNORECASE | re.MULTILINE)


def _dn_to_dns(dn: str) -> str | None:
    """DC=htb,DC=local → htb.local. Returns None for Configuration /
    Schema / DnsZones partitions and for anything without a DC= RDN."""
    stripped = dn.strip().rstrip(",")
    upper = stripped.upper()
    if any(upper.startswith(p.upper()) for p in _SKIP_DN_PREFIXES):
        return None
    parts: list[str] = []
    for piece in stripped.split(","):
        piece = piece.strip()
        if piece.upper().startswith("DC="):
            parts.append(piece[3:])
        else:
            return None
    if not parts:
        return None
    return ".".join(parts)


def _sanitize_dns_name(name: str) -> str | None:
    """Strip nmap NetBIOS padding (`LOCAL0.` → `LOCAL`) and reject
    workgroup labels. Used for both namingContext DNs and `Domain:`
    banners."""
    cleaned = name.strip().strip(".")
    if not cleaned:
        return None
    if cleaned.upper() in _NOT_A_DOMAIN:
        return None
    padded = _NETBIOS_PADDED_DNS.match(cleaned)
    if padded:
        return f"{padded.group(1)}.{padded.group(2)}"
    return cleaned


def extract_domain_from_text(text: str) -> str | None:
    """Pull a DNS domain out of ldap-rootdse / ldapsearch naming-context
    lines, or from nmap's LDAP `Domain:` banner. Prefer a namingContext
    DN (authoritative); fall back to the banner and strip NetBIOS `0`
    padding so GetNPUsers.py gets a real realm."""
    found: list[str] = []
    for match in _NAMING_CONTEXT_RE.finditer(text):
        dns = _sanitize_dns_name(_dn_to_dns(match.group(1)) or "")
        if dns and dns not in found:
            found.append(dns)
    if found:
        return found[0]
    for match in _NMAP_DOMAIN_BANNER_RE.finditer(text):
        dns = _sanitize_dns_name(match.group(1))
        if dns:
            return dns
    return None


def detect_ad_signals(findings: list[Finding]) -> Finding | None:
    """Return one synthetic Finding if the already-parsed nmap findings
    look like a domain controller, else None.

    Positive only when:
      (a) a domain DNS name was extracted from script/detail text
          (ldap-rootdse namingContexts / defaultNamingContext), OR
      (b) LDAP or Global Catalog is open (389/636/3268/3269) AND at
          least one of DNS/Kerberos/kpasswd (53/88/464) is also open.

    SMB+RPC+NetBIOS alone (Blue, Legacy) must not fire — those ports
    are on every Windows box, DC or not. A workgroup name in
    smb-os-discovery is not a domain name and is ignored.
    """
    ports = {f.port for f in findings if f.kind == "port" and f.port}
    host = next((f.host for f in findings if f.host), None)
    blob = "\n".join(f.detail or "" for f in findings)
    domain = extract_domain_from_text(blob)

    has_ldap = bool(ports & _LDAP_PORTS)
    has_support = bool(ports & _AD_SUPPORTING_PORTS)
    if not domain and not (has_ldap and has_support):
        return None

    if domain:
        detail = f"domain: {domain}"
    else:
        detail = (
            "AD port cluster (LDAP/GC + Kerberos/DNS); "
            "domain name not extracted from script output"
        )
    return Finding(
        source_tool="nmap",
        kind="ad_domain_controller",
        host=host,
        detail=detail,
        raw_ref="detect_ad_signals",
    )


def parse_ldapsearch(text: str, raw_ref: str | Path | None = None) -> list[Finding]:
    """Parse ldapsearch LDIF (anonymous RootDSE namingContexts and/or a
    user dump). Verified format: OpenLDAP ldapsearch writes
    `namingContexts: DC=...` and `sAMAccountName: user` as LDIF
    attribute lines (man ldapsearch(1); HTB Forest writeups).

    A readable namingContexts value is treated as anonymous bind
    succeeding — if the bind had been rejected, ldapsearch prints
    `result: 1 Operations error` / `Insufficient access` and no
    namingContexts lines (HackIndex LDAP null-bind notes).
    """
    ref = str(raw_ref) if raw_ref else None
    findings: list[Finding] = []
    domain = extract_domain_from_text(text)
    if domain:
        findings.append(
            Finding(
                source_tool="ldapsearch",
                kind="ldap_anon",
                detail=f"anonymous LDAP bind succeeded; domain: {domain}",
                raw_ref=ref,
            )
        )

    seen_users: set[str] = set()
    for match in _SAM_RE.finditer(text):
        name = match.group(1)
        if name.endswith("$") or name in seen_users:
            continue
        seen_users.add(name)
        findings.append(
            Finding(
                source_tool="ldapsearch",
                kind="user",
                detail=f"user: {name}",
                raw_ref=ref,
            )
        )
    return findings


def parse_getnpusers(text: str, raw_ref: str | Path | None = None) -> list[Finding]:
    """Parse Impacket GetNPUsers.py stdout. Records the roastable
    account name only — the $krb5asrep$ blob is matched then dropped,
    same 'don't pile up secrets' instinct as not auto-looting hashes.
    """
    ref = str(raw_ref) if raw_ref else None
    accounts: list[str] = []
    for match in _ASREP_RE.finditer(text):
        acct = match.group(1)
        if acct not in accounts:
            accounts.append(acct)
    for match in _GETTGT_RE.finditer(text):
        acct = match.group(1)
        if acct not in accounts:
            accounts.append(acct)

    return [
        Finding(
            source_tool="GetNPUsers.py",
            kind="asrep_hash",
            detail=f"account: {acct}",
            raw_ref=ref,
        )
        for acct in accounts
    ]


def parse_getuserspns(text: str, raw_ref: str | Path | None = None) -> list[Finding]:
    """Parse Impacket GetUserSPNs.py stdout. Account name only; TGS
    hash is not stored."""
    ref = str(raw_ref) if raw_ref else None
    accounts: list[str] = []
    for match in _TGS_RE.finditer(text):
        acct = match.group(1)
        if acct not in accounts:
            accounts.append(acct)
    return [
        Finding(
            source_tool="GetUserSPNs.py",
            kind="kerberoastable_account",
            detail=f"account: {acct}",
            raw_ref=ref,
        )
        for acct in accounts
    ]


def parse_ad_recon_file(path: str | Path) -> list[Finding]:
    """Dispatcher: sniff ldapsearch LDIF vs GetNPUsers vs GetUserSPNs
    by distinctive markers, same idea as parsers/autorecon.py walking
    by filename/shape. Returns [] if nothing is recognized — never
    raises on unknown text."""
    path = Path(path)
    try:
        text = path.read_text(errors="ignore")
    except OSError:
        return []

    if "$krb5asrep$" in text or "Getting TGT for" in text:
        return parse_getnpusers(text, path)
    if "$krb5tgs$" in text or "ServicePrincipalName" in text:
        return parse_getuserspns(text, path)
    if (
        "namingContexts:" in text
        or "defaultNamingContext:" in text
        or "sAMAccountName:" in text
        or "# extended LDIF" in text
    ):
        return parse_ldapsearch(text, path)
    return []

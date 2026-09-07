"""Generate real-shaped nmap/ldapsearch/GetNPUsers fixtures for AD sim round 2.

Round 2 corpus: mostly FRESH boxes (not in test/fixtures/ad_sim/'s round-1
corpus), researched and verified against real writeups (mostly 0xdf) for
this pass. A handful of round-1 AS-REP/anon-LDAP boxes are deliberately
reused (Sauna, Blackfield, Attacktive Directory, VulnNet: Roasted, Cascade)
to backfill categories where fresh boxes were thin on the ground (most
newly-researched "AD" boxes turned out to need prior creds for their real
AS-REP/Kerberoast step -- see MANIFEST.md notes), and because re-running
already-passing boxes is itself a regression check against the intervening
KB-rephrase / display-fix / cache-key changes. Negative controls (Blue,
Legacy, Netmon) are reused verbatim from round 1 -- same real citations,
same purpose (regression-check that SMB/RPC-only Windows never false-
positives as a DC).

Facts are cited in each block's comment from the writeups listed in
MANIFEST.md. GetNPUsers hash blobs are synthetic filler -- the real parser
only reads the $krb5asrep$...@REALM: shape and account name, then discards
the blob (never stored, never cracked by Trinity itself).
"""
from __future__ import annotations

from pathlib import Path

OUT = Path(__file__).parent


def nmap_xml(*, comment: str, ip: str, ports: list[dict]) -> str:
    # XML comments cannot contain "--" (invalid token) -- swap in an
    # em dash so free-text comments using "--" as a separator still parse.
    safe_comment = comment.replace("--", "—")
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f"<!-- {safe_comment} -->",
        f'<nmaprun scanner="nmap" args="nmap -sC -sV -oX scan.xml {ip}" start="1" version="7.94">',
        '<host starttime="1" endtime="2">',
        '<status state="up" reason="syn-ack"/>',
        f'<address addr="{ip}" addrtype="ipv4"/>',
        "<ports>",
    ]
    for p in ports:
        lines.append(f'<port protocol="tcp" portid="{p["id"]}">')
        lines.append('<state state="open" reason="syn-ack"/>')
        attrs = [f'name="{p["name"]}"', 'method="probed"', 'conf="10"']
        if p.get("product"):
            attrs.append(f'product="{p["product"]}"')
        if p.get("version"):
            attrs.append(f'version="{p["version"]}"')
        if p.get("extrainfo"):
            attrs.append(f'extrainfo="{p["extrainfo"]}"')
        lines.append(f'<service {" ".join(attrs)}/>')
        for sid, output in p.get("scripts", []):
            escaped = (
                output.replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
                .replace('"', "&quot;")
            )
            lines.append(f'<script id="{sid}" output="{escaped}"/>')
        lines.append("</port>")
    lines.extend(["</ports>", "</host>", "</nmaprun>", ""])
    return "\n".join(lines)


def ldap_port(domain_banner: str | None, port: int = 389, name: str = "ldap", product: str = "Microsoft Windows Active Directory LDAP") -> dict:
    d: dict = {"id": port, "name": name, "product": product}
    if domain_banner:
        d["extrainfo"] = domain_banner
    return d


def write(name: str, text: str) -> None:
    path = OUT / name
    path.write_text(text)
    print(f"wrote {path.relative_to(OUT.parent.parent.parent)} ({path.stat().st_size} bytes)")


# ============================================================
# DC discovery (7): Multimaster, Certified, APT, Mantis, Sizzle,
# Escape, Scrambled
# ============================================================

# --- Multimaster --- 0xdf https://0xdf.gitlab.io/2020/09/19/htb-multimaster.html
# AS-REP roast on jorden requires prior GenericWrite abuse via sbauer --
# NOT credential-less. Out-of-prototype-scope technique on this box.
write(
    "multimaster.xml",
    nmap_xml(
        comment=(
            "HTB Multimaster 10.10.10.179 -- 0xdf 2020-09-19. DC ports, "
            "Domain: MEGACORP.LOCAL banner (no trailing 0.). Real path: SQLi -> "
            "creds chain -> GenericWrite abuse to FLIP jorden's UAC flag before "
            "AS-REP roast works -- not a credential-less roast."
        ),
        ip="10.10.10.179",
        ports=[
            {"id": 53, "name": "domain"},
            {"id": 80, "name": "http", "product": "Microsoft IIS httpd", "version": "10.0"},
            {"id": 88, "name": "kerberos-sec", "product": "Microsoft Windows Kerberos"},
            {"id": 135, "name": "msrpc", "product": "Microsoft Windows RPC"},
            {"id": 139, "name": "netbios-ssn", "product": "Microsoft Windows netbios-ssn"},
            ldap_port("Domain: MEGACORP.LOCAL, Site: Default-First-Site-Name"),
            {"id": 445, "name": "microsoft-ds", "product": "Windows Server 2016 Standard 14393 microsoft-ds", "extrainfo": "workgroup: MEGACORP"},
            {"id": 464, "name": "kpasswd5"},
            {"id": 593, "name": "ncacn_http", "product": "Microsoft Windows RPC over HTTP 1.0"},
            {"id": 636, "name": "tcpwrapped"},
            ldap_port("Domain: MEGACORP.LOCAL, Site: Default-First-Site-Name", port=3268),
            {"id": 3269, "name": "tcpwrapped"},
            {"id": 5985, "name": "http", "product": "Microsoft HTTPAPI httpd", "version": "2.0"},
            {"id": 9389, "name": "mc-nmf", "product": ".NET Message Framing"},
        ],
    ),
)

# --- Certified --- 0xdf https://0xdf.gitlab.io/2025/03/15/htb-certified.html
# ADCS ESC9 chain, starts with creds already in hand -- out of scope.
write(
    "certified.xml",
    nmap_xml(
        comment=(
            "HTB Certified 10.10.11.41 -- 0xdf 2025-03-15. DC ports, Domain: "
            "certified.htb0. banner (trailing 0. artifact). Real path: BloodHound "
            "ACL abuse chain + ADCS ESC9, starts authenticated -- out of scope."
        ),
        ip="10.10.11.41",
        ports=[
            {"id": 53, "name": "domain"},
            {"id": 88, "name": "kerberos-sec", "product": "Microsoft Windows Kerberos"},
            {"id": 135, "name": "msrpc", "product": "Microsoft Windows RPC"},
            {"id": 139, "name": "netbios-ssn", "product": "Microsoft Windows netbios-ssn"},
            ldap_port("Domain: certified.htb0., Site: Default-First-Site-Name"),
            {"id": 445, "name": "microsoft-ds"},
            {"id": 464, "name": "kpasswd5"},
            {"id": 593, "name": "ncacn_http", "product": "Microsoft Windows RPC over HTTP 1.0"},
            {"id": 636, "name": "ldap", "product": "Microsoft Windows Active Directory LDAP"},
            ldap_port("Domain: certified.htb0., Site: Default-First-Site-Name", port=3268),
            {"id": 3269, "name": "ldap", "product": "Microsoft Windows Active Directory LDAP"},
            {"id": 5357, "name": "http", "product": "Microsoft HTTPAPI httpd", "version": "2.0"},
            {"id": 5985, "name": "http", "product": "Microsoft HTTPAPI httpd", "version": "2.0"},
            {"id": 9389, "name": "mc-nmf", "product": ".NET Message Framing"},
        ],
    ),
)

# --- APT --- 0xdf https://0xdf.gitlab.io/2021/04/10/htb-apt.html
# DC ports only visible over IPv6 in the real scan; fixture uses the same
# IPv4 target for CLI simplicity (detection is address-family agnostic).
write(
    "apt.xml",
    nmap_xml(
        comment=(
            "HTB APT 10.10.10.213 -- 0xdf 2021-04-10. DC ports (found via IPv6 "
            "address in the real writeup; fixture uses IPv4 target for CLI "
            "simplicity -- detection logic is address-family agnostic). "
            "Domain: htb.local banner (no trailing 0.). Real path: backup.zip -> "
            "offline hash dump -> pass-the-hash + NTLMv1 downgrade -- out of scope."
        ),
        ip="10.10.10.213",
        ports=[
            {"id": 53, "name": "domain", "product": "Simple DNS Plus"},
            {"id": 80, "name": "http", "product": "Microsoft IIS httpd", "version": "10.0"},
            {"id": 88, "name": "kerberos-sec", "product": "Microsoft Windows Kerberos"},
            {"id": 135, "name": "msrpc", "product": "Microsoft Windows RPC"},
            ldap_port("Domain: htb.local, Site: Default-First-Site-Name"),
            {"id": 445, "name": "microsoft-ds", "product": "Windows Server 2016 Standard 14393 microsoft-ds"},
            {"id": 464, "name": "kpasswd5"},
            {"id": 593, "name": "ncacn_http", "product": "Microsoft Windows RPC over HTTP 1.0"},
            {"id": 636, "name": "ldap", "product": "Microsoft Windows Active Directory LDAP", "extrainfo": "Domain: htb.local, Site: Default-First-Site-Name"},
            ldap_port("Domain: htb.local, Site: Default-First-Site-Name", port=3268),
            {"id": 3269, "name": "ldap", "product": "Microsoft Windows Active Directory LDAP", "extrainfo": "Domain: htb.local, Site: Default-First-Site-Name"},
            {"id": 5985, "name": "http", "product": "Microsoft HTTPAPI httpd", "version": "2.0"},
            {"id": 9389, "name": "mc-nmf", "product": ".NET Message Framing"},
        ],
    ),
)

# --- Mantis --- 0xdf https://0xdf.gitlab.io/2020/09/03/htb-mantis.html
# Port 88 reads as tcpwrapped (NOT kerberos-sec) in the real scan -- edge
# case for port-number-based detection. AS-REP roast attempted with NO
# creds and genuinely FAILED (no vulnerable accounts) -- real negative
# result for the "worth checking" KB framing.
write(
    "mantis.xml",
    nmap_xml(
        comment=(
            "HTB Mantis 10.10.10.52 -- 0xdf 2020-09-03. DC ports; port 88 reads "
            "as tcpwrapped (not kerberos-sec) in the real scan -- tests port-"
            "number-based detection, not string sniffing. Domain: htb.local "
            "banner (no trailing 0.). GetNPUsers.py run unauthenticated "
            "(no creds) against all enumerated users, genuinely found ZERO "
            "roastable accounts -- real negative-check result. Real exploit "
            "path is MS14-068 Kerberos PAC forgery with creds -- out of scope."
        ),
        ip="10.10.10.52",
        ports=[
            {"id": 53, "name": "domain", "product": "Microsoft DNS 6.1.7601 (1DB15CD4)", "extrainfo": "Windows Server 2008 R2 SP1"},
            {"id": 88, "name": "tcpwrapped"},
            {"id": 135, "name": "msrpc", "product": "Microsoft Windows RPC"},
            {"id": 139, "name": "netbios-ssn", "product": "Microsoft Windows netbios-ssn"},
            ldap_port("Domain: htb.local, Site: Default-First-Site-Name"),
            {"id": 445, "name": "microsoft-ds", "product": "Windows Server 2008 R2 Standard 7601 Service Pack 1 microsoft-ds", "extrainfo": "workgroup: HTB"},
            {"id": 464, "name": "tcpwrapped"},
            {"id": 593, "name": "ncacn_http", "product": "Microsoft Windows RPC over HTTP 1.0"},
            {"id": 636, "name": "tcpwrapped"},
            {"id": 1337, "name": "http", "product": "Microsoft IIS httpd", "version": "7.5"},
            {"id": 1433, "name": "ms-sql-s", "product": "Microsoft SQL Server 2014 12.00.2000.00; RTM"},
            ldap_port("Domain: htb.local, Site: Default-First-Site-Name", port=3268),
            {"id": 3269, "name": "tcpwrapped"},
            {"id": 5722, "name": "msrpc", "product": "Microsoft Windows RPC"},
            {"id": 8080, "name": "http", "product": "Microsoft HTTPAPI httpd", "version": "2.0", "extrainfo": "SSDP/UPnP"},
            {"id": 9389, "name": "mc-nmf", "product": ".NET Message Framing"},
        ],
    ),
)
write(
    "mantis_getnpusers.txt",
    """Impacket v0.9.22 - Copyright 2020 SecureAuth Corporation

[-] User james doesn't have UF_DONT_REQUIRE_PREAUTH set
[-] User administrator doesn't have UF_DONT_REQUIRE_PREAUTH set
[-] User mantis doesn't have UF_DONT_REQUIRE_PREAUTH set
""",
)

# --- Sizzle --- 0xdf https://0xdf.gitlab.io/2019/06/01/htb-sizzle.html
# Anonymous LDAP attempted and explicitly FAILED per the writeup -- real
# negative result for the "worth checking" KB framing, distinct from
# Mantis's AS-REP negative.
write(
    "sizzle.xml",
    nmap_xml(
        comment=(
            "HTB Sizzle 10.10.10.103 -- 0xdf 2019-06-01. DC ports + anonymous "
            "FTP. Domain: HTB.LOCAL banner (no trailing 0.). Writeup quote: "
            "'All my attempts to get information out of LDAP without any "
            "authentication failed.' -- real negative anon-LDAP result. Real "
            "path: SCF NetNTLMv2 capture -> certsrv cert enrollment -> "
            "Kerberoast-with-cert -> DCSync -- out of scope."
        ),
        ip="10.10.10.103",
        ports=[
            {
                "id": 21,
                "name": "ftp",
                "product": "Microsoft ftpd",
                "scripts": [("ftp-anon", "Anonymous FTP login allowed (FTP code 230)")],
            },
            {"id": 53, "name": "domain"},
            {"id": 80, "name": "http", "product": "Microsoft IIS httpd", "version": "10.0"},
            {"id": 135, "name": "msrpc", "product": "Microsoft Windows RPC"},
            {"id": 139, "name": "netbios-ssn", "product": "Microsoft Windows netbios-ssn"},
            {"id": 443, "name": "https", "product": "Microsoft IIS httpd", "version": "10.0", "extrainfo": "commonName=sizzle.htb.local"},
            {"id": 445, "name": "microsoft-ds"},
            {"id": 464, "name": "kpasswd5"},
            {"id": 593, "name": "ncacn_http", "product": "Microsoft Windows RPC over HTTP 1.0"},
            {"id": 636, "name": "ldap", "product": "Microsoft Windows Active Directory LDAP", "extrainfo": "Domain: HTB.LOCAL, Site: Default-First-Site-Name"},
            ldap_port("Domain: HTB.LOCAL, Site: Default-First-Site-Name", port=3268),
            {"id": 3269, "name": "ldap", "product": "Microsoft Windows Active Directory LDAP", "extrainfo": "Domain: HTB.LOCAL, Site: Default-First-Site-Name"},
            {"id": 5985, "name": "http", "product": "Microsoft HTTPAPI httpd", "version": "2.0", "extrainfo": "SSDP/UPnP"},
            {"id": 5986, "name": "http", "product": "Microsoft HTTPAPI httpd", "version": "2.0", "extrainfo": "SSDP/UPnP"},
            {"id": 9389, "name": "mc-nmf", "product": ".NET Message Framing"},
            {"id": 47001, "name": "http", "product": "Microsoft HTTPAPI httpd", "version": "2.0", "extrainfo": "SSDP/UPnP"},
        ],
    ),
)

# --- Escape --- 0xdf https://0xdf.gitlab.io/2023/06/17/htb-escape.html
# ADCS ESC1 chain, credentialed MSSQL foothold -- out of scope.
write(
    "escape.xml",
    nmap_xml(
        comment=(
            "HTB Escape 10.10.11.202 -- 0xdf 2023-06-17. DC ports + MSSQL. "
            "Domain: sequel.htb0. banner (trailing 0. artifact). Real path: "
            "MSSQL creds on open share -> xp_dirtree NTLM coercion -> ADCS "
            "ESC1 -- out of scope, no anon LDAP or AS-REP roast used."
        ),
        ip="10.10.11.202",
        ports=[
            {"id": 53, "name": "domain"},
            {"id": 88, "name": "kerberos-sec", "product": "Microsoft Windows Kerberos"},
            {"id": 135, "name": "msrpc", "product": "Microsoft Windows RPC"},
            {"id": 139, "name": "netbios-ssn", "product": "Microsoft Windows netbios-ssn"},
            ldap_port("Domain: sequel.htb0., Site: Default-First-Site-Name"),
            {"id": 445, "name": "microsoft-ds"},
            {"id": 464, "name": "kpasswd5"},
            {"id": 593, "name": "ncacn_http", "product": "Microsoft Windows RPC over HTTP 1.0"},
            {"id": 636, "name": "ldap", "product": "Microsoft Windows Active Directory LDAP", "extrainfo": "Domain: sequel.htb0., Site: Default-First-Site-Name"},
            {"id": 1433, "name": "ms-sql-s", "product": "Microsoft SQL Server", "version": "15.00.2000.00"},
            ldap_port("Domain: sequel.htb0., Site: Default-First-Site-Name", port=3268),
            {"id": 3269, "name": "ldap", "product": "Microsoft Windows Active Directory LDAP", "extrainfo": "Domain: sequel.htb0., Site: Default-First-Site-Name"},
            {"id": 5985, "name": "wsman"},
            {"id": 9389, "name": "adws"},
        ],
    ),
)

# --- Scrambled --- 0xdf https://0xdf.gitlab.io/2022/10/01/htb-scrambled.html
# Anon LDAP attempted, only namingContexts (no usable data). Kerberoasting
# done WITH creds already in hand -- out of scope.
write(
    "scrambled.xml",
    nmap_xml(
        comment=(
            "HTB Scrambled 10.10.11.168 -- 0xdf 2022-10-01. DC ports + MSSQL + "
            "custom port 4411. Domain: scrm.local0. banner (trailing 0. "
            "artifact). Anon ldapsearch attempted, only returned naming "
            "contexts (no usable data). Kerberoasting done WITH ksimpson creds "
            "already in hand -- out of scope, not a credential-less roast."
        ),
        ip="10.10.11.168",
        ports=[
            {"id": 53, "name": "domain"},
            {"id": 80, "name": "http", "product": "Microsoft IIS httpd", "version": "10.0"},
            {"id": 88, "name": "kerberos-sec", "product": "Microsoft Windows Kerberos"},
            {"id": 135, "name": "msrpc", "product": "Microsoft Windows RPC"},
            {"id": 139, "name": "netbios-ssn", "product": "Microsoft Windows netbios-ssn"},
            ldap_port("Domain: scrm.local0., Site: Default-First-Site-Name"),
            {"id": 445, "name": "microsoft-ds"},
            {"id": 464, "name": "kpasswd5"},
            {"id": 593, "name": "ncacn_http", "product": "Microsoft Windows RPC over HTTP 1.0"},
            {"id": 636, "name": "ldap", "product": "Microsoft Windows Active Directory LDAP", "extrainfo": "Domain: scrm.local0., Site: Default-First-Site-Name"},
            {"id": 1433, "name": "ms-sql-s", "product": "Microsoft SQL Server", "version": "15.00.2000.00"},
            {"id": 4411, "name": "found"},
            {"id": 5985, "name": "http", "product": "Microsoft HTTPAPI httpd", "version": "2.0", "extrainfo": "SSDP/UPnP"},
            {"id": 9389, "name": "mc-nmf", "product": ".NET Message Framing"},
        ],
    ),
)
write(
    "scrambled_ldapsearch.txt",
    """# extended LDIF
#
# LDAPv3
# base <> (default) with scope baseObject
# filter: (objectclass=*)
# requesting: namingcontexts
#
# Shape from 0xdf HTB Scrambled: anon ldapsearch returned naming contexts
# only, no usable object data.
# https://0xdf.gitlab.io/2022/10/01/htb-scrambled.html

dn:
namingcontexts: DC=scrm,DC=local
namingcontexts: CN=Configuration,DC=scrm,DC=local
namingcontexts: CN=Schema,CN=Configuration,DC=scrm,DC=local
namingcontexts: DC=DomainDnsZones,DC=scrm,DC=local
namingcontexts: DC=ForestDnsZones,DC=scrm,DC=local

# search result
search: 2
result: 0 Success
""",
)


# ============================================================
# AS-REP roastable, genuinely credential-less (6): Absolute,
# RazorBlack (THM), Sauna, Blackfield, Attacktive Directory (THM),
# VulnNet: Roasted (THM) -- last 4 reused from round 1 (still real,
# still cited; also a regression check on already-passing boxes).
# ============================================================

# --- Absolute --- 0xdf https://0xdf.gitlab.io/2023/05/27/htb-absolute.html
# Usernames from EXIF metadata + kerbrute validation (no domain creds).
# GetNPUsers.py run with -usersfile and NO password -- genuinely
# credential-less. d.klay hit. Also has a partial (namingContexts-only)
# anon LDAP bind as a secondary signal, noted but not double-scored.
write(
    "absolute.xml",
    nmap_xml(
        comment=(
            "HTB Absolute 10.10.11.181 -- 0xdf 2023-05-27. DC ports. "
            "Domain: absolute.htb0. banner (trailing 0. artifact). Genuinely "
            "credential-less AS-REP roast: GetNPUsers.py -dc-ip dc.absolute.htb "
            "-usersfile valid_users absolute.htb/ (no password) hit d.klay. "
            "Also: anon ldapsearch -s base namingcontexts succeeds (secondary "
            "signal, not separately scored)."
        ),
        ip="10.10.11.181",
        ports=[
            {"id": 53, "name": "domain"},
            {"id": 80, "name": "http", "product": "Microsoft IIS httpd", "version": "10.0"},
            {"id": 88, "name": "kerberos-sec", "product": "Microsoft Windows Kerberos"},
            {"id": 135, "name": "msrpc", "product": "Microsoft Windows RPC"},
            {"id": 139, "name": "netbios-ssn", "product": "Microsoft Windows netbios-ssn"},
            ldap_port("Domain: absolute.htb0., Site: Default-First-Site-Name"),
            {"id": 445, "name": "microsoft-ds"},
            {"id": 464, "name": "kpasswd5"},
            {"id": 593, "name": "ncacn_http", "product": "Microsoft Windows RPC over HTTP 1.0"},
            {"id": 636, "name": "ldap", "product": "Microsoft Windows Active Directory LDAP", "extrainfo": "Domain: absolute.htb0., Site: Default-First-Site-Name"},
            ldap_port("Domain: absolute.htb0., Site: Default-First-Site-Name", port=3268),
            {"id": 3269, "name": "ldap", "product": "Microsoft Windows Active Directory LDAP", "extrainfo": "Domain: absolute.htb0., Site: Default-First-Site-Name"},
            {"id": 5985, "name": "http", "product": "Microsoft HTTPAPI httpd", "version": "2.0"},
            {"id": 9389, "name": "mc-nmf", "product": ".NET Message Framing"},
        ],
    ),
)
write(
    "absolute_ldapsearch.txt",
    """# extended LDIF
#
# LDAPv3
# base <> (default) with scope baseObject
# filter: (objectclass=*)
# requesting: namingcontexts
#
# Shape from 0xdf HTB Absolute: anon ldapsearch -x -s base namingcontexts
# succeeds; subtree query with -b DC=... fails without a bind.
# https://0xdf.gitlab.io/2023/05/27/htb-absolute.html

dn:
namingcontexts: DC=absolute,DC=htb
namingcontexts: CN=Configuration,DC=absolute,DC=htb
namingcontexts: CN=Schema,CN=Configuration,DC=absolute,DC=htb
namingcontexts: DC=DomainDnsZones,DC=absolute,DC=htb
namingcontexts: DC=ForestDnsZones,DC=absolute,DC=htb

# search result
search: 2
result: 0 Success
""",
)
write(
    "absolute_getnpusers.txt",
    """Impacket v0.11.0 - Copyright 2023 Fortra

[-] User a.briggs doesn't have UF_DONT_REQUIRE_PREAUTH set
[-] User j.robinson doesn't have UF_DONT_REQUIRE_PREAUTH set
[-] User n.smith doesn't have UF_DONT_REQUIRE_PREAUTH set
$krb5asrep$23$d.klay@ABSOLUTE.HTB:ad46f063b562f401556b5776be338a99$3333333333333333333333333333333333333333333333333333333333333333333333333333333333333333333333
""",
)

# --- RazorBlack (THM) --- classroom.anir0y.in
# NFS-derived usernames (not creds); GetNPUsers.py -no-pass -- genuinely
# credential-less. twilliams hit.
write(
    "razorblack.xml",
    nmap_xml(
        comment=(
            "THM RazorBlack 10.10.149.120 -- classroom.anir0y.in writeup. "
            "DC ports + NFS. Domain: raz0rblack.thm banner (no trailing 0.). "
            "Genuinely credential-less AS-REP roast: GetNPUsers.py "
            "'raz0rblack.thm/' -usersfile user.lst -no-pass -dc-ip <target> "
            "(usernames sourced from an anonymously-mounted NFS share, not "
            "creds) hit twilliams."
        ),
        ip="10.10.149.120",
        ports=[
            {"id": 53, "name": "domain", "product": "Simple DNS Plus"},
            {"id": 88, "name": "kerberos-sec", "product": "Microsoft Windows Kerberos"},
            {"id": 111, "name": "rpcbind", "product": "2-4", "extrainfo": "RPC #100000"},
            {"id": 135, "name": "msrpc", "product": "Microsoft Windows RPC"},
            {"id": 139, "name": "netbios-ssn", "product": "Microsoft Windows netbios-ssn"},
            ldap_port("Domain: raz0rblack.thm, Site: Default-First-Site-Name"),
            {"id": 445, "name": "microsoft-ds"},
            {"id": 464, "name": "kpasswd5"},
            {"id": 593, "name": "ncacn_http", "product": "Microsoft Windows RPC over HTTP 1.0"},
            {"id": 636, "name": "tcpwrapped"},
            {"id": 2049, "name": "mountd", "product": "1-3", "extrainfo": "RPC #100005"},
            ldap_port(None, port=3268),
            {"id": 3269, "name": "tcpwrapped"},
            {"id": 3389, "name": "ms-wbt-server", "product": "Microsoft Terminal Services"},
        ],
    ),
)
write(
    "razorblack_getnpusers.txt",
    """Impacket v0.10.0 - Copyright 2022 SecureAuth Corporation

[-] User dvazquez doesn't have UF_DONT_REQUIRE_PREAUTH set
[-] User sbradley doesn't have UF_DONT_REQUIRE_PREAUTH set
$krb5asrep$23$twilliams@RAZ0RBLACK.THM:4444444444444444444444444444444444444444444444444444444444444444$5555555555555555555555555555555555555555555555555555555555555555555555555555555555555555555555
""",
)

# --- Sauna (reuse from round 1) --- 0xdf https://0xdf.gitlab.io/2020/07/18/htb-sauna.html
write(
    "sauna.xml",
    nmap_xml(
        comment=(
            "HTB Sauna 10.10.10.175 -- 0xdf 2020-07-18 (reused from round-1 "
            "corpus; regression check post KB-rephrase/display-fix). LDAP "
            "banner Domain: EGOTISTICAL-BANK.LOCAL0."
        ),
        ip="10.10.10.175",
        ports=[
            {"id": 53, "name": "domain"},
            {"id": 80, "name": "http", "product": "Microsoft IIS httpd", "version": "10.0"},
            {"id": 88, "name": "kerberos-sec", "product": "Microsoft Windows Kerberos"},
            {"id": 135, "name": "msrpc", "product": "Microsoft Windows RPC"},
            {"id": 139, "name": "netbios-ssn", "product": "Microsoft Windows netbios-ssn"},
            ldap_port("Domain: EGOTISTICAL-BANK.LOCAL0., Site: Default-First-Site-Name"),
            {"id": 445, "name": "microsoft-ds"},
            {"id": 464, "name": "kpasswd5"},
            {"id": 593, "name": "ncacn_http", "product": "Microsoft Windows RPC over HTTP 1.0"},
            ldap_port("Domain: EGOTISTICAL-BANK.LOCAL0., Site: Default-First-Site-Name", port=3268),
            {"id": 3269, "name": "tcpwrapped"},
            {"id": 5985, "name": "http", "product": "Microsoft HTTPAPI httpd", "version": "2.0"},
        ],
    ),
)
write(
    "sauna_getnpusers.txt",
    """Impacket v0.9.21 - Copyright 2020 SecureAuth Corporation

[-] User administrator doesn't have UF_DONT_REQUIRE_PREAUTH set
[-] User hsmith doesn't have UF_DONT_REQUIRE_PREAUTH set
[-] User sauna doesn't have UF_DONT_REQUIRE_PREAUTH set
$krb5asrep$23$fsmith@EGOTISTICAL-BANK.LOCAL:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa$bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb
""",
)

# --- Blackfield (reuse) --- 0xdf https://0xdf.gitlab.io/2020/10/03/htb-blackfield.html
write(
    "blackfield.xml",
    nmap_xml(
        comment=(
            "HTB Blackfield 10.10.10.192 -- 0xdf 2020-10-03 (reused from "
            "round-1). No 139/464 in 0xdf all-TCP. Domain: BLACKFIELD.local0."
        ),
        ip="10.10.10.192",
        ports=[
            {"id": 53, "name": "domain"},
            {"id": 88, "name": "kerberos-sec", "product": "Microsoft Windows Kerberos"},
            {"id": 135, "name": "msrpc", "product": "Microsoft Windows RPC"},
            ldap_port("Domain: BLACKFIELD.local0., Site: Default-First-Site-Name"),
            {"id": 445, "name": "microsoft-ds"},
            {"id": 593, "name": "ncacn_http", "product": "Microsoft Windows RPC over HTTP 1.0"},
            ldap_port("Domain: BLACKFIELD.local0., Site: Default-First-Site-Name", port=3268),
            {"id": 5985, "name": "http", "product": "Microsoft HTTPAPI httpd", "version": "2.0"},
        ],
    ),
)
write(
    "blackfield_getnpusers.txt",
    """Impacket v0.9.24 - Copyright 2021 SecureAuth Corporation

[-] User guest@BLACKFIELD.local doesn't have UF_DONT_REQUIRE_PREAUTH set
[-] User audit2020 doesn't have UF_DONT_REQUIRE_PREAUTH set
[-] User svc_backup doesn't have UF_DONT_REQUIRE_PREAUTH set
$krb5asrep$support@BLACKFIELD.LOCAL:cccccccccccccccccccccccccccccccc$dddddddddddddddddddddddddddddddddddddddddddddddd
""",
)

# --- Attacktive Directory (THM, reuse) --- steflan-security + shounakdas
write(
    "attacktive.xml",
    nmap_xml(
        comment=(
            "THM Attacktive Directory -- steflan-security + shounakdas "
            "writeups (reused from round-1). Domain spookysec.local0. banner."
        ),
        ip="10.10.230.172",
        ports=[
            {"id": 53, "name": "domain"},
            {"id": 80, "name": "http", "product": "Microsoft IIS httpd", "version": "10.0"},
            {"id": 88, "name": "kerberos-sec", "product": "Microsoft Windows Kerberos"},
            {"id": 135, "name": "msrpc", "product": "Microsoft Windows RPC"},
            {"id": 139, "name": "netbios-ssn", "product": "Microsoft Windows netbios-ssn"},
            ldap_port("Domain: spookysec.local0., Site: Default-First-Site-Name"),
            {"id": 445, "name": "microsoft-ds"},
            {"id": 464, "name": "kpasswd5"},
            {"id": 593, "name": "ncacn_http", "product": "Microsoft Windows RPC over HTTP 1.0"},
            {"id": 636, "name": "tcpwrapped"},
            ldap_port("Domain: spookysec.local0., Site: Default-First-Site-Name", port=3268),
            {"id": 3269, "name": "tcpwrapped"},
            {"id": 3389, "name": "ms-wbt-server", "product": "Microsoft Terminal Services"},
        ],
    ),
)
write(
    "attacktive_getnpusers.txt",
    """Impacket v0.9.22 - Copyright 2020 SecureAuth Corporation

[-] User administrator doesn't have UF_DONT_REQUIRE_PREAUTH set
[-] User backup doesn't have UF_DONT_REQUIRE_PREAUTH set
[*] Getting TGT for svc-admin
$krb5asrep$23$svc-admin@SPOOKYSEC.LOCAL:eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee$ffffffffffffffffffffffffffffffffffffffffffffffff
""",
)

# --- VulnNet: Roasted (THM, reuse) --- sechub.in/view/2345117 + geobour98
write(
    "vulnnet-roasted.xml",
    nmap_xml(
        comment=(
            "THM VulnNet: Roasted -- sechub.in + geobour98 writeups (reused "
            "from round-1). Domain vulnnet-rst.local0. banner."
        ),
        ip="10.10.138.220",
        ports=[
            {"id": 53, "name": "domain", "product": "Simple DNS Plus"},
            {"id": 88, "name": "kerberos-sec", "product": "Microsoft Windows Kerberos"},
            {"id": 135, "name": "msrpc", "product": "Microsoft Windows RPC"},
            {"id": 139, "name": "netbios-ssn", "product": "Microsoft Windows netbios-ssn"},
            ldap_port("Domain: vulnnet-rst.local0., Site: Default-First-Site-Name"),
            {"id": 445, "name": "microsoft-ds"},
            {"id": 464, "name": "kpasswd5"},
            {"id": 593, "name": "ncacn_http", "product": "Microsoft Windows RPC over HTTP 1.0"},
            {"id": 636, "name": "tcpwrapped"},
            ldap_port("Domain: vulnnet-rst.local0., Site: Default-First-Site-Name", port=3268),
            {"id": 3269, "name": "tcpwrapped"},
            {"id": 5985, "name": "http", "product": "Microsoft HTTPAPI httpd", "version": "2.0"},
        ],
    ),
)
write(
    "vulnnet-roasted_getnpusers.txt",
    """Impacket v0.9.22 - Copyright 2020 SecureAuth Corporation

[-] User Administrator doesn't have UF_DONT_REQUIRE_PREAUTH set
[-] User Guest doesn't have UF_DONT_REQUIRE_PREAUTH set
[-] User enterprise-core-vn doesn't have UF_DONT_REQUIRE_PREAUTH set
$krb5asrep$23$t-skid@VULNNET-RST.LOCAL:11111111111111111111111111111111$2222222222222222222222222222222222222222
[-] User j-goldenhand doesn't have UF_DONT_REQUIRE_PREAUTH set
[-] User j-leet doesn't have UF_DONT_REQUIRE_PREAUTH set
""",
)


# ============================================================
# Anonymous LDAP bind (3): Fuse, Manager, Cascade (reuse)
# ============================================================

# --- Fuse --- 0xdf https://0xdf.gitlab.io/2020/10/31/htb-fuse.html
# Domain banner only confirmed on 3268 (GC) in the real -sC -sV output --
# 389 appears in an earlier unversioned full-port sweep only, so this
# fixture deliberately omits a banner on 389 to match what nmap -sV
# actually printed.
write(
    "fuse.xml",
    nmap_xml(
        comment=(
            "HTB Fuse 10.10.10.193 -- 0xdf 2020-10-31. Domain: fabricorp.local "
            "banner appears on port 3268 (GC) in the real -sC -sV output; 389 "
            "shows in an earlier unversioned full sweep with no banner text, "
            "so this fixture matches that (389 has no extrainfo). Anon "
            "ldapsearch -s base namingcontexts succeeds; subtree query fails "
            "without a bind."
        ),
        ip="10.10.10.193",
        ports=[
            {"id": 53, "name": "domain"},
            {"id": 80, "name": "http", "product": "Microsoft IIS httpd", "version": "10.0"},
            {"id": 88, "name": "kerberos-sec", "product": "Microsoft Windows Kerberos"},
            {"id": 135, "name": "msrpc", "product": "Microsoft Windows RPC"},
            {"id": 139, "name": "netbios-ssn", "product": "Microsoft Windows netbios-ssn"},
            {"id": 389, "name": "ldap"},
            {"id": 445, "name": "microsoft-ds", "product": "Windows Server 2016 Standard 14393 microsoft-ds", "extrainfo": "workgroup: FABRICORP"},
            {"id": 464, "name": "kpasswd5"},
            {"id": 593, "name": "ncacn_http", "product": "Microsoft Windows RPC over HTTP 1.0"},
            {"id": 636, "name": "tcpwrapped"},
            ldap_port("Domain: fabricorp.local, Site: Default-First-Site-Name", port=3268),
            {"id": 3269, "name": "tcpwrapped"},
            {"id": 5985, "name": "http", "product": "Microsoft HTTPAPI httpd", "version": "2.0", "extrainfo": "SSDP/UPnP"},
        ],
    ),
)
write(
    "fuse_ldapsearch.txt",
    """# extended LDIF
#
# LDAPv3
# base <> (default) with scope baseObject
# filter: (objectclass=*)
# requesting: namingcontexts
#
# Shape from 0xdf HTB Fuse: ldapsearch -h 10.10.10.193 -x -s base namingcontexts
# succeeds; -b "DC=fabricorp,DC=local" subtree query fails without a bind.
# https://0xdf.gitlab.io/2020/10/31/htb-fuse.html

dn:
namingContexts: DC=fabricorp,DC=local
namingContexts: CN=Configuration,DC=fabricorp,DC=local
namingContexts: CN=Schema,CN=Configuration,DC=fabricorp,DC=local
namingContexts: DC=DomainDnsZones,DC=fabricorp,DC=local
namingContexts: DC=ForestDnsZones,DC=fabricorp,DC=local

# search result
search: 2
result: 0 Success
""",
)

# --- Manager --- 0xdf https://0xdf.gitlab.io/2024/03/16/htb-manager.html
write(
    "manager.xml",
    nmap_xml(
        comment=(
            "HTB Manager 10.10.11.236 -- 0xdf 2024-03-16. DC + MSSQL. Domain: "
            "manager.htb0. banner (trailing 0. artifact). Anon ldapsearch -x "
            "-s base namingcontexts succeeds returning DC=manager,DC=htb; "
            "deeper query fails without a bind. Real exploit path is ADCS "
            "ESC7 with creds -- out of scope."
        ),
        ip="10.10.11.236",
        ports=[
            {"id": 53, "name": "domain"},
            {"id": 80, "name": "http", "product": "Microsoft IIS httpd", "version": "10.0"},
            {"id": 88, "name": "kerberos-sec", "product": "Microsoft Windows Kerberos"},
            {"id": 135, "name": "msrpc", "product": "Microsoft Windows RPC"},
            {"id": 139, "name": "netbios-ssn", "product": "Microsoft Windows netbios-ssn"},
            ldap_port("Domain: manager.htb0., Site: Default-First-Site-Name"),
            {"id": 445, "name": "microsoft-ds"},
            {"id": 464, "name": "kpasswd5"},
            {"id": 593, "name": "ncacn_http", "product": "Microsoft Windows RPC over HTTP 1.0"},
            {"id": 636, "name": "ldap", "product": "Microsoft Windows Active Directory LDAP", "extrainfo": "Domain: manager.htb0., Site: Default-First-Site-Name"},
            {"id": 1433, "name": "ms-sql-s", "product": "Microsoft SQL Server", "version": "15.00.2000.00"},
            ldap_port("Domain: manager.htb0., Site: Default-First-Site-Name", port=3268, name="globalcatLDAP"),
            {"id": 3269, "name": "globalcatLDAPssl", "product": "Microsoft Windows Active Directory LDAP"},
            {"id": 5985, "name": "wsman", "product": "Microsoft HTTPAPI httpd", "version": "2.0"},
            {"id": 9389, "name": "adws", "product": ".NET Message Framing"},
        ],
    ),
)
write(
    "manager_ldapsearch.txt",
    """# extended LDIF
#
# LDAPv3
# base <> (default) with scope baseObject
# filter: (objectclass=*)
# requesting: namingcontexts
#
# Shape from 0xdf HTB Manager:
# ldapsearch -H ldap://dc01.manager.htb -x -s base namingcontexts
# https://0xdf.gitlab.io/2024/03/16/htb-manager.html

dn:
namingcontexts: DC=manager,DC=htb
namingcontexts: CN=Configuration,DC=manager,DC=htb
namingcontexts: CN=Schema,CN=Configuration,DC=manager,DC=htb
namingcontexts: DC=DomainDnsZones,DC=manager,DC=htb
namingcontexts: DC=ForestDnsZones,DC=manager,DC=htb

# search result
search: 2
result: 0 Success
""",
)

# --- Cascade (reuse) --- 0xdf https://0xdf.gitlab.io/2020/07/25/htb-cascade.html
write(
    "cascade.xml",
    nmap_xml(
        comment=(
            "HTB Cascade 10.10.10.182 -- 0xdf 2020-07-25 (reused from "
            "round-1). No 464 in 0xdf all-TCP. Domain: cascade.local banner "
            "(no trailing 0.). Anonymous ldapsearch dumps real users."
        ),
        ip="10.10.10.182",
        ports=[
            {"id": 53, "name": "domain"},
            {"id": 88, "name": "kerberos-sec", "product": "Microsoft Windows Kerberos"},
            {"id": 135, "name": "msrpc", "product": "Microsoft Windows RPC"},
            {"id": 139, "name": "netbios-ssn", "product": "Microsoft Windows netbios-ssn"},
            ldap_port("Domain: cascade.local, Site: Default-First-Site-Name"),
            {"id": 445, "name": "microsoft-ds"},
            {"id": 636, "name": "tcpwrapped"},
            ldap_port("Domain: cascade.local, Site: Default-First-Site-Name", port=3268),
            {"id": 3269, "name": "tcpwrapped"},
            {"id": 5985, "name": "wsman"},
        ],
    ),
)
write(
    "cascade_ldapsearch.txt",
    """# extended LDIF
#
# LDAPv3
# base <> (default) with scope baseObject
# filter: (objectclass=*)
# requesting: namingcontexts
#
# Shape from 0xdf HTB Cascade:
# ldapsearch -h 10.10.10.182 -x -s base namingcontexts
# then ldapsearch -h 10.10.10.182 -x -b "DC=cascade,DC=local"
# https://0xdf.gitlab.io/2020/07/25/htb-cascade.html

dn:
namingContexts: DC=cascade,DC=local
namingContexts: CN=Configuration,DC=cascade,DC=local
namingContexts: CN=Schema,CN=Configuration,DC=cascade,DC=local
namingContexts: DC=DomainDnsZones,DC=cascade,DC=local
namingContexts: DC=ForestDnsZones,DC=cascade,DC=local

# search result
search: 2
result: 0 Success

dn: CN=Ryan Thompson,OU=Users,OU=UK,DC=cascade,DC=local
objectClass: user
objectClass: person
sAMAccountName: r.thompson

dn: CN=ArkSvc,OU=Users,OU=UK,DC=cascade,DC=local
objectClass: user
sAMAccountName: arkSvc
""",
)


# ============================================================
# Negative controls (3, reused verbatim from round 1): Blue, Legacy,
# Netmon -- SMB/RPC-only Windows, NOT domain controllers.
# ============================================================

write(
    "blue.xml",
    nmap_xml(
        comment=(
            "HTB Blue 10.10.10.40 -- 0xdf 2021-05-11 (reused from round-1). "
            "Negative control: Windows 7 workstation, NOT a DC. No LDAP, "
            "Kerberos, or DNS."
        ),
        ip="10.10.10.40",
        ports=[
            {"id": 135, "name": "msrpc", "product": "Microsoft Windows RPC"},
            {"id": 139, "name": "netbios-ssn", "product": "Microsoft Windows netbios-ssn"},
            {"id": 445, "name": "microsoft-ds", "product": "Windows 7 Professional 7601 Service Pack 1 microsoft-ds", "extrainfo": "workgroup: WORKGROUP"},
            {"id": 49152, "name": "msrpc", "product": "Microsoft Windows RPC"},
            {"id": 49153, "name": "msrpc", "product": "Microsoft Windows RPC"},
            {"id": 49154, "name": "msrpc", "product": "Microsoft Windows RPC"},
            {"id": 49155, "name": "msrpc", "product": "Microsoft Windows RPC"},
            {"id": 49156, "name": "msrpc", "product": "Microsoft Windows RPC"},
            {"id": 49157, "name": "msrpc", "product": "Microsoft Windows RPC"},
        ],
    ),
)

write(
    "legacy.xml",
    nmap_xml(
        comment=(
            "HTB Legacy 10.10.10.4 -- justus.pw + 0xdf 2019-02-21 (reused "
            "from round-1). Negative control: Windows XP workstation, NOT a "
            "DC. Workgroup HTB, not a domain. No LDAP/Kerberos/DNS."
        ),
        ip="10.10.10.4",
        ports=[
            {"id": 135, "name": "msrpc", "product": "Microsoft Windows RPC"},
            {"id": 139, "name": "netbios-ssn", "product": "Microsoft Windows netbios-ssn"},
            {"id": 445, "name": "microsoft-ds", "product": "Windows XP microsoft-ds", "extrainfo": "Workgroup: HTB"},
        ],
    ),
)

write(
    "netmon.xml",
    nmap_xml(
        comment=(
            "HTB Netmon 10.10.10.152 -- 0xdf 2019-06-29 + hackingarticles "
            "(reused from round-1). Windows with FTP/HTTP/SMB/RPC. NOT a DC: "
            "no 88/389/53. Negative control -- also the box where the "
            "Anonymous-FTP-vs-AD-LDAP-KB false positive was originally found "
            "and fixed (match_service FTS gate)."
        ),
        ip="10.10.10.152",
        ports=[
            {
                "id": 21,
                "name": "ftp",
                "product": "Microsoft ftpd",
                "scripts": [("ftp-anon", "Anonymous FTP login allowed (FTP code 230)")],
            },
            {
                "id": 80,
                "name": "http",
                "product": "Indy httpd",
                "version": "18.1.37.13946",
                "extrainfo": "Paessler PRTG bandwidth monitor",
            },
            {"id": 135, "name": "msrpc", "product": "Microsoft Windows RPC"},
            {"id": 139, "name": "netbios-ssn", "product": "Microsoft Windows netbios-ssn"},
            {
                "id": 445,
                "name": "microsoft-ds",
                "product": "Microsoft Windows Server 2008 R2 - 2012 microsoft-ds",
            },
        ],
    ),
)

print("done")

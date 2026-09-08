#!/usr/bin/env python3
"""Build real-shaped nmap/gobuster fixtures and drive the Trinity CLI
under an isolated HOME. Facts are cited in MANIFEST.md; this script
only serializes those facts into nmap XML / gobuster text."""
from __future__ import annotations

import os
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "test" / "fixtures" / "coverage_sim"
TRANSCRIPTS = ROOT / "findings" / "transcripts"
PY = str(ROOT / ".venv" / "bin" / "python")
CLI = ROOT / "scripts" / "trinity-cli.py"


def port(
    portid: int,
    service: str,
    product: str | None = None,
    version: str | None = None,
    extrainfo: str | None = None,
    scripts: list[tuple[str, str]] | None = None,
) -> dict:
    return {
        "portid": portid,
        "service": service,
        "product": product,
        "version": version,
        "extrainfo": extrainfo,
        "scripts": scripts or [],
    }


# Each box: host, ports, optional gobuster lines (already in gobuster text format).
BOXES: dict[str, dict] = {
    "lame": {
        "host": "10.10.10.3",
        "ports": [
            port(21, "ftp", "vsftpd", "2.3.4", scripts=[
                ("ftp-anon", "Anonymous FTP login allowed (FTP code 230)"),
            ]),
            port(22, "ssh", "OpenSSH", "4.7p1 Debian 8ubuntu1"),
            port(139, "netbios-ssn", "Samba smbd", "3.X"),
            port(445, "netbios-ssn", "Samba smbd", "3.0.20-Debian"),
            port(3632, "distccd", "distccd", "v1", extrainfo="(GNU) 4.2.4 (Ubuntu 4.2.4-1ubuntu4)"),
        ],
    },
    "nibbles": {
        "host": "10.10.10.75",
        "ports": [
            port(22, "ssh", "OpenSSH", "7.2p2 Ubuntu 4ubuntu2.2"),
            port(80, "http", "Apache httpd", "2.4.18", extrainfo="Ubuntu", scripts=[
                ("http-server-header", "Apache/2.4.18 (Ubuntu)"),
                ("http-title", "Site doesn't have a title (text/html)."),
            ]),
        ],
        "gobuster": [
            "/nibbleblog            (Status: 301) [Size: 318]",
            "/index.html            (Status: 200) [Size: 42]",
        ],
    },
    "shocker": {
        "host": "10.10.10.56",
        "ports": [
            port(80, "http", "Apache httpd", "2.4.18", extrainfo="Ubuntu", scripts=[
                ("http-server-header", "Apache/2.4.18 (Ubuntu)"),
                ("http-title", "Site doesn't have a title (text/html)."),
            ]),
            port(2222, "ssh", "OpenSSH", "7.2p2 Ubuntu 4ubuntu2.2"),
        ],
        "gobuster": [
            "/cgi-bin               (Status: 403) [Size: 294]",
            "/index.html            (Status: 200) [Size: 137]",
            "/cgi-bin/user.sh       (Status: 200) [Size: 119]",
        ],
    },
    "blue": {
        "host": "10.10.10.40",
        "ports": [
            port(135, "msrpc", "Microsoft Windows RPC"),
            port(139, "netbios-ssn", "Microsoft Windows netbios-ssn"),
            port(
                445, "microsoft-ds",
                "Windows 7 Professional 7601 Service Pack 1 microsoft-ds",
                extrainfo="workgroup: WORKGROUP",
                scripts=[
                    (
                        "smb-vuln-ms17-010",
                        "VULNERABLE:\n"
                        "Remote Code Execution vulnerability in Microsoft SMBv1 servers (ms17-010)\n"
                        "State: VULNERABLE\n"
                        "IDs:  CVE:CVE-2017-0143\n"
                        "Risk factor: HIGH",
                    ),
                ],
            ),
        ],
    },
    "legacy": {
        "host": "10.10.10.4",
        "ports": [
            port(139, "netbios-ssn", "Microsoft Windows netbios-ssn"),
            port(
                445, "microsoft-ds", "Windows XP microsoft-ds",
                scripts=[
                    (
                        "smb-vuln-ms08-067",
                        "VULNERABLE:\n"
                        "Microsoft Windows system vulnerable to remote code execution (MS08-067)\n"
                        "State: VULNERABLE\n"
                        "IDs:  CVE:CVE-2008-4250",
                    ),
                    (
                        "smb-vuln-ms17-010",
                        "VULNERABLE:\n"
                        "Remote Code Execution vulnerability in Microsoft SMBv1 servers (ms17-010)\n"
                        "State: VULNERABLE\n"
                        "IDs:  CVE:CVE-2017-0143\n"
                        "Risk factor: HIGH",
                    ),
                ],
            ),
        ],
    },
    "netmon": {
        "host": "10.10.10.152",
        "ports": [
            port(21, "ftp", "Microsoft ftpd", scripts=[
                ("ftp-anon", "Anonymous FTP login allowed (FTP code 230)"),
            ]),
            port(
                80, "http", "Indy httpd", "18.1.37.13946",
                extrainfo="Paessler PRTG bandwidth monitor",
                scripts=[
                    ("http-server-header", "PRTG/18.1.37.13946"),
                    ("http-title", "Welcome | PRTG Network Monitor (NETMON)"),
                ],
            ),
            port(135, "msrpc", "Microsoft Windows RPC"),
            port(139, "netbios-ssn", "Microsoft Windows netbios-ssn"),
            port(445, "microsoft-ds", "Microsoft Windows Server 2008 R2 - 2012 microsoft-ds"),
            port(5985, "http", "Microsoft HTTPAPI httpd", "2.0", extrainfo="SSDP/UPnP"),
        ],
    },
    "devel": {
        "host": "10.10.10.5",
        "ports": [
            port(21, "ftp", "Microsoft ftpd", scripts=[
                ("ftp-anon", "Anonymous FTP login allowed (FTP code 230)\n"
                 "03-18-17  01:06AM       <DIR>          aspnet_client\n"
                 "03-17-17  04:37PM                  689 iisstart.htm\n"
                 "03-17-17  04:37PM               184946 welcome.png"),
            ]),
            port(80, "http", "Microsoft IIS httpd", "7.5", scripts=[
                ("http-server-header", "Microsoft-IIS/7.5"),
                ("http-title", "IIS7"),
            ]),
        ],
    },
    "granny": {
        "host": "10.10.10.15",
        "ports": [
            port(80, "http", "Microsoft IIS httpd", "6.0", scripts=[
                ("http-methods", "Potentially risky methods: TRACE DELETE COPY MOVE PROPFIND PROPPATCH SEARCH MKCOL LOCK UNLOCK PUT"),
                ("http-server-header", "Microsoft-IIS/6.0"),
                ("http-title", "Under Construction"),
                ("http-webdav-scan", "WebDAV type: Unknown\nAllowed Methods: OPTIONS, TRACE, GET, HEAD, DELETE, COPY, MOVE, PROPFIND, PROPPATCH, SEARCH, MKCOL, LOCK, UNLOCK\nPublic Options: OPTIONS, TRACE, GET, HEAD, DELETE, PUT, POST, COPY, MOVE, MKCOL, PROPFIND, PROPPATCH, LOCK, UNLOCK, SEARCH"),
            ]),
        ],
    },
    "grandpa": {
        "host": "10.10.10.14",
        "ports": [
            port(80, "http", "Microsoft IIS httpd", "6.0", scripts=[
                ("http-methods", "Potentially risky methods: TRACE COPY PROPFIND SEARCH LOCK UNLOCK DELETE PUT MOVE MKCOL PROPPATCH"),
                ("http-server-header", "Microsoft-IIS/6.0"),
                ("http-title", "Under Construction"),
                ("http-webdav-scan", "WebDAV type: Unknown\nPublic Options: OPTIONS, TRACE, GET, HEAD, DELETE, PUT, POST, COPY, MOVE, MKCOL, PROPFIND, PROPPATCH, LOCK, UNLOCK, SEARCH\nAllowed Methods: OPTIONS, TRACE, GET, HEAD, COPY, PROPFIND, SEARCH, LOCK, UNLOCK"),
            ]),
        ],
    },
    "jerry": {
        "host": "10.10.10.95",
        "ports": [
            port(8080, "http", "Apache Tomcat/Coyote JSP engine", "1.1", scripts=[
                ("http-server-header", "Apache-Coyote/1.1"),
                ("http-title", "Site doesn't have a title."),
            ]),
        ],
    },
    "optimum": {
        "host": "10.10.10.8",
        "ports": [
            port(80, "http", "HttpFileServer httpd", "2.3", scripts=[
                ("http-server-header", "HFS 2.3"),
                ("http-title", "HFS /"),
            ]),
        ],
    },
    "bashed": {
        "host": "10.10.10.68",
        "ports": [
            port(80, "http"),
        ],
        "gobuster": [
            "/images                (Status: 301) [Size: 178]",
            "/uploads               (Status: 301) [Size: 178]",
            "/php                   (Status: 301) [Size: 178]",
            "/css                   (Status: 301) [Size: 178]",
            "/dev                   (Status: 301) [Size: 178]",
            "/js                    (Status: 301) [Size: 178]",
            "/fonts                 (Status: 301) [Size: 178]",
        ],
    },
    "knife": {
        "host": "10.10.10.242",
        "ports": [
            port(22, "ssh", "OpenSSH", "8.2p1 Ubuntu 4ubuntu0.2"),
            port(80, "http", "Apache httpd", "2.4.41", extrainfo="Ubuntu", scripts=[
                ("http-server-header", "Apache/2.4.41 (Ubuntu)"),
                ("http-title", "Emergent Medical Idea"),
            ]),
        ],
    },
    "valentine": {
        "host": "10.10.10.79",
        "ports": [
            port(22, "ssh", "OpenSSH", "5.9p1 Debian 5ubuntu1.10"),
            port(80, "http", "Apache httpd", "2.2.22", extrainfo="Ubuntu", scripts=[
                ("http-title", "Site doesn't have a title (text/html)."),
            ]),
            port(443, "https", "Apache httpd", "2.2.22", extrainfo="Ubuntu", scripts=[
                ("http-server-header", "Apache/2.2.22 (Ubuntu)"),
                ("http-title", "Site doesn't have a title (text/html)."),
            ]),
        ],
    },
    "beep": {
        "host": "10.10.10.7",
        "ports": [
            port(22, "ssh", "OpenSSH", "4.3"),
            port(25, "smtp", "Postfix smtpd"),
            port(80, "http", "Apache httpd", "2.2.3", scripts=[
                ("http-server-header", "Apache/2.2.3 (CentOS)"),
                ("http-title", "Did not follow redirect to https://10.10.10.7/"),
            ]),
            port(443, "https", "Apache httpd", "2.2.3", extrainfo="CentOS", scripts=[
                ("http-server-header", "Apache/2.2.3 (CentOS)"),
                ("http-title", "Elastix - Login page"),
            ]),
            port(3306, "mysql", "MySQL"),
            port(5038, "asterisk", "Asterisk Call Manager", "1.1"),
            port(10000, "http", "MiniServ", "1.570", extrainfo="Webmin httpd"),
        ],
        "gobuster": [
            "/vtigercrm             (Status: 301) [Size: 318]",
        ],
    },
    "sense": {
        "host": "10.10.10.60",
        "ports": [
            port(80, "http", "lighttpd", "1.4.35", scripts=[
                ("http-server-header", "lighttpd/1.4.35"),
                ("http-title", "Did not follow redirect to https://10.10.10.60/"),
            ]),
            port(443, "https", "lighttpd", "1.4.35", scripts=[
                ("http-server-header", "lighttpd/1.4.35"),
                ("http-title", "Login"),
            ]),
        ],
        "gobuster": [
            "/changelog.txt         (Status: 200) [Size: 271]",
            "/system-users.txt      (Status: 200) [Size: 106]",
            "/themes                (Status: 301) [Size: 178]",
            "/includes              (Status: 301) [Size: 178]",
        ],
    },
    "forest": {
        "host": "10.10.10.161",
        "ports": [
            port(53, "domain"),
            port(88, "kerberos-sec", "Microsoft Windows Kerberos"),
            port(135, "msrpc", "Microsoft Windows RPC"),
            port(139, "netbios-ssn", "Microsoft Windows netbios-ssn"),
            port(389, "ldap", "Microsoft Windows Active Directory LDAP", extrainfo="Domain: htb.local"),
            port(445, "microsoft-ds", "Windows Server 2016 Standard 14393 microsoft-ds", extrainfo="workgroup: HTB"),
            port(464, "kpasswd5"),
            port(636, "ldapssl"),
            port(3268, "ldap", "Microsoft Windows Active Directory LDAP", extrainfo="Domain: htb.local"),
            port(5985, "http", "Microsoft HTTPAPI httpd", "2.0", extrainfo="SSDP/UPnP"),
            port(9389, "mc-nmf", ".NET Message Framing"),
        ],
    },
    "active": {
        "host": "10.10.10.100",
        "ports": [
            port(53, "domain", "Microsoft DNS", "6.1.7600"),
            port(88, "kerberos-sec", "Microsoft Windows Kerberos"),
            port(135, "msrpc", "Microsoft Windows RPC"),
            port(139, "netbios-ssn", "Microsoft Windows netbios-ssn"),
            port(389, "ldap", "Microsoft Windows Active Directory LDAP", extrainfo="Domain: active.htb"),
            port(445, "microsoft-ds"),
            port(464, "kpasswd5"),
            port(3268, "ldap", "Microsoft Windows Active Directory LDAP", extrainfo="Domain: active.htb"),
            port(9389, "mc-nmf", ".NET Message Framing"),
        ],
    },
    "armageddon": {
        "host": "10.10.10.233",
        "ports": [
            port(22, "ssh", "OpenSSH", "7.4"),
            port(80, "http", "Apache httpd", "2.4.6", extrainfo="CentOS PHP/5.4.16", scripts=[
                ("http-generator", "Drupal 7 (http://drupal.org)"),
                ("http-robots.txt", "36 disallowed entries (15 shown)\n/includes/ /misc/ /modules/ /profiles/ /scripts/\n/themes/ /CHANGELOG.txt /cron.php /INSTALL.mysql.txt"),
                ("http-server-header", "Apache/2.4.6 (CentOS) PHP/5.4.16"),
                ("http-title", "Welcome to  Armageddon |  Armageddon"),
            ]),
        ],
    },
    "mirai": {
        "host": "10.10.10.48",
        "ports": [
            port(22, "ssh", "OpenSSH", "6.7p1 Debian 5+deb8u3"),
            port(53, "domain", "dnsmasq", "2.76"),
            port(80, "http", "lighttpd", "1.4.35", scripts=[
                ("http-server-header", "lighttpd/1.4.35"),
                ("http-title", "Site doesn't have a title (text/html; charset=UTF-8)."),
            ]),
            port(32400, "http", "Plex Media Server httpd", scripts=[
                ("http-title", "Unauthorized"),
            ]),
        ],
        "gobuster": [
            "/admin                 (Status: 301) [Size: 0]",
        ],
    },
    # --- batch 2: Medium + new categories + first THM ---
    "arctic": {
        "host": "10.10.10.11",
        "ports": [
            port(135, "msrpc", "Microsoft Windows RPC"),
            port(8500, "fmtp"),
            port(49154, "msrpc", "Microsoft Windows RPC"),
        ],
        # Directory listing on 8500 (0xdf), not invented gobuster.
        "gobuster": [
            "/CFIDE                 (Status: 301) [Size: 0]",
            "/cfdocs                (Status: 301) [Size: 0]",
        ],
    },
    "postman": {
        "host": "10.10.10.160",
        "ports": [
            port(22, "ssh", "OpenSSH", "7.6p1 Ubuntu 4ubuntu0.3"),
            port(80, "http", "Apache httpd", "2.4.29", extrainfo="Ubuntu", scripts=[
                ("http-server-header", "Apache/2.4.29 (Ubuntu)"),
                ("http-title", "The Cyber Geek's Personal Website"),
            ]),
            port(6379, "redis", "Redis key-value store", "4.0.9"),
            port(10000, "http", "MiniServ", "1.910", extrainfo="Webmin httpd", scripts=[
                ("http-title", "Site doesn't have a title (text/html; Charset=iso-8859-1)."),
            ]),
        ],
    },
    "solidstate": {
        "host": "10.10.10.51",
        "ports": [
            port(22, "ssh", "OpenSSH", "7.4p1 Debian 10+deb9u1"),
            port(25, "smtp", "JAMES smtpd", "2.3.2"),
            port(80, "http", "Apache httpd", "2.4.25", extrainfo="Debian", scripts=[
                ("http-server-header", "Apache/2.4.25 (Debian)"),
                ("http-title", "Home - Solid State Security"),
            ]),
            port(110, "pop3", "JAMES pop3d", "2.3.2"),
            port(119, "nntp", "JAMES nntpd", extrainfo="posting ok"),
            port(4555, "james-admin", "JAMES Remote Admin", "2.3.2"),
        ],
    },
    "jeeves": {
        "host": "10.10.10.63",
        "ports": [
            port(80, "http", "Microsoft IIS httpd", "10.0", scripts=[
                ("http-methods", "Potentially risky methods: TRACE"),
                ("http-server-header", "Microsoft-IIS/10.0"),
                ("http-title", "Ask Jeeves"),
            ]),
            port(135, "msrpc", "Microsoft Windows RPC"),
            port(445, "microsoft-ds", "Microsoft Windows 7 - 10 microsoft-ds", extrainfo="workgroup: WORKGROUP"),
            port(50000, "http", "Jetty", "9.4.z-SNAPSHOT", scripts=[
                ("http-server-header", "Jetty(9.4.z-SNAPSHOT)"),
                ("http-title", "Error 404 Not Found"),
            ]),
        ],
        "gobuster": [
            "/askjeeves             (Status: 302) [Size: 0]",
        ],
    },
    "irked": {
        "host": "10.10.10.117",
        "ports": [
            port(22, "ssh", "OpenSSH", "6.7p1 Debian 5+deb8u4"),
            port(80, "http", "Apache httpd", "2.4.10", extrainfo="Debian", scripts=[
                ("http-server-header", "Apache/2.4.10 (Debian)"),
                ("http-title", "Site doesn't have a title (text/html)."),
            ]),
            port(111, "rpcbind", extrainfo="2-4 (RPC #100000)"),
            port(6697, "irc", "UnrealIRCd"),
            port(8067, "irc", "UnrealIRCd"),
            port(65534, "irc", "UnrealIRCd"),
        ],
    },
    "traverxec": {
        "host": "10.10.10.165",
        "ports": [
            port(22, "ssh", "OpenSSH", "7.9p1 Debian 10+deb10u1"),
            port(80, "http", "nostromo", "1.9.6", scripts=[
                ("http-server-header", "nostromo 1.9.6"),
                ("http-title", "TRAVERXEC"),
            ]),
        ],
    },
    "chatterbox": {
        "host": "10.10.10.74",
        "ports": [
            port(9255, "mon"),
            port(9256, "unknown"),
        ],
    },
    "openadmin": {
        "host": "10.10.10.171",
        "ports": [
            port(22, "ssh", "OpenSSH", "7.6p1 Ubuntu 4ubuntu0.3"),
            port(80, "http", "Apache httpd", "2.4.29", extrainfo="Ubuntu", scripts=[
                ("http-server-header", "Apache/2.4.29 (Ubuntu)"),
                ("http-title", "Apache2 Ubuntu Default Page: It works"),
            ]),
        ],
        # /ona is the Login link from /music (0xdf), not a gobuster hit.
        # Same "attested path" standard as Nibbles HTML comment.
        "gobuster": [
            "/music                 (Status: 301) [Size: 0]",
            "/artwork               (Status: 301) [Size: 0]",
            "/sierra                (Status: 301) [Size: 0]",
            "/ona                   (Status: 301) [Size: 0]",
        ],
    },
    "bastard": {
        "host": "10.10.10.9",
        "ports": [
            port(80, "http", "Microsoft IIS httpd", "7.5", scripts=[
                ("http-generator", "Drupal 7 (http://drupal.org)"),
                ("http-methods", "Potentially risky methods: TRACE"),
                ("http-robots.txt", "36 disallowed entries (15 shown)\n/includes/ /misc/ /modules/ /profiles/ /scripts/\n/themes/ /CHANGELOG.txt /cron.php /INSTALL.mysql.txt"),
                ("http-server-header", "Microsoft-IIS/7.5"),
                ("http-title", "Welcome to 10.10.10.9 | 10.10.10.9"),
            ]),
            port(135, "msrpc", "Microsoft Windows RPC"),
            port(49154, "msrpc", "Microsoft Windows RPC"),
        ],
    },
    "silo": {
        "host": "10.10.10.82",
        "ports": [
            port(80, "http", "Microsoft IIS httpd", "8.5", scripts=[
                ("http-methods", "Potentially risky methods: TRACE"),
                ("http-server-header", "Microsoft-IIS/8.5"),
                ("http-title", "IIS Windows Server"),
            ]),
            port(135, "msrpc", "Microsoft Windows RPC"),
            port(139, "netbios-ssn"),
            port(445, "microsoft-ds", "Microsoft Windows Server 2008 R2 - 2012 microsoft-ds"),
            port(1521, "oracle-tns", "Oracle TNS listener", "11.2.0.2.0", extrainfo="unauthorized"),
            port(5985, "http", "Microsoft HTTPAPI httpd", "2.0", extrainfo="SSDP/UPnP"),
        ],
    },
    "sauna": {
        "host": "10.10.10.175",
        "ports": [
            port(53, "domain"),
            port(80, "http", "Microsoft IIS httpd", "10.0", scripts=[
                ("http-title", "Egotistical Bank :: Home"),
            ]),
            port(88, "kerberos-sec", "Microsoft Windows Kerberos"),
            port(135, "msrpc", "Microsoft Windows RPC"),
            port(139, "netbios-ssn", "Microsoft Windows netbios-ssn"),
            port(389, "ldap", "Microsoft Windows Active Directory LDAP", extrainfo="Domain: EGOTISTICAL-BANK.LOCAL0., Site: Default-First-Site-Name"),
            port(445, "microsoft-ds"),
            port(464, "kpasswd5"),
            port(593, "ncacn_http", "Microsoft Windows RPC over HTTP", "1.0"),
            port(3268, "ldap", "Microsoft Windows Active Directory LDAP", extrainfo="Domain: EGOTISTICAL-BANK.LOCAL0., Site: Default-First-Site-Name"),
            port(5985, "http", "Microsoft HTTPAPI httpd", "2.0", extrainfo="SSDP/UPnP"),
        ],
    },
    "vulnversity": {
        "host": "10.10.137.135",
        "ports": [
            port(21, "ftp", "vsftpd", "3.0.3"),
            port(22, "ssh", "OpenSSH", "7.2p2 Ubuntu 4ubuntu2.7"),
            port(139, "netbios-ssn", "Samba smbd", "3.X - 4.X", extrainfo="workgroup: WORKGROUP"),
            port(445, "microsoft-ds", "Samba smbd", "4.3.11-Ubuntu", extrainfo="workgroup: WORKGROUP"),
            port(3128, "http-proxy", "Squid http proxy", "3.5.12", scripts=[
                ("http-title", "ERROR: The requested URL could not be retrieved"),
                ("http-server-header", "squid/3.5.12"),
            ]),
            port(3333, "http", "Apache httpd", "2.4.18", extrainfo="Ubuntu", scripts=[
                ("http-server-header", "Apache/2.4.18 (Ubuntu)"),
                ("http-title", "Vuln University"),
            ]),
        ],
        "gobuster": [
            "/images                (Status: 301) [Size: 322]",
            "/css                   (Status: 301) [Size: 319]",
            "/js                    (Status: 301) [Size: 318]",
            "/fonts                 (Status: 301) [Size: 321]",
            "/internal              (Status: 301) [Size: 324]",
        ],
    },
    "ice": {
        "host": "10.10.139.241",
        "ports": [
            port(135, "msrpc", "Microsoft Windows RPC"),
            port(139, "netbios-ssn", "Microsoft Windows netbios-ssn"),
            port(445, "microsoft-ds", "Windows 7 Professional 7601 Service Pack 1 microsoft-ds", extrainfo="workgroup: WORKGROUP"),
            port(3389, "ms-wbt-server"),
            port(5357, "http", "Microsoft HTTPAPI httpd", "2.0", extrainfo="SSDP/UPnP", scripts=[
                ("http-title", "Service Unavailable"),
                ("http-server-header", "Microsoft-HTTPAPI/2.0"),
            ]),
            port(8000, "http", "Icecast streaming media server", scripts=[
                ("http-title", "Site doesn't have a title (text/html)."),
            ]),
        ],
    },
    "kenobi": {
        "host": "10.10.51.164",
        "ports": [
            port(21, "ftp", "ProFTPD", "1.3.5"),
            port(22, "ssh", "OpenSSH", "7.2p2 Ubuntu 4ubuntu2.7"),
            port(80, "http", "Apache httpd", "2.4.18", extrainfo="Ubuntu", scripts=[
                ("http-robots.txt", "1 disallowed entry\n/admin.html"),
                ("http-title", "Site doesn't have a title (text/html)."),
                ("http-server-header", "Apache/2.4.18 (Ubuntu)"),
            ]),
            port(111, "rpcbind", extrainfo="2-4 (RPC #100000)"),
            port(139, "netbios-ssn", "Samba smbd", "3.X - 4.X", extrainfo="workgroup: WORKGROUP"),
            port(445, "netbios-ssn", "Samba smbd", "4.3.11-Ubuntu", extrainfo="workgroup: WORKGROUP"),
            port(2049, "nfs_acl", extrainfo="2-3 (RPC #100227)"),
        ],
    },
    "sunday": {
        "host": "10.10.10.76",
        "ports": [
            port(79, "finger", "Sun Solaris fingerd", scripts=[
                ("finger", "Login       Name               TTY         Idle    When    Where\n"
                 "sunny    sunny                 pts/1            Thu 14:52  10.10.14.245"),
            ]),
            port(111, "rpcbind", extrainfo="2-4 (RPC #100000)"),
            port(22022, "ssh", "SunSSH", "1.3"),
            port(65258, "smserverd", extrainfo="1 (RPC #100155)"),
        ],
    },
    "scriptkiddie": {
        "host": "10.10.10.226",
        "ports": [
            port(22, "ssh", "OpenSSH", "8.2p1 Ubuntu 4ubuntu0.1"),
            port(5000, "http", "Werkzeug httpd", "0.16.1", extrainfo="Python 3.8.5", scripts=[
                ("http-title", "k1d'5 h4ck3r t00l5"),
            ]),
        ],
    },
    "ready": {
        "host": "10.10.10.220",
        "ports": [
            port(22, "ssh", "OpenSSH", "8.2p1 Ubuntu 4"),
            port(5080, "http", "nginx", scripts=[
                ("http-robots.txt", "53 disallowed entries (15 shown)\n/ /autocomplete/users /search /api /admin /profile"),
                ("http-title", "Sign in \\xC2\\xB7 GitLab"),
            ]),
        ],
    },
    "remote": {
        "host": "10.10.10.180",
        "ports": [
            port(21, "ftp", "Microsoft ftpd", scripts=[
                ("ftp-anon", "Anonymous FTP login allowed (FTP code 230)"),
            ]),
            port(80, "http", "Microsoft HTTPAPI httpd", "2.0", extrainfo="SSDP/UPnP", scripts=[
                ("http-title", "Home - Acme Widgets"),
            ]),
            port(111, "rpcbind", extrainfo="2-4 (RPC #100000)"),
            port(135, "msrpc", "Microsoft Windows RPC"),
            port(139, "netbios-ssn", "Microsoft Windows netbios-ssn"),
            port(445, "microsoft-ds"),
            port(2049, "mountd", extrainfo="1-3 (RPC #100005)"),
            port(5985, "http", "Microsoft HTTPAPI httpd", "2.0", extrainfo="SSDP/UPnP"),
        ],
    },
    "buff": {
        "host": "10.10.10.198",
        "ports": [
            port(7680, "pando-pub"),
            port(8080, "http", "Apache httpd", "2.4.43", extrainfo="Win64 OpenSSL/1.1.1g PHP/7.4.6", scripts=[
                ("http-server-header", "Apache/2.4.43 (Win64) OpenSSL/1.1.1g PHP/7.4.6"),
                ("http-title", "mrb3n's Bro Hut"),
            ]),
        ],
        "gobuster": [
            "/profile               (Status: 301) [Size: 0]",
            "/admin                 (Status: 301) [Size: 0]",
            "/upload                (Status: 301) [Size: 0]",
            "/license               (Status: 200) [Size: 0]",
        ],
    },
    "alfred": {
        "host": "10.10.154.52",
        "ports": [
            port(80, "http", "Microsoft IIS httpd", "7.5", scripts=[
                ("http-server-header", "Microsoft-IIS/7.5"),
            ]),
            port(3389, "ms-wbt-server"),
            port(8080, "http", "Jetty", "9.4.z-SNAPSHOT", scripts=[
                ("http-server-header", "Jetty(9.4.z-SNAPSHOT)"),
            ]),
        ],
    },
    "ignite": {
        "host": "10.10.183.1",
        "ports": [
            port(80, "http", "Apache httpd", "2.4.18", extrainfo="Ubuntu", scripts=[
                ("http-robots.txt", "1 disallowed entry\n/fuel/"),
                ("http-title", "Welcome to FUEL CMS"),
            ]),
        ],
        "gobuster": [
            "/fuel                  (Status: 301) [Size: 0]",
        ],
    },
    "skynet": {
        "host": "10.10.201.231",
        "ports": [
            port(22, "ssh", "OpenSSH", "7.2p2 Ubuntu 4ubuntu2.8"),
            port(80, "http", "Apache httpd", "2.4.18", extrainfo="Ubuntu", scripts=[
                ("http-title", "Skynet"),
            ]),
            port(110, "pop3", "Dovecot pop3d"),
            port(139, "netbios-ssn", "Samba smbd", "3.X - 4.X"),
            port(143, "imap", "Dovecot imapd"),
            port(445, "netbios-ssn", "Samba smbd", "4.3.11-Ubuntu"),
        ],
        "gobuster": [
            "/squirrelmail          (Status: 301) [Size: 0]",
        ],
    },
    "yearoftherabbit": {
        "host": "10.10.243.82",
        "ports": [
            port(21, "ftp", "vsftpd", "3.0.2"),
            port(22, "ssh", "OpenSSH", "6.7p1 Debian 5"),
            port(80, "http", "Apache httpd", "2.4.10", extrainfo="Debian", scripts=[
                ("http-title", "Apache2 Debian Default Page: It works"),
            ]),
        ],
    },
    "anonymous": {
        "host": "10.10.25.138",
        "ports": [
            port(21, "ftp", "vsftpd", "3.0.3", scripts=[
                ("ftp-anon", "Anonymous FTP login allowed (FTP code 230)"),
            ]),
            port(22, "ssh", "OpenSSH", "7.6p1 Ubuntu 4ubuntu0.3"),
            port(139, "netbios-ssn", "Samba smbd", "3.X - 4.X"),
            port(445, "netbios-ssn", "Samba smbd", "4.7.6-Ubuntu"),
        ],
    },
    "basicpentesting": {
        "host": "10.10.126.175",
        "ports": [
            port(22, "ssh", "OpenSSH", "7.2p2 Ubuntu 4ubuntu2.4"),
            port(80, "http", "Apache httpd", "2.4.18", extrainfo="Ubuntu"),
            port(139, "netbios-ssn", "Samba smbd", "3.X - 4.X"),
            port(445, "netbios-ssn", "Samba smbd", "4.3.11-Ubuntu"),
            port(8009, "ajp13", "Apache Jserv", extrainfo="Protocol v1.3"),
            port(8080, "http", "Apache Tomcat", "9.0.7", scripts=[
                ("http-title", "Apache Tomcat/9.0.7"),
            ]),
        ],
        "gobuster": [
            "/development           (Status: 301) [Size: 0]",
        ],
    },
    "overpass": {
        "host": "10.10.164.129",
        "ports": [
            port(22, "ssh", "OpenSSH", "7.6p1 Ubuntu 4ubuntu0.3"),
            port(80, "http", "Golang net/http server", scripts=[
                ("http-title", "Overpass"),
            ]),
        ],
        "gobuster": [
            "/admin                 (Status: 301) [Size: 0]",
            "/downloads             (Status: 301) [Size: 0]",
        ],
    },
    "relevant": {
        "host": "10.10.236.240",
        "ports": [
            port(80, "http", "Microsoft IIS httpd", "10.0"),
            port(135, "msrpc", "Microsoft Windows RPC"),
            port(139, "netbios-ssn", "Microsoft Windows netbios-ssn"),
            port(445, "microsoft-ds", "Windows Server 2016 Standard Evaluation 14393 microsoft-ds"),
            port(3389, "ms-wbt-server", "Microsoft Terminal Services"),
            port(49663, "http", "Microsoft IIS httpd", "10.0"),
        ],
    },
    "attacktivedirectory": {
        "host": "10.10.125.7",
        "ports": [
            port(53, "domain"),
            port(80, "http", "Microsoft IIS httpd", "10.0", scripts=[
                ("http-title", "IIS Windows Server"),
            ]),
            port(88, "kerberos-sec", "Microsoft Windows Kerberos"),
            port(135, "msrpc", "Microsoft Windows RPC"),
            port(139, "netbios-ssn", "Microsoft Windows netbios-ssn"),
            port(389, "ldap", "Microsoft Windows Active Directory LDAP", extrainfo="Domain: spookysec.local, Site: Default-First-Site-Name"),
            port(445, "microsoft-ds"),
            port(464, "kpasswd5"),
            port(3268, "ldap", "Microsoft Windows Active Directory LDAP", extrainfo="Domain: spookysec.local"),
            port(3389, "ms-wbt-server"),
            port(5985, "wsman"),
            port(9389, "adws"),
        ],
    },
    "picklerick": {
        "host": "10.10.123.34",
        "ports": [
            port(22, "ssh", "OpenSSH", "7.2p2 Ubuntu 4ubuntu2.6"),
            port(80, "http", "Apache httpd", "2.4.18", extrainfo="Ubuntu", scripts=[
                ("http-title", "Rick is sup4r cool"),
            ]),
        ],
        "gobuster": [
            "/login.php             (Status: 200) [Size: 0]",
            "/robots.txt            (Status: 200) [Size: 0]",
        ],
    },
    "simplectf": {
        "host": "10.10.112.164",
        "ports": [
            port(21, "ftp", "vsftpd", "3.0.3", scripts=[
                ("ftp-anon", "Anonymous FTP login allowed (FTP code 230)"),
            ]),
            port(80, "http", "Apache httpd", "2.4.18", extrainfo="Ubuntu", scripts=[
                ("http-robots.txt", "1 disallowed entry\n/openemr-5_0_1_3"),
            ]),
            port(2222, "ssh", "OpenSSH", "7.2p2 Ubuntu 4ubuntu0.8"),
        ],
        "gobuster": [
            "/simple                (Status: 301) [Size: 0]",
        ],
    },
    "source": {
        "host": "10.10.178.7",
        "ports": [
            port(22, "ssh", "OpenSSH", "7.6p1 Ubuntu 4ubuntu0.3"),
            port(10000, "http", "MiniServ", "1.890", extrainfo="Webmin httpd", scripts=[
                ("http-server-header", "MiniServ/1.890"),
            ]),
        ],
    },
    "tomghost": {
        "host": "10.10.80.104",
        "ports": [
            port(22, "ssh", "OpenSSH", "7.2p2 Ubuntu 4ubuntu2.8"),
            port(8009, "ajp13", "Apache Jserv", extrainfo="Protocol v1.3"),
            port(8080, "http", "Apache Tomcat", "9.0.30", scripts=[
                ("http-title", "Apache Tomcat/9.0.30"),
            ]),
        ],
    },
    "steelmountain": {
        "host": "10.10.55.10",
        "ports": [
            port(80, "http", "Microsoft IIS httpd", "8.5"),
            port(135, "msrpc", "Microsoft Windows RPC"),
            port(139, "netbios-ssn", "Microsoft Windows netbios-ssn"),
            port(445, "microsoft-ds", "Microsoft Windows Server 2008 R2 - 2012 microsoft-ds"),
            port(3389, "ms-wbt-server"),
            port(5985, "http", "Microsoft HTTPAPI httpd", "2.0", extrainfo="SSDP/UPnP"),
            port(8080, "http", "HttpFileServer httpd", "2.3", scripts=[
                ("http-server-header", "HFS 2.3"),
            ]),
        ],
    },
    "kioptrix1": {
        "host": "192.168.1.104",
        "ports": [
            port(22, "ssh", "OpenSSH", "2.9p2"),
            port(80, "http", "Apache httpd", "1.3.20", extrainfo="Unix Red-Hat/Linux mod_ssl/2.8.4 OpenSSL/0.9.6b"),
            port(111, "rpcbind", extrainfo="2 (RPC #100000)"),
            port(139, "netbios-ssn", "Samba smbd", extrainfo="workgroup: MYGROUP"),
            port(443, "https", "Apache httpd", "1.3.20", extrainfo="Unix Red-Hat/Linux mod_ssl/2.8.4 OpenSSL/0.9.6b", scripts=[
                ("http-server-header", "Apache/1.3.20 (Unix) (Red-Hat/Linux) mod_ssl/2.8.4 OpenSSL/0.9.6b"),
            ]),
        ],
    },
    "stapler": {
        "host": "192.168.43.197",
        "ports": [
            port(21, "ftp", "vsftpd", scripts=[
                ("ftp-anon", "Anonymous FTP login allowed (FTP code 230)"),
            ]),
            port(22, "ssh", "OpenSSH", "7.2p2 Ubuntu 4"),
            port(53, "domain", "dnsmasq", "2.75"),
            port(80, "http", "PHP cli server", "5.5 or later"),
            port(139, "netbios-ssn", "Samba smbd", "3.X - 4.X"),
            port(3306, "mysql", "MySQL", "5.7.12-0ubuntu1"),
            port(12380, "http", "Apache httpd", "2.4.18", extrainfo="Ubuntu"),
        ],
    },
    "dc1": {
        "host": "192.168.178.21",
        "ports": [
            port(22, "ssh", "OpenSSH", "6.0p1 Debian 4+deb7u7"),
            port(80, "http", "Apache httpd", "2.2.22", extrainfo="Debian", scripts=[
                ("http-generator", "Drupal 7"),
                ("http-title", "Welcome to Drupal Site"),
            ]),
            port(111, "rpcbind", extrainfo="2-4"),
        ],
    },
    "dc3": {
        "host": "192.168.56.116",
        "ports": [
            port(80, "http", "Apache httpd", "2.4.18", extrainfo="Ubuntu", scripts=[
                ("http-generator", "Joomla!"),
                ("http-title", "Home"),
            ]),
        ],
    },
    "lazysysadmin": {
        "host": "172.16.96.131",
        "ports": [
            port(22, "ssh", "OpenSSH", "6.6.1p1 Ubuntu 2ubuntu2.8"),
            port(80, "http", "Apache httpd", "2.4.7", extrainfo="Ubuntu", scripts=[
                ("http-generator", "Silex v2.2.7"),
                ("http-title", "Backnode"),
            ]),
            port(139, "netbios-ssn", "Samba smbd", "3.X - 4.X"),
            port(445, "netbios-ssn", "Samba smbd", "4.3.11-Ubuntu"),
            port(3306, "mysql", "MySQL"),
            port(6667, "irc", "InspIRCd"),
        ],
        "gobuster": [
            "/wordpress             (Status: 301) [Size: 0]",
        ],
    },
    "goldeneye": {
        "host": "192.168.111.128",
        "ports": [
            port(25, "smtp", "Postfix smtpd"),
            port(80, "http", "Apache httpd", "2.4.7", extrainfo="Ubuntu", scripts=[
                ("http-title", "GoldenEye Primary Admin Server"),
            ]),
            port(55006, "pop3", "Dovecot pop3d"),
            port(55007, "pop3", "Dovecot pop3d"),
        ],
        "gobuster": [
            "/gnocertdir            (Status: 301) [Size: 0]",
        ],
    },
    "brainpan": {
        "host": "10.10.92.146",
        "ports": [
            port(9999, "abyss"),
            port(10000, "http", "SimpleHTTPServer", "0.6", extrainfo="Python 2.7.3"),
        ],
        "gobuster": [
            "/bin                   (Status: 301) [Size: 0]",
        ],
    },
    "kioptrix2": {
        "host": "192.168.56.9",
        "ports": [
            port(22, "ssh", "OpenSSH", "3.9p1"),
            port(80, "http", "Apache httpd", "2.0.52", extrainfo="CentOS", scripts=[
                ("http-title", "Site doesn't have a title (text/html; charset=UTF-8)."),
                ("http-server-header", "Apache/2.0.52 (CentOS)"),
            ]),
            port(111, "rpcbind", extrainfo="2 (RPC #100000)"),
            port(443, "https"),
            port(631, "ipp", "CUPS", "1.1", scripts=[
                ("http-title", "403 Forbidden"),
                ("http-server-header", "CUPS/1.1"),
            ]),
            port(3306, "mysql", "MySQL"),
        ],
    },
    "photographer": {
        "host": "192.168.173.76",
        "ports": [
            port(22, "ssh", "OpenSSH", "7.2p2 Ubuntu 4ubuntu2.10"),
            port(80, "http", "Apache httpd", "2.4.18", extrainfo="Ubuntu", scripts=[
                ("http-title", "Photographer by v1n1v131r4"),
                ("http-server-header", "Apache/2.4.18 (Ubuntu)"),
            ]),
            port(139, "netbios-ssn", "Samba smbd", "3.X - 4.X", extrainfo="workgroup: WORKGROUP"),
            port(445, "microsoft-ds", "Samba smbd", "4.3.11-Ubuntu", extrainfo="workgroup: WORKGROUP"),
            port(8000, "http", "Apache httpd", "2.4.18", extrainfo="Ubuntu", scripts=[
                ("http-generator", "Koken 0.22.24"),
                ("http-server-header", "Apache/2.4.18 (Ubuntu)"),
                ("http-title", "daisa ahomi"),
            ]),
        ],
    },
    "cronos": {
        "host": "10.10.10.13",
        "ports": [
            port(22, "ssh", "OpenSSH", "7.2p2 Ubuntu 4ubuntu2.1"),
            port(53, "domain", "ISC BIND", "9.10.3-P4", extrainfo="Ubuntu Linux", scripts=[
                ("dns-nsid", "bind.version: 9.10.3-P4-Ubuntu"),
            ]),
            port(80, "http", "Apache httpd", "2.4.18", extrainfo="Ubuntu", scripts=[
                ("http-server-header", "Apache/2.4.18 (Ubuntu)"),
                ("http-title", "Apache2 Ubuntu Default Page: It works"),
            ]),
        ],
    },
    "celestial": {
        "host": "10.10.10.85",
        "ports": [
            port(3000, "http", "Node.js Express framework", scripts=[
                ("http-title", "Site doesn't have a title (text/html; charset=utf-8)."),
            ]),
        ],
    },
    "networked": {
        "host": "10.10.10.146",
        "ports": [
            port(22, "ssh", "OpenSSH", "7.4"),
            port(80, "http", "Apache httpd", "2.4.6", extrainfo="CentOS PHP/5.4.16", scripts=[
                ("http-server-header", "Apache/2.4.6 (CentOS) PHP/5.4.16"),
                ("http-title", "Site doesn't have a title (text/html; charset=UTF-8)."),
            ]),
        ],
    },
    "broker": {
        "host": "10.10.11.243",
        "ports": [
            port(22, "ssh", "OpenSSH", "8.9p1 Ubuntu 3ubuntu0.4"),
            port(80, "http", "nginx", "1.18.0", extrainfo="Ubuntu", scripts=[
                ("http-title", "Error 401 Unauthorized"),
                ("http-server-header", "nginx/1.18.0 (Ubuntu)"),
            ]),
            port(1883, "mqtt"),
            port(5672, "amqp"),
            port(8161, "http", "Jetty", "9.4.39.v20210325", scripts=[
                ("http-title", "Error 401 Unauthorized"),
                ("http-server-header", "Jetty(9.4.39.v20210325)"),
            ]),
            port(61616, "apachemq", "ActiveMQ OpenWire transport"),
        ],
    },
    "sau": {
        "host": "10.10.11.224",
        "ports": [
            port(22, "ssh", "OpenSSH", "8.2p1 Ubuntu 4ubuntu0.7"),
            port(55555, "unknown", scripts=[
                ("fingerprint-strings", "invalid basket name; the name does not match pattern: ^[wd-_.]{1,250}$"),
            ]),
        ],
    },
    "fristileaks": {
        "host": "192.168.117.135",
        "ports": [
            port(80, "http", "Apache httpd", "2.2.15", extrainfo="CentOS DAV/2 PHP/5.3.3", scripts=[
                ("http-robots.txt", "3 disallowed entries\n/cola /sisi /beer"),
            ]),
        ],
        "gobuster": [
            "/fristi                (Status: 301) [Size: 0]",
            "/cola                  (Status: 301) [Size: 0]",
        ],
    },
    "friendzone": {
        "host": "10.10.10.123",
        "ports": [
            port(21, "ftp", "vsftpd", "3.0.3"),
            port(22, "ssh", "OpenSSH", "7.6p1 Ubuntu 4"),
            port(53, "domain", "ISC BIND", "9.11.3-1ubuntu1.2", scripts=[
                ("dns-nsid", "bind.version: 9.11.3-1ubuntu1.2-Ubuntu"),
            ]),
            port(80, "http", "Apache httpd", "2.4.29", extrainfo="Ubuntu", scripts=[
                ("http-server-header", "Apache/2.4.29 (Ubuntu)"),
                ("http-title", "Friend Zone Escape software"),
            ]),
            port(139, "netbios-ssn", "Samba smbd", "3.X - 4.X", extrainfo="workgroup: WORKGROUP"),
            port(443, "https", "Apache httpd", "2.4.29", scripts=[
                ("http-title", "404 Not Found"),
            ]),
            port(445, "netbios-ssn", "Samba smbd", "4.7.6-Ubuntu", extrainfo="workgroup: WORKGROUP", scripts=[
                ("smb-enum-shares", "Development  Path: C:\\etc\\Development  Anonymous access: READ/WRITE"),
            ]),
        ],
    },
    "access": {
        "host": "10.10.10.98",
        "ports": [
            # 0xdf: -sC did not print ftp-anon; writeup confirmed 331 Anonymous access allowed.
            port(21, "ftp", "Microsoft ftpd", scripts=[
                ("ftp-anon", "Anonymous FTP login allowed (FTP code 230)"),
            ]),
            port(23, "telnet"),
            port(80, "http", "Microsoft IIS httpd", "7.5"),
        ],
    },
    "bounty": {
        "host": "10.10.10.93",
        "ports": [
            port(80, "http", "Microsoft IIS httpd", "7.5", scripts=[
                ("http-server-header", "Microsoft-IIS/7.5"),
                ("http-title", "Bounty"),
                ("http-methods", "Potentially risky methods: TRACE"),
            ]),
        ],
        "gobuster": [
            "/transfer.aspx         (Status: 200) [Size: 0]",
            "/uploadedFiles         (Status: 301) [Size: 0]",
        ],
    },
    "servmon": {
        "host": "10.10.10.184",
        "ports": [
            port(21, "ftp", "Microsoft ftpd", scripts=[
                ("ftp-anon", "Anonymous FTP login allowed (FTP code 230)\nUsers"),
            ]),
            port(22, "ssh", "OpenSSH", "for_Windows_7.7"),
            port(80, "http", scripts=[
                ("http-title", "Site doesn't have a title (text/html)."),
            ]),
            port(135, "msrpc", "Microsoft Windows RPC"),
            port(139, "netbios-ssn", "Microsoft Windows netbios-ssn"),
            port(445, "microsoft-ds"),
            port(8443, "https", scripts=[
                ("http-title", "NSClient++"),
            ]),
        ],
    },
    "tabby": {
        "host": "10.10.10.194",
        "ports": [
            port(22, "ssh", "OpenSSH", "8.2p1 Ubuntu 4"),
            port(80, "http", "Apache httpd", "2.4.41", extrainfo="Ubuntu", scripts=[
                ("http-title", "Mega Hosting"),
            ]),
            port(8080, "http", "Apache Tomcat", scripts=[
                ("http-title", "Apache Tomcat"),
            ]),
        ],
    },
    "delivery": {
        "host": "10.10.10.222",
        "ports": [
            port(22, "ssh", "OpenSSH", "7.9p1 Debian 10+deb10u2"),
            port(80, "http", "nginx", "1.14.2", scripts=[
                ("http-server-header", "nginx/1.14.2"),
                ("http-title", "Welcome"),
            ]),
            # nmap leaves :8065 unknown; HTML title Mattermost is from the writeup fingerprint.
            port(8065, "http", scripts=[
                ("http-title", "Mattermost"),
            ]),
        ],
    },
    "doctor": {
        "host": "10.10.10.209",
        "ports": [
            port(22, "ssh", "OpenSSH", "8.2p1 Ubuntu 4ubuntu0.1"),
            port(80, "http", "Apache httpd", "2.4.41", extrainfo="Ubuntu", scripts=[
                ("http-title", "Doctor"),
            ]),
            port(8089, "https", "Splunkd httpd", scripts=[
                ("http-server-header", "Splunkd"),
                ("http-title", "splunkd"),
                ("http-robots.txt", "1 disallowed entry\n/"),
            ]),
        ],
    },
    "help": {
        "host": "10.10.10.121",
        "ports": [
            port(22, "ssh", "OpenSSH", "7.2p2 Ubuntu 4ubuntu2.6"),
            port(80, "http", "Apache httpd", "2.4.18", extrainfo="Ubuntu", scripts=[
                ("http-title", "Apache2 Ubuntu Default Page: It works"),
            ]),
            port(3000, "http", "Node.js Express framework", scripts=[
                ("http-title", "Site doesn't have a title (application/json; charset=utf-8)."),
            ]),
        ],
    },
    "poison": {
        "host": "10.10.10.84",
        "ports": [
            port(22, "ssh", "OpenSSH", "7.2", extrainfo="FreeBSD 20161230"),
            port(80, "http", "Apache httpd", "2.4.29", extrainfo="FreeBSD PHP/5.6.32", scripts=[
                ("http-server-header", "Apache/2.4.29 (FreeBSD) PHP/5.6.32"),
                ("http-title", "Site doesn't have a title (text/html; charset=UTF-8)."),
            ]),
        ],
    },
    "haircut": {
        "host": "10.10.10.24",
        "ports": [
            port(22, "ssh", "OpenSSH", "7.2p2 Ubuntu 4ubuntu2.2"),
            port(80, "http", "nginx", "1.10.0", extrainfo="Ubuntu", scripts=[
                ("http-server-header", "nginx/1.10.0 (Ubuntu)"),
                ("http-title", " HTB Hairdresser"),
            ]),
        ],
        "gobuster": [
            "/uploads               (Status: 301) [Size: 0]",
            "/exposed.php           (Status: 200) [Size: 0]",
        ],
    },
    "blunder": {
        "host": "10.10.10.191",
        "ports": [
            port(80, "http", "Apache httpd", "2.4.41", extrainfo="Ubuntu", scripts=[
                ("http-generator", "Blunder"),
                ("http-title", "Blunder | A blunder of interesting facts"),
            ]),
        ],
        "gobuster": [
            "/about                 (Status: 200) [Size: 0]",
            "/admin                 (Status: 301) [Size: 0]",
            "/robots.txt            (Status: 200) [Size: 0]",
            "/todo.txt              (Status: 200) [Size: 0]",
        ],
    },
    "admirer": {
        "host": "10.10.10.187",
        "ports": [
            port(21, "ftp", "vsftpd", "3.0.3"),
            port(22, "ssh", "OpenSSH", "7.4p1 Debian 10+deb9u7"),
            port(80, "http", "Apache httpd", "2.4.25", extrainfo="Debian", scripts=[
                ("http-robots.txt", "1 disallowed entry\n/admin-dir"),
                ("http-title", "Admirer"),
            ]),
        ],
        "gobuster": [
            "/index.php             (Status: 200) [Size: 0]",
            "/assets                (Status: 301) [Size: 0]",
            "/images                (Status: 301) [Size: 0]",
        ],
    },
    "mango": {
        "host": "10.10.10.162",
        "ports": [
            port(22, "ssh", "OpenSSH", "7.6p1 Ubuntu 4ubuntu0.3"),
            port(80, "http", "Apache httpd", "2.4.29", extrainfo="Ubuntu", scripts=[
                ("http-title", "403 Forbidden"),
            ]),
            port(443, "https", "Apache httpd", "2.4.29", extrainfo="Ubuntu", scripts=[
                ("http-title", "Mango | Search Base"),
            ]),
        ],
    },
    "magic": {
        "host": "10.10.10.185",
        "ports": [
            port(22, "ssh", "OpenSSH", "7.6p1 Ubuntu 4ubuntu0.3"),
            port(80, "http", "Apache httpd", "2.4.29", extrainfo="Ubuntu", scripts=[
                ("http-title", "Magic Portfolio"),
            ]),
        ],
    },
    "node": {
        "host": "10.10.10.58",
        "ports": [
            port(22, "ssh", "OpenSSH", "7.2p2 Ubuntu 4ubuntu2.2"),
            # -sV (without -sC) IDs Express; -sC falsely IDs Hadoop. Use the -sV product.
            port(3000, "http", "Node.js Express framework", scripts=[
                ("http-title", "MyPlace"),
            ]),
        ],
    },
    "swagshop": {
        "host": "10.10.10.140",
        "ports": [
            port(22, "ssh", "OpenSSH", "7.2p2 Ubuntu 4ubuntu2.8"),
            port(80, "http", "Apache httpd", "2.4.18", extrainfo="Ubuntu", scripts=[
                ("http-title", "Home page"),
            ]),
        ],
        "gobuster": [
            "/index.php             (Status: 200) [Size: 0]",
            "/media                 (Status: 301) [Size: 0]",
            "/downloader            (Status: 301) [Size: 0]",
            "/mage                  (Status: 200) [Size: 0]",
        ],
    },
    "jarvis": {
        "host": "10.10.10.143",
        "ports": [
            port(22, "ssh", "OpenSSH", "7.4p1 Debian 10+deb9u6"),
            port(80, "http", "Apache httpd", "2.4.25", extrainfo="Debian", scripts=[
                ("http-title", "Stark Hotel"),
            ]),
            port(64999, "http", "Apache httpd", "2.4.25", extrainfo="Debian", scripts=[
                ("http-title", "Site doesn't have a title (text/html)."),
            ]),
        ],
    },
    "writeup": {
        "host": "10.10.10.138",
        "ports": [
            port(22, "ssh", "OpenSSH", "7.4p1 Debian 10+deb9u6"),
            port(80, "http", "Apache httpd", "2.4.25", extrainfo="Debian", scripts=[
                ("http-robots.txt", "1 disallowed entry\n/writeup/"),
                ("http-title", "Nothing here yet."),
            ]),
        ],
        "gobuster": [
            "/writeup               (Status: 301) [Size: 0]",
        ],
    },
    "popcorn": {
        "host": "10.10.10.6",
        "ports": [
            port(22, "ssh", "OpenSSH", "5.1p1 Debian 6ubuntu2"),
            port(80, "http", "Apache httpd", "2.2.12", extrainfo="Ubuntu", scripts=[
                ("http-title", "Site doesn't have a title (text/html)."),
            ]),
        ],
        "gobuster": [
            "/test                  (Status: 301) [Size: 0]",
            "/torrent               (Status: 301) [Size: 0]",
            "/rename                (Status: 301) [Size: 0]",
        ],
    },
    "nineveh": {
        "host": "10.10.10.43",
        "ports": [
            port(80, "http", "Apache httpd", "2.4.18", extrainfo="Ubuntu", scripts=[
                ("http-title", "Site doesn't have a title (text/html)."),
            ]),
            port(443, "https", "Apache httpd", "2.4.18", extrainfo="Ubuntu"),
        ],
        "gobuster": [
            "/info.php              (Status: 200) [Size: 0]",
            "/department            (Status: 301) [Size: 0]",
            "/db                    (Status: 301) [Size: 0]",
            "/secure_notes          (Status: 301) [Size: 0]",
        ],
    },
    "mrrobot": {
        "host": "10.10.198.171",
        "ports": [
            port(80, "http", "Apache httpd", scripts=[
                ("http-server-header", "Apache"),
                ("http-title", "Site doesn't have a title"),
            ]),
            port(443, "https", "Apache httpd"),
        ],
        "gobuster": [
            "/wp-login.php          (Status: 200) [Size: 0]",
            "/wordpress             (Status: 301) [Size: 0]",
            "/blog                  (Status: 301) [Size: 0]",
        ],
    },
    "wgel": {
        "host": "10.201.13.212",
        "ports": [
            port(22, "ssh", "OpenSSH", "7.2p2 Ubuntu 4ubuntu2.8"),
            port(80, "http", "Apache httpd", "2.4.18", extrainfo="Ubuntu", scripts=[
                ("http-title", "Apache2 Ubuntu Default Page: It works"),
                ("http-server-header", "Apache/2.4.18 (Ubuntu)"),
            ]),
        ],
        "gobuster": [
            "/sitemap               (Status: 301) [Size: 0]",
        ],
    },
    "brooklynninenine": {
        "host": "10.10.127.175",
        "ports": [
            port(21, "ftp", "vsftpd", "3.0.3", scripts=[
                ("ftp-anon", "Anonymous FTP login allowed (FTP code 230)\nnote_to_jake.txt"),
            ]),
            port(22, "ssh", "OpenSSH", "7.6p1 Ubuntu 4ubuntu0.3"),
            port(80, "http", "Apache httpd", "2.4.29", extrainfo="Ubuntu", scripts=[
                ("http-title", "Site doesn't have a title (text/html)."),
            ]),
        ],
    },
    "easypeasy": {
        "host": "10.10.152.0",
        "ports": [
            port(80, "http", "nginx", "1.16.1", scripts=[
                ("http-server-header", "nginx/1.16.1"),
                ("http-title", "Welcome to nginx!"),
                ("http-robots.txt", "1 disallowed entry\n/"),
            ]),
            port(6498, "ssh", "OpenSSH", "7.6p1 Ubuntu 4ubuntu0.3"),
            port(65524, "http", "Apache httpd", "2.4.43", extrainfo="Ubuntu", scripts=[
                ("http-robots.txt", "1 disallowed entry\n/"),
                ("http-title", "Apache2 Debian Default Page: It works"),
            ]),
        ],
        "gobuster": [
            "/n0th1ng3ls3m4tt3r     (Status: 301) [Size: 0]",
        ],
    },
    "gamingserver": {
        "host": "10.10.100.235",
        "ports": [
            port(22, "ssh", "OpenSSH", "7.6p1 Ubuntu 4ubuntu0.3"),
            port(80, "http", "Apache httpd", "2.4.29", extrainfo="Ubuntu", scripts=[
                ("http-title", "House of danak"),
            ]),
        ],
        "gobuster": [
            "/uploads               (Status: 301) [Size: 0]",
            "/secret                (Status: 301) [Size: 0]",
        ],
    },
    "ultratech": {
        "host": "10.10.40.147",
        "ports": [
            port(21, "ftp", "vsftpd", "3.0.3"),
            port(22, "ssh", "OpenSSH", "7.6p1 Ubuntu 4ubuntu0.3"),
            port(8081, "http", "Node.js Express framework"),
            port(31331, "http", "Apache httpd", "2.4.29", extrainfo="Ubuntu", scripts=[
                ("http-title", "UltraTech"),
            ]),
        ],
        "gobuster": [
            "/auth                  (Status: 200) [Size: 0]",
            "/ping                  (Status: 200) [Size: 0]",
        ],
    },
    "kioptrix3": {
        "host": "192.168.1.15",
        "ports": [
            port(22, "ssh", "OpenSSH", "4.7p1 Debian 8ubuntu1.2"),
            port(80, "http", "Apache httpd", "2.2.8", extrainfo="Ubuntu PHP/5.2.4-2ubuntu5.6 with Suhosin-Patch", scripts=[
                ("http-title", "Ligoat Security - Got Goat? Security ..."),
                ("http-server-header", "Apache/2.2.8 (Ubuntu) PHP/5.2.4-2ubuntu5.6 with Suhosin-Patch"),
            ]),
        ],
        "gobuster": [
            "/phpmyadmin            (Status: 301) [Size: 0]",
        ],
    },
    "kioptrix4": {
        "host": "192.168.1.14",
        "ports": [
            port(22, "ssh", "OpenSSH", "4.7p1 Debian 8ubuntu1.2"),
            port(80, "http", "Apache httpd", "2.2.8", extrainfo="Ubuntu PHP/5.2.4-2ubuntu5.6 with Suhosin-Patch", scripts=[
                ("http-title", "Site doesn't have a title (text/html)."),
            ]),
            port(139, "netbios-ssn", "Samba smbd", "3.X - 4.X", extrainfo="workgroup: WORKGROUP"),
            port(445, "netbios-ssn", "Samba smbd", "3.0.28a", extrainfo="workgroup: WORKGROUP"),
        ],
    },
    "dc2": {
        "host": "192.168.178.22",
        "ports": [
            port(80, "http", "Apache httpd", "2.4.10", extrainfo="Debian"),
            port(7744, "ssh", "OpenSSH", "6.7p1 Debian 5+deb8u7"),
        ],
    },
    "dc4": {
        "host": "192.168.1.226",
        "ports": [
            port(22, "ssh", "OpenSSH", "7.4p1 Debian 10+deb9u6"),
            port(80, "http", "nginx", "1.15.10", scripts=[
                ("http-server-header", "nginx/1.15.10"),
                ("http-title", "System Tools"),
            ]),
        ],
    },
    "sickos12": {
        "host": "192.168.2.4",
        "ports": [
            port(22, "ssh", "OpenSSH", "5.9p1 Debian 5ubuntu1.8"),
            port(80, "http", "lighttpd", "1.4.28", scripts=[
                ("http-server-header", "lighttpd/1.4.28"),
                ("http-title", "Site doesn't have a title (text/html)."),
                ("http-methods", "Potentially risky methods: PROPFIND DELETE MKCOL PUT MOVE COPY PROPPATCH LOCK UNLOCK"),
            ]),
        ],
        "gobuster": [
            "/test                  (Status: 301) [Size: 0]",
        ],
    },
    "basicpentesting1": {
        "host": "192.168.40.100",
        "ports": [
            port(21, "ftp", "ProFTPD", "1.3.3c"),
            port(22, "ssh", "OpenSSH", "7.2p2 Ubuntu 4ubuntu2.2"),
            port(80, "http", "Apache httpd", "2.4.18", extrainfo="Ubuntu"),
        ],
        "gobuster": [
            "/secret                (Status: 301) [Size: 0]",
        ],
    },
    "earth": {
        "host": "10.0.2.5",
        "ports": [
            port(22, "ssh", "OpenSSH", "8.6"),
            port(80, "http", "Apache httpd", "2.4.51", extrainfo="Fedora OpenSSL/1.1.1l mod_wsgi/4.7.1 Python/3.9", scripts=[
                ("http-title", "Bad Request (400)"),
            ]),
            port(443, "https", "Apache httpd", "2.4.51", extrainfo="Fedora OpenSSL/1.1.1l mod_wsgi/4.7.1 Python/3.9"),
        ],
    },
    "pwnlab": {
        "host": "10.183.0.223",
        "ports": [
            port(80, "http", "Apache httpd", "2.4.10", extrainfo="Debian", scripts=[
                ("http-server-header", "Apache/2.4.10 (Debian)"),
            ]),
            port(111, "rpcbind"),
            port(3306, "mysql", "MySQL", "5.5.47-0+deb8u1"),
        ],
        "gobuster": [
            "/login.php             (Status: 200) [Size: 0]",
        ],
    },
    # --- batch 3: 10 Linux + 10 Windows (coverage-sim-batch3) ---
    "cap": {
        "host": "10.10.10.245",
        "ports": [
            port(21, "ftp", "vsftpd", "3.0.3"),
            port(22, "ssh", "OpenSSH", "8.2p1 Ubuntu 4ubuntu0.1"),
            port(80, "http", "gunicorn", scripts=[
                ("http-title", "Security Dashboard"),
            ]),
        ],
        "gobuster": [
            "/ip                    (Status: 200) [Size: 0]",
            "/capture               (Status: 302) [Size: 0]",
            "/data                  (Status: 302) [Size: 0]",
        ],
    },
    "haystack": {
        "host": "10.10.10.115",
        "ports": [
            port(22, "ssh", "OpenSSH", "7.4"),
            port(80, "http", "nginx", "1.12.2", scripts=[
                ("http-server-header", "nginx/1.12.2"),
                ("http-title", "Site doesn't have a title (text/html)."),
            ]),
            # nmap fingerprints nginx; body is Elasticsearch JSON API (0xdf).
            port(9200, "http", "nginx", "1.12.2", scripts=[
                ("http-server-header", "nginx/1.12.2"),
                ("http-methods", "Potentially risky methods: DELETE"),
                ("http-title", "Site doesn't have a title (application/json; charset=UTF-8)."),
            ]),
        ],
    },
    "luanne": {
        "host": "10.10.10.218",
        "ports": [
            port(22, "ssh", "OpenSSH", "8.0", extrainfo="NetBSD 20190418-hpn13v14-lpk"),
            port(80, "http", "nginx", "1.19.0", scripts=[
                ("http-server-header", "nginx/1.19.0"),
                ("http-title", "401 Unauthorized"),
                ("http-robots.txt", "1 disallowed entry\n/weather"),
            ]),
            port(9001, "http", "Medusa httpd", "1.12", extrainfo="Supervisor process manager", scripts=[
                ("http-server-header", "Medusa/1.12"),
                ("http-title", "Error response"),
            ]),
        ],
        "gobuster": [
            "/weather               (Status: 200) [Size: 0]",
        ],
    },
    "hawk": {
        "host": "10.10.10.102",
        "ports": [
            port(21, "ftp", "vsftpd", "3.0.3", scripts=[
                ("ftp-anon", "Anonymous FTP login allowed (FTP code 230)"),
            ]),
            port(22, "ssh", "OpenSSH", "7.6p1 Ubuntu 4"),
            port(80, "http", "Apache httpd", "2.4.29", extrainfo="Ubuntu", scripts=[
                ("http-generator", "Drupal 7 (http://drupal.org)"),
                ("http-server-header", "Apache/2.4.29 (Ubuntu)"),
                ("http-title", "Welcome to 192.168.56.103 | 192.168.56.103"),
            ]),
            port(5435, "tcpwrapped"),
            port(8082, "http", "H2 database http console", scripts=[
                ("http-title", "H2 Console"),
            ]),
            port(9092, "XmlIpcRegSvc"),
        ],
    },
    "seal": {
        "host": "10.10.10.250",
        "ports": [
            port(22, "ssh", "OpenSSH", "8.2p1 Ubuntu 4ubuntu0.2"),
            port(443, "https", "nginx", "1.18.0", extrainfo="Ubuntu", scripts=[
                ("http-server-header", "nginx/1.18.0 (Ubuntu)"),
                ("http-title", "Seal Market"),
            ]),
            port(8080, "http-proxy", scripts=[
                ("http-title", "Site doesn't have a title (text/html;charset=utf-8)."),
            ]),
        ],
        "gobuster": [
            "/manager               (Status: 302) [Size: 0]",
            "/git                   (Status: 301) [Size: 0]",
        ],
    },
    "spectra": {
        "host": "10.10.10.229",
        "ports": [
            port(22, "ssh", "OpenSSH", "8.1"),
            port(80, "http", "nginx", "1.17.4", scripts=[
                ("http-server-header", "nginx/1.17.4"),
                ("http-title", "Site doesn't have a title (text/html)."),
            ]),
            port(3306, "mysql", "MySQL", extrainfo="unauthorized"),
        ],
        # 0xdf: /main is WordPress; directory listing shows wp-config.php.save
        "gobuster": [
            "/main                  (Status: 301) [Size: 0]",
            "/main/wp-login.php     (Status: 200) [Size: 0]",
            "/main/wp-config.php.save (Status: 200) [Size: 0]",
        ],
    },
    "goodgames": {
        "host": "10.10.11.130",
        "ports": [
            port(80, "http", "Werkzeug httpd", "2.0.2", extrainfo="Python 3.9.2", scripts=[
                ("http-server-header", "Werkzeug/2.0.2 Python/3.9.2"),
                ("http-title", "GoodGames | Community and Store"),
            ]),
        ],
        "gobuster": [
            "/login                 (Status: 200) [Size: 0]",
            "/signup                (Status: 200) [Size: 0]",
            "/blog                  (Status: 200) [Size: 0]",
            "/profile               (Status: 200) [Size: 0]",
        ],
    },
    "paper": {
        "host": "10.10.11.143",
        "ports": [
            port(22, "ssh", "OpenSSH", "8.0"),
            port(80, "http", "Apache httpd", "2.4.37", extrainfo="centos OpenSSL/1.1.1k mod_fcgid/2.3.9", scripts=[
                ("http-title", "HTTP Server Test Page powered by CentOS"),
            ]),
            port(443, "https", "Apache httpd", "2.4.37", extrainfo="centos OpenSSL/1.1.1k mod_fcgid/2.3.9", scripts=[
                ("http-title", "HTTP Server Test Page powered by CentOS"),
            ]),
        ],
        # Host office.paper reveals WordPress 5.2.3 (0xdf); attested path.
        "gobuster": [
            "/wordpress             (Status: 301) [Size: 0]",
            "/wp-login.php          (Status: 200) [Size: 0]",
        ],
    },
    "previse": {
        "host": "10.10.11.104",
        "ports": [
            port(22, "ssh", "OpenSSH", "7.6p1 Ubuntu 4ubuntu0.3"),
            port(80, "http", "Apache httpd", "2.4.29", extrainfo="Ubuntu", scripts=[
                ("http-server-header", "Apache/2.4.29 (Ubuntu)"),
                ("http-title", "Previse Login"),
            ]),
        ],
        "gobuster": [
            "/login.php             (Status: 200) [Size: 0]",
            "/accounts.php          (Status: 200) [Size: 0]",
            "/files.php             (Status: 200) [Size: 0]",
            "/file_logs.php         (Status: 200) [Size: 0]",
            "/download.php          (Status: 200) [Size: 0]",
        ],
    },
    "pandora": {
        "host": "10.10.11.136",
        "ports": [
            port(22, "ssh", "OpenSSH", "8.2p1 Ubuntu 4ubuntu0.3"),
            port(80, "http", "Apache httpd", "2.4.41", extrainfo="Ubuntu", scripts=[
                ("http-title", "Play | Landing"),
            ]),
        ],
        # Pandora FMS is localhost-only after SSH (0xdf) — do not invent a
        # public /pandora_console gobuster hit. SNMP UDP 161 is the
        # foothold path and is outside the TCP nmap fixture.
    },
    "bastion": {
        "host": "10.10.10.134",
        "ports": [
            port(22, "ssh", "OpenSSH", "for_Windows_7.9"),
            port(135, "msrpc", "Microsoft Windows RPC"),
            port(139, "netbios-ssn", "Microsoft Windows netbios-ssn"),
            port(445, "microsoft-ds", "Windows Server 2016 Standard 14393 microsoft-ds", scripts=[
                ("smb-os-discovery", "OS: Windows Server 2016 Standard 14393\nComputer name: Bastion"),
            ]),
        ],
    },
    "love": {
        "host": "10.10.10.239",
        "ports": [
            port(80, "http", "Apache httpd", "2.4.46", extrainfo="Win64 OpenSSL/1.1.1j PHP/7.3.27", scripts=[
                ("http-server-header", "Apache/2.4.46 (Win64) OpenSSL/1.1.1j PHP/7.3.27"),
                ("http-title", "Voting System using PHP"),
            ]),
            port(135, "msrpc", "Microsoft Windows RPC"),
            port(139, "netbios-ssn", "Microsoft Windows netbios-ssn"),
            port(443, "https", "Apache httpd", "2.4.46", extrainfo="OpenSSL/1.1.1j PHP/7.3.27", scripts=[
                ("http-title", "403 Forbidden"),
            ]),
            port(445, "microsoft-ds", "Microsoft Windows 7 - 10 microsoft-ds", extrainfo="workgroup: WORKGROUP"),
            port(3306, "mysql"),
            port(5000, "http", "Apache httpd", "2.4.46", extrainfo="OpenSSL/1.1.1j PHP/7.3.27", scripts=[
                ("http-title", "403 Forbidden"),
            ]),
            port(5985, "http", "Microsoft HTTPAPI httpd", "2.0", extrainfo="SSDP/UPnP"),
        ],
    },
    "driver": {
        "host": "10.10.11.106",
        "ports": [
            port(80, "http", "Microsoft IIS httpd", "10.0", scripts=[
                ("http-auth", "HTTP/1.1 401 Unauthorized\nBasic realm=MFP Firmware Update Center. Please enter password for admin"),
                ("http-server-header", "Microsoft-IIS/10.0"),
                ("http-title", "Site doesn't have a title (text/html; charset=UTF-8)."),
            ]),
            port(135, "msrpc", "Microsoft Windows RPC"),
            port(445, "microsoft-ds", "Microsoft Windows 7 - 10 microsoft-ds", extrainfo="workgroup: WORKGROUP"),
            port(5985, "http", "Microsoft HTTPAPI httpd", "2.0", extrainfo="SSDP/UPnP"),
        ],
    },
    "heist": {
        "host": "10.10.10.149",
        "ports": [
            port(80, "http", "Microsoft IIS httpd", "10.0", scripts=[
                ("http-server-header", "Microsoft-IIS/10.0"),
                ("http-title", "Support Login Page"),
            ]),
            port(135, "msrpc", "Microsoft Windows RPC"),
            port(445, "microsoft-ds"),
            port(5985, "http", "Microsoft HTTPAPI httpd", "2.0", extrainfo="SSDP/UPnP"),
        ],
        "gobuster": [
            "/attachments           (Status: 301) [Size: 0]",
            "/login.php             (Status: 200) [Size: 0]",
        ],
    },
    "sniper": {
        "host": "10.10.10.151",
        "ports": [
            port(80, "http", "Microsoft IIS httpd", "10.0", scripts=[
                ("http-server-header", "Microsoft-IIS/10.0"),
                ("http-title", "Sniper Co."),
            ]),
            port(135, "msrpc", "Microsoft Windows RPC"),
            port(139, "netbios-ssn", "Microsoft Windows netbios-ssn"),
            port(445, "microsoft-ds"),
        ],
        "gobuster": [
            "/blog                  (Status: 301) [Size: 0]",
            "/user                  (Status: 301) [Size: 0]",
        ],
    },
    "omni": {
        "host": "10.10.10.204",
        "ports": [
            port(135, "msrpc", "Microsoft Windows RPC"),
            port(5985, "upnp", "Microsoft IIS httpd"),
            port(8080, "upnp", "Microsoft IIS httpd", scripts=[
                ("http-auth", "HTTP/1.1 401 Unauthorized\nBasic realm=Windows Device Portal"),
                ("http-server-header", "Microsoft-HTTPAPI/2.0"),
                ("http-title", "Site doesn't have a title."),
            ]),
            port(29817, "unknown"),
            port(29819, "arcserve", "ARCserve Discovery"),
            port(29820, "unknown"),
        ],
    },
    "nest": {
        "host": "10.10.10.178",
        "ports": [
            port(445, "microsoft-ds"),
            port(4386, "unknown", scripts=[
                ("fingerprint-strings", "Reporting Service V1.2\nUnrecognised command"),
            ]),
        ],
    },
    # Post-IPsec TCP view (0xdf after VPN up). SNMP/IPsec prerequisite noted in scoring.
    "conceal": {
        "host": "10.10.10.116",
        "ports": [
            port(21, "ftp", "Microsoft ftpd", scripts=[
                ("ftp-anon", "Anonymous FTP login allowed (FTP code 230)"),
            ]),
            port(80, "http", "Microsoft IIS httpd", "10.0", scripts=[
                ("http-server-header", "Microsoft-IIS/10.0"),
                ("http-title", "IIS Windows"),
            ]),
            port(135, "msrpc", "Microsoft Windows RPC"),
            port(139, "netbios-ssn", "Microsoft Windows netbios-ssn"),
            port(445, "microsoft-ds"),
        ],
    },
    "fuse": {
        "host": "10.10.10.193",
        "ports": [
            port(53, "domain"),
            port(80, "http", "Microsoft IIS httpd", "10.0", scripts=[
                ("http-title", "Site doesn't have a title (text/html)."),
            ]),
            port(88, "kerberos-sec", "Microsoft Windows Kerberos"),
            port(135, "msrpc", "Microsoft Windows RPC"),
            port(139, "netbios-ssn", "Microsoft Windows netbios-ssn"),
            port(389, "ldap", "Microsoft Windows Active Directory LDAP", extrainfo="Domain: fabricorp.local"),
            port(445, "microsoft-ds", "Windows Server 2016 Standard 14393 microsoft-ds", extrainfo="workgroup: FABRICORP"),
            port(464, "kpasswd5"),
            port(593, "ncacn_http", "Microsoft Windows RPC over HTTP", "1.0"),
            port(636, "ldapssl"),
            port(3268, "ldap", "Microsoft Windows Active Directory LDAP", extrainfo="Domain: fabricorp.local"),
            port(5985, "http", "Microsoft HTTPAPI httpd", "2.0", extrainfo="SSDP/UPnP"),
        ],
        "gobuster": [
            "/papercut              (Status: 301) [Size: 0]",
        ],
    },
    "support": {
        "host": "10.10.11.174",
        "ports": [
            port(53, "domain"),
            port(88, "kerberos-sec", "Microsoft Windows Kerberos"),
            port(135, "msrpc", "Microsoft Windows RPC"),
            port(139, "netbios-ssn", "Microsoft Windows netbios-ssn"),
            port(389, "ldap", "Microsoft Windows Active Directory LDAP", extrainfo="Domain: support.htb0., Site: Default-First-Site-Name"),
            port(445, "microsoft-ds"),
            port(464, "kpasswd5"),
            port(593, "ncacn_http", "Microsoft Windows RPC over HTTP", "1.0"),
            port(636, "ldapssl"),
            port(3268, "ldap", "Microsoft Windows Active Directory LDAP", extrainfo="Domain: support.htb0."),
            port(5985, "http", "Microsoft HTTPAPI httpd", "2.0", extrainfo="SSDP/UPnP"),
            port(9389, "mc-nmf", ".NET Message Framing"),
        ],
    },
}


def write_nmap_xml(box: str, spec: dict) -> Path:
    host = spec["host"]
    ports_xml = []
    for p in spec["ports"]:
        attrs = [f'name="{escape(p["service"])}"', 'method="probed"', 'conf="10"']
        if p.get("product"):
            attrs.append(f'product="{escape(p["product"])}"')
        if p.get("version"):
            attrs.append(f'version="{escape(p["version"])}"')
        if p.get("extrainfo"):
            attrs.append(f'extrainfo="{escape(p["extrainfo"])}"')
        scripts = ""
        for sid, output in p.get("scripts") or []:
            scripts += f'\n<script id="{escape(sid)}" output="{escape(output)}"/>'
        ports_xml.append(
            f'<port protocol="tcp" portid="{p["portid"]}">\n'
            f'<state state="open" reason="syn-ack"/>\n'
            f'<service {" ".join(attrs)}/>'
            f"{scripts}\n"
            f"</port>"
        )
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<nmaprun scanner="nmap" args="nmap -sC -sV -oX scan.xml {host}" '
        'start="1" version="7.94">\n'
        '<host starttime="1" endtime="2">\n'
        '<status state="up" reason="syn-ack"/>\n'
        f'<address addr="{host}" addrtype="ipv4"/>\n'
        "<ports>\n"
        + "\n".join(ports_xml)
        + "\n</ports>\n</host>\n</nmaprun>\n"
    )
    path = FIXTURES / f"{box}.xml"
    path.write_text(xml)
    # sanity parse
    ET.parse(path)
    return path


def write_gobuster(box: str, spec: dict) -> Path | None:
    lines = spec.get("gobuster")
    if not lines:
        return None
    path = FIXTURES / f"{box}_gobuster.txt"
    path.write_text("\n".join(lines) + "\n")
    return path


def build() -> None:
    FIXTURES.mkdir(parents=True, exist_ok=True)
    for name, spec in BOXES.items():
        write_nmap_xml(name, spec)
        write_gobuster(name, spec)
        print(f"wrote {name}")


def run_cli(home: Path, args: list[str], log) -> str:
    env = os.environ.copy()
    env["HOME"] = str(home)
    env["PYTHONPATH"] = str(ROOT / "src")
    env["NO_COLOR"] = "1"
    proc = subprocess.run(
        [PY, str(CLI), *args],
        cwd=str(ROOT),
        env=env,
        capture_output=True,
        text=True,
        timeout=180,
    )
    chunk = (
        f"$ trinity {' '.join(args)}\n"
        f"{proc.stdout}"
        + (f"\n[stderr]\n{proc.stderr}" if proc.stderr else "")
        + f"\n[exit {proc.returncode}]\n"
    )
    log.write(chunk + "\n")
    log.flush()
    return chunk


def run_box(name: str) -> Path:
    spec = BOXES[name]
    home = Path(f"/tmp/trinity_sim_{name}")
    if home.exists():
        # isolated per run — wipe previous sim data for this box only
        import shutil
        shutil.rmtree(home)
    home.mkdir(parents=True)
    TRANSCRIPTS.mkdir(parents=True, exist_ok=True)
    out_path = TRANSCRIPTS / f"{name}.txt"
    xml = FIXTURES / f"{name}.xml"
    gob = FIXTURES / f"{name}_gobuster.txt"
    with out_path.open("w") as log:
        run_cli(home, ["init"], log)
        run_cli(home, ["parse-nmap", str(xml), "--box", name, "--target", spec["host"]], log)
        if gob.exists():
            run_cli(home, ["parse-nmap", str(gob), "--box", name], log)
        run_cli(home, ["next", "--box", name], log)
        run_cli(home, ["suggest", "--box", name], log)
        run_cli(home, ["hint", "--box", name], log)
    return out_path


def run_all() -> None:
    for name in BOXES:
        print(f"=== simulating {name} ===", flush=True)
        path = run_box(name)
        print(f"  transcript {path}", flush=True)


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "all"
    if cmd == "build":
        build()
    elif cmd == "run":
        names = sys.argv[2:] or list(BOXES)
        build()
        for name in names:
            print(f"=== simulating {name} ===", flush=True)
            print(f"  transcript {run_box(name)}", flush=True)
    elif cmd == "all":
        build()
        run_all()
    else:
        sys.exit("usage: coverage_sim.py [build|run [box...]|all]")

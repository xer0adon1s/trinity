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
PY = "/home/alexander/Work/trinity/.venv/bin/python"
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
        sys.exit(f"usage: coverage_sim.py [build|run [box...]|all]")

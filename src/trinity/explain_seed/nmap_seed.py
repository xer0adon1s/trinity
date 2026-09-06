"""Pre-authored ELI5 explanations for nmap commands and flags — the most
common invocations across the recon phase of a CTF/HTB box. Each entry
maps an exact normalized command string to a plain-language explanation.
"""
from __future__ import annotations

ENTRIES: dict[str, str] = {
    "nmap -sC -sV <target>": (
        "This is the classic 'first scan' on any box. -sC runs nmap's "
        "default set of safe scripts against whatever ports it finds "
        "open (things like grabbing banners, checking for anonymous FTP, "
        "listing SMB shares). -sV probes each open port to figure out "
        "exactly what software and version is running there (e.g. "
        "'Apache httpd 2.4.41' instead of just 'port 80 is open'). "
        "Together, this single command tells you what's open, what's "
        "running on it, and surfaces some obvious low-hanging fruit, all "
        "in one pass."
    ),
    "nmap -p- <target>": (
        "-p- tells nmap to scan all 65,535 possible TCP ports instead of "
        "its default top-1000 most common ones. It's slower, but "
        "catches services running on unusual ports that a quick scan "
        "would miss — CTF boxes sometimes deliberately hide a service on "
        "an odd port number to make you look harder."
    ),
    "nmap -p- --min-rate 5000 <target>": (
        "Same full-port scan as -p-, but --min-rate 5000 tells nmap to "
        "fire at least 5000 packets per second instead of pacing itself "
        "conservatively. This trades some stealth/accuracy for a much "
        "faster full scan — common on CTF/lab targets where you're not "
        "worried about tripping an IDS."
    ),
    "nmap -sU <target>": (
        "-sU switches nmap to scan UDP ports instead of the default TCP. "
        "UDP scanning is much slower and less reliable (UDP has no "
        "handshake to confirm a port is open), but some services — DNS, "
        "SNMP, TFTP — only run on UDP, so it's worth a dedicated pass if "
        "TCP alone doesn't turn up a way in."
    ),
    "nmap -A <target>": (
        "-A is a bundle flag: it turns on OS detection, version "
        "detection (-sV), default script scanning (-sC), and "
        "traceroute, all at once. Convenient, but noisier and slower "
        "than picking the flags individually — many operators prefer "
        "-sC -sV so they know exactly what's running."
    ),
    "nmap -oX <output>.xml <target>": (
        "-oX writes the scan results in XML format to the given file, "
        "instead of (or as well as) printing them to the screen. XML "
        "output is the format tools like Trinity parse programmatically "
        "— always worth adding this flag so you have a machine-readable "
        "copy of every scan you run, not just what scrolled past in the "
        "terminal."
    ),
    "nmap -oA <output> <target>": (
        "-oA writes the scan results in all three of nmap's output "
        "formats at once (normal .nmap, XML .xml, and grepable .gnmap) "
        "using the given filename as a prefix. Handy so you never have "
        "to decide in advance which format you'll need later."
    ),
    "nmap --script vuln <target>": (
        "This runs nmap's whole 'vuln' script category against every "
        "open port it finds — a broad set of scripts that check for "
        "specific known CVEs and misconfigurations. It's slower and "
        "noisier than -sC's default scripts, but can surface a "
        "known vulnerability nmap's default scan wouldn't have flagged."
    ),
    "nmap -sn <target>/24": (
        "-sn is a 'ping scan' — it checks which hosts on a network "
        "range are actually up and responding, without scanning any "
        "ports on them. Useful when you're given a whole subnet and need "
        "to find which specific IP is the actual target."
    ),
    "nmap --top-ports 20 <target>": (
        "Scans only the 20 most commonly-open TCP ports (based on "
        "nmap's own statistics of what's usually open across real "
        "hosts). Much faster than a full scan — a good quick first pass "
        "before committing to a slower, more thorough scan."
    ),
}

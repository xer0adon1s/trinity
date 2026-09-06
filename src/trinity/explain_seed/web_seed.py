"""Pre-authored ELI5 explanations for web enumeration commands:
gobuster, ffuf, nikto, whatweb, and common curl recon one-liners.
"""
from __future__ import annotations

ENTRIES: dict[str, str] = {
    "gobuster dir -u <url> -w <wordlist>": (
        "gobuster's 'dir' mode brute-forces hidden directories/files on "
        "a website. -u sets the target URL, -w points to a wordlist "
        "(a big list of common folder/file names like 'admin', "
        "'backup', 'login'). gobuster tries every word in the list as a "
        "URL path and reports which ones return a real page instead of "
        "a 404 — that's how you find hidden admin panels or forgotten "
        "files a developer left exposed."
    ),
    "gobuster dir -u <url> -w <wordlist> -x php,txt,html": (
        "Same as the basic dir scan, but -x tells gobuster to also try "
        "each wordlist entry with these file extensions appended (e.g. "
        "'admin' becomes 'admin.php', 'admin.txt', 'admin.html'). Useful "
        "when you know or suspect the target is running PHP, or when "
        "you're not sure and want to cover multiple possibilities in "
        "one pass."
    ),
    "gobuster dns -d <domain> -w <wordlist>": (
        "gobuster's 'dns' mode brute-forces subdomains instead of "
        "directories. -d sets the base domain, -w is the wordlist of "
        "common subdomain names (like 'admin', 'dev', 'api'). It checks "
        "whether each guessed subdomain (e.g. 'dev.target.com') actually "
        "resolves — useful for finding hidden subdomains that host "
        "separate, possibly less-secured applications."
    ),
    "gobuster vhost -u <url> -w <wordlist>": (
        "gobuster's 'vhost' mode finds virtual hosts — different "
        "websites served by the same web server depending on what "
        "hostname you ask for in the request. Some CTF boxes hide extra "
        "content behind a vhost that isn't linked from the main site at "
        "all, only reachable if you know its name (which this brute-"
        "forces) and add it to your /etc/hosts file."
    ),
    "ffuf -u <url>/FUZZ -w <wordlist>": (
        "ffuf (Fuzz Faster U Fool) works like gobuster's dir mode but "
        "more flexibly — the literal word 'FUZZ' in the URL marks where "
        "each wordlist entry gets substituted. -u is the URL template "
        "with FUZZ in it, -w is the wordlist. It's popular because FUZZ "
        "can go anywhere in the request (URL path, headers, POST body), "
        "not just at the end of a path."
    ),
    "ffuf -u <url>?param=FUZZ -w <wordlist>": (
        "Uses ffuf to brute-force a GET parameter's value instead of a "
        "URL path — FUZZ sits inside the query string here. Useful for "
        "guessing valid IDs, usernames, or hidden parameter values a "
        "web app expects."
    ),
    "ffuf -u <url> -H 'Host: FUZZ.target.com' -w <wordlist>": (
        "This fuzzes the Host header instead of the URL — effectively "
        "ffuf's version of virtual-host discovery, same idea as "
        "gobuster's vhost mode. Sends the same request repeatedly with a "
        "different Host header value each time from the wordlist, to "
        "find vhosts the web server responds to differently."
    ),
    "nikto -h <target>": (
        "nikto is an automated web vulnerability scanner — it checks a "
        "web server against a large built-in database of known issues: "
        "outdated software versions, dangerous default files, missing "
        "security headers, common misconfigurations. -h sets the target "
        "host/URL. It's a broad, noisy scan (not stealthy at all) that's "
        "good for a quick 'anything obviously wrong here?' check."
    ),
    "nikto -h <target> -Format json -output <file>.json": (
        "Same nikto scan as usual, but -Format json plus -output tells "
        "it to write results as structured JSON to a file instead of "
        "just printing plain text. This is what lets a tool like "
        "Trinity parse nikto's findings automatically rather than you "
        "reading through scroll-back."
    ),
    "whatweb <target>": (
        "whatweb fingerprints a website — it identifies what "
        "technologies are running behind the scenes (web server "
        "software and version, CMS like WordPress, JavaScript "
        "frameworks, analytics tools) by examining response headers, "
        "cookies, and page content. Good first step to know what you're "
        "actually dealing with before choosing an attack approach."
    ),
    "whatweb -a 3 <target>": (
        "-a sets whatweb's 'aggression level' (1-4). Level 3 makes it "
        "probe more actively — following some links, trying a few extra "
        "requests — to identify technologies that a passive check "
        "(level 1, the default) might miss. Trade-off: more requests "
        "sent, more noise, but better identification."
    ),
    "curl -I <url>": (
        "-I sends a HEAD request instead of a normal GET — it asks the "
        "server for just the response headers, not the actual page "
        "content. Quick way to check a server's response headers "
        "(software version, security headers, redirects) without "
        "downloading anything."
    ),
    "curl -s <url> | grep -i <keyword>": (
        "-s runs curl 'silently' (no progress bar cluttering the "
        "output), fetching the page content and piping it into grep to "
        "search for a specific keyword. A fast way to check whether a "
        "page contains something specific — a version string, an error "
        "message, a comment left in the HTML — without opening a "
        "browser."
    ),
}

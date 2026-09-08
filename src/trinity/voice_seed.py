"""Trinity's Voice v1 -- hand-authored teaching corpus.

DESIGN: docs/TRINITY_VOICE_DESIGN.md. This is a plain-English,
phase-safe explanation for each entry in kb/seed.py's small starter
corpus, keyed by kb_entries.title (the stable join key -- see the
design doc for why kb_entries.id is NOT used).

Authoring rules, enforced by review not by code (same discipline as
hints.py's nudge field):
  - Three short paragraphs: what_it_is, why_it_happens, what_to_watch_for.
  - NEVER mention a later phase than the one this finding belongs to.
    A foothold-phase entry (this whole file, for now -- kb/seed.py has
    no privesc-CVE entries yet) never mentions privesc/root except in
    the deliberately generic, phase-agnostic "SUID binaries" entry,
    which IS the privesc phase itself and is written accordingly.
  - Voice, described not prescribed: a little dry, quietly pattern-
    spotting, like someone who has seen this exact mistake a thousand
    times and finds mild amusement in how often it recurs. Never a
    cartoon, never undercuts the teaching with a joke.
  - Every entry must be genuinely informative on its own merits -- if
    a paragraph would just restate kb_entries.summary in longer words,
    it isn't finished yet.

Add an entry here whenever a new title lands in kb/seed.py; this file
intentionally does not try to cover the full match/searchsploit
long-tail -- see the design doc's "Deferred: v2" for that.
"""
from __future__ import annotations

ENTRIES: dict[str, dict[str, str]] = {
    "vsftpd 2.3.4 backdoor (CVE-2011-2523)": {
        "what_it_is": (
            "vsftpd stands for \"very secure FTP daemon,\" which is a name "
            "this particular build spectacularly failed to live up to. "
            "Somewhere between June 30th and July 1st, 2011, someone "
            "compromised the official download server and swapped the "
            "source tarball for a trojaned copy. Anyone who compiled "
            "vsftpd 2.3.4 from that window got a hidden backdoor baked "
            "into their FTP server without knowing it."
        ),
        "why_it_happens": (
            "The backdoor triggers on a username containing a smiley face "
            "-- literally the characters \":)\" -- sent during login. When "
            "the server sees that string, it stops behaving like an FTP "
            "server and opens a raw root shell on TCP port 6200 instead. "
            "No password needed, no exploit chain, no memory corruption -- "
            "just a string comparison someone slipped into the code that "
            "quietly grants root to anyone who knows the joke. It's less "
            "a vulnerability in the traditional sense and more a practical "
            "joke with root privileges attached, which is exactly why it "
            "became a rite-of-passage teaching box: it's memorable, and it "
            "teaches you to actually read version banners instead of "
            "skimming past them."
        ),
        "what_to_watch_for": (
            "The lesson that generalizes: an exact version number on a "
            "service banner is worth a search before you do anything "
            "else. Most version-based vulnerabilities need real exploit "
            "development or a specific CVE writeup; this one is unusually "
            "generous, but the habit it teaches -- version banner first, "
            "searchsploit second, assumptions third -- applies to every "
            "service you'll ever enumerate."
        ),
    },
    "Anonymous FTP login": {
        "what_it_is": (
            "FTP has supported an \"anonymous\" account since long before "
            "modern authentication norms existed -- log in as the literal "
            "username \"anonymous\" with any password (traditionally an "
            "email address, though most servers don't check), and you're "
            "in, no real credentials required."
        ),
        "why_it_happens": (
            "This isn't a bug, it's a feature that outlived its original "
            "purpose. It exists for public file distribution -- the "
            "1980s equivalent of a public download link -- and it was "
            "genuinely useful when FTP servers hosted software mirrors "
            "and public documents. The problem is that it got left "
            "enabled by default on countless FTP daemons for decades "
            "after that use case stopped being common, so a huge amount "
            "of real-world FTP servers still answer to it, usually "
            "because whoever set the server up never turned it off "
            "rather than because anyone wanted the public to have access."
        ),
        "what_to_watch_for": (
            "This is a five-second check that costs nothing and "
            "occasionally hands you the whole box -- config files, "
            "credentials left in a home directory, a write-access folder "
            "you can drop a webshell into. The generalizable habit: "
            "always try the free/default/no-auth path before assuming a "
            "service requires real credentials. A shocking number of "
            "\"vulnerabilities\" are just defaults nobody changed."
        ),
    },
    "SMB null session / anonymous enumeration": {
        "what_it_is": (
            "SMB (Windows file/printer sharing, and Samba's Linux "
            "implementation of the same protocol) supports connecting "
            "with a \"null session\" -- an empty username and password -- "
            "which, depending on how the server is configured, can still "
            "let you list shares, enumerate valid usernames, and pull "
            "group/policy information without ever authenticating."
        ),
        "why_it_happens": (
            "Older Windows/Samba defaults were considerably looser about "
            "what an unauthenticated connection could see, on the "
            "assumption that internal networks were trusted by default -- "
            "a very 1990s-2000s security posture that didn't survive "
            "contact with the modern internet. Even after Microsoft "
            "tightened the defaults over successive Windows/Samba "
            "versions, a huge number of deployed systems (and a huge "
            "number of deliberately-vulnerable teaching boxes) still run "
            "with the looser settings, either through inertia or because "
            "some other internal tool depends on the old behavior."
        ),
        "what_to_watch_for": (
            "This is one of the highest-value \"try it for free\" checks "
            "in an enumeration phase, because the payoff (a list of real "
            "usernames, a readable share) directly feeds every later "
            "step -- you can't brute-force a login with a username you "
            "don't have. The generalizable pattern: enumeration is rarely "
            "one tool doing one thing; it's several cheap unauthenticated "
            "probes stacked together, each one narrowing what the next "
            "step should be."
        ),
    },
    "SSH version banner grabbing for known CVEs": {
        "what_it_is": (
            "SSH servers announce their exact software version in the "
            "very first bytes of a connection, before any authentication "
            "happens at all -- which means you can learn the precise "
            "OpenSSH build a target is running just by connecting and "
            "reading, with no login required."
        ),
        "why_it_happens": (
            "This isn't a flaw specific to SSH -- almost every network "
            "service announces itself this way, because interoperability "
            "requires both sides to know what protocol dialect they're "
            "speaking. The security tradeoff is that the same "
            "transparency that lets two SSH clients/servers negotiate "
            "correctly also tells an attacker exactly which version-"
            "specific bugs might apply, without needing to guess."
        ),
        "what_to_watch_for": (
            "SSH itself is rarely the easy way in on a well-patched box -- "
            "most OpenSSH CVEs are narrow (a specific auth-bypass window, "
            "a user-enumeration timing bug, occasionally something more "
            "serious) and version-specific enough that they won't apply "
            "most of the time. The real habit this teaches: banner "
            "grabbing is nearly free, so do it on every service, even the "
            "ones you don't expect to be vulnerable -- the cost of "
            "checking is a few seconds, and the alternative is missing "
            "the one time it actually matters."
        ),
    },
    "HTTP directory brute-forcing is next after a webserver is found": {
        "what_it_is": (
            "Web applications almost always have more URLs than the ones "
            "linked from the homepage -- admin panels, backup files left "
            "behind by a careless deploy, API endpoints never meant to be "
            "public, old versions of pages someone forgot to delete. "
            "Directory brute-forcing systematically requests a large "
            "wordlist of common path names against a target and reports "
            "which ones actually respond."
        ),
        "why_it_happens": (
            "Nobody manually removes every trace of a web application's "
            "development history before shipping it, and modern web apps "
            "genuinely do have dozens-to-hundreds of routes that were "
            "never meant to be discovered by navigation alone -- they're "
            "reached by a mobile app's hardcoded API calls, or an admin "
            "who bookmarked the login page and never told anyone else it "
            "existed. None of that shows up by clicking around; it only "
            "shows up by asking the server directly whether each "
            "candidate path exists."
        ),
        "what_to_watch_for": (
            "This is close to mandatory on any HTTP/HTTPS port you find, "
            "because the return on five minutes of brute-forcing is "
            "consistently high -- it's one of the few techniques in "
            "recon that reliably turns \"nothing visible here\" into \"oh, "
            "there's an entire admin login I wasn't shown.\" The "
            "generalizable lesson: what a web server shows you by default "
            "and what it will actually respond to are two very different "
            "sets of URLs, and the gap between them is where a lot of "
            "real findings live."
        ),
    },
    "SUID binaries are the first privesc check on Linux": {
        "what_it_is": (
            "A SUID (\"set user ID\") bit on an executable makes it run "
            "with the permissions of the file's OWNER, not the user who "
            "launched it -- so a binary owned by root with the SUID bit "
            "set runs as root no matter who executes it. This exists so "
            "that ordinary users can run a small number of privileged "
            "operations (changing their own password, for instance) "
            "without being handed full root access."
        ),
        "why_it_happens": (
            "The mechanism itself is intentional and decades old, but the "
            "vulnerability shows up when a SUID binary can be convinced "
            "to do something its author didn't intend -- read an "
            "arbitrary file, write one, or spawn a shell -- while still "
            "running as root. GTFOBins exists specifically because a "
            "surprising number of completely ordinary, pre-installed "
            "Linux utilities (things you'd never suspect) have a "
            "documented way to be abused exactly like this if the SUID "
            "bit is set on them, usually by an administrator who set it "
            "for a legitimate reason years ago and forgot it was there."
        ),
        "what_to_watch_for": (
            "This is the very first thing to check the moment you have "
            "any shell at all, before anything more elaborate -- it costs "
            "one command and regularly turns a low-privilege foothold "
            "into root in under a minute. The generalizable habit: once "
            "you're on a box, your first move is always a cheap, "
            "automatic sweep for the well-known misconfiguration classes "
            "(SUID, sudo -l, writable cron jobs, capabilities) before "
            "reaching for anything that requires real analysis -- most "
            "boxes fall to one of a small number of well-documented "
            "shapes, and checking the cheap ones first is just efficient."
        ),
    },
}

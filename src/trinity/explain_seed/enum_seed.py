"""Pre-authored ELI5 explanations for SMB, FTP, and SSH enumeration
commands — the standard checks for those three services on a box."""
from __future__ import annotations

ENTRIES: dict[str, str] = {
    "smbclient -L //<target>/ -N": (
        "smbclient talks to Windows/Samba file shares. -L lists every "
        "share the server offers (like folders you could connect to), "
        "and -N tells it not to prompt for a password — it tries an "
        "anonymous ('null') connection instead. If the server allows "
        "this, you instantly see what shares exist without any "
        "credentials at all."
    ),
    "smbclient //<target>/<share> -N": (
        "Connects directly into one specific SMB share (rather than "
        "just listing shares) using an anonymous/null login (-N). Once "
        "connected you get an interactive prompt where you can 'ls' to "
        "list files and 'get <file>' to download them — the SMB "
        "equivalent of browsing a shared folder."
    ),
    "enum4linux -a <target>": (
        "enum4linux is a one-stop SMB enumeration tool — it tries to "
        "pull users, groups, shares, password policy, and OS "
        "information all in one run, often without needing any "
        "credentials. -a means 'do everything' — run every check it "
        "has. It's the older, still widely used tool; enum4linux-ng is "
        "a modern rewrite with cleaner (JSON) output."
    ),
    "enum4linux-ng -A <target>": (
        "enum4linux-ng is a rewritten, more actively maintained version "
        "of enum4linux. -A runs all the standard enumeration checks "
        "(shares, users, groups, OS info, password policy) in one pass. "
        "Its output is structured enough to parse programmatically, "
        "unlike the original tool's plain text."
    ),
    "crackmapexec smb <target> --shares -u '' -p ''": (
        "CrackMapExec (often shortened to CME) is a network-protocol "
        "swiss-army-knife, here targeting SMB. --shares lists available "
        "shares. -u '' -p '' passes empty username and password, which "
        "attempts a null/anonymous login — the same idea as smbclient's "
        "-N but through a different tool that also handles multiple "
        "targets and credential testing well."
    ),
    "rpcclient -U '' <target>": (
        "rpcclient talks to the Windows RPC service that SMB exposes. "
        "-U '' attempts a connection with no username (anonymous/null "
        "session). Once connected, you get an interactive shell where "
        "commands like 'enumdomusers' or 'querydominfo' can pull user "
        "lists and domain info — useful when smbclient/enum4linux don't "
        "give the full picture."
    ),
    "smbmap -H <target>": (
        "smbmap checks what permission level you have on every SMB "
        "share on a target — read, write, or no access — which "
        "smbclient's basic listing doesn't show clearly. -H sets the "
        "target host. Particularly useful for spotting a share you can "
        "actually write to, since a writable share is often a path to a "
        "foothold."
    ),
    "ftp <target>": (
        "Opens an interactive FTP (File Transfer Protocol) session to "
        "the target. The very first thing worth trying is logging in "
        "with username 'anonymous' and any (or blank) password — a "
        "surprising number of FTP servers, especially on CTF boxes, "
        "allow this by default and give you a browsable file listing "
        "with no real authentication at all."
    ),
    "wget -m ftp://anonymous:anonymous@<target>/": (
        "Uses wget's mirror mode (-m) to recursively download an "
        "entire anonymous FTP server's contents in one command, instead "
        "of manually browsing and downloading files one at a time "
        "through an interactive FTP session. Handy when anonymous "
        "access is confirmed and there's a lot to grab."
    ),
    "ssh <user>@<target>": (
        "The standard way to open an interactive SSH (Secure Shell) "
        "session to a target once you have valid credentials — this is "
        "usually the goal after finding a foothold, not a recon step "
        "itself. SSH itself is rarely the initial way in on a CTF box, "
        "since it requires a valid username/password or key already."
    ),
    "ssh-keyscan <target>": (
        "Grabs the target's public SSH host key(s) without logging in "
        "or authenticating at all. Occasionally useful for fingerprinting "
        "(different SSH implementations/versions have subtly different "
        "key behavior) but mostly a reconnaissance curiosity rather than "
        "a common attack step."
    ),
    "hydra -l <user> -P <wordlist> ssh://<target>": (
        "hydra is a network login brute-forcer. -l sets a single known "
        "username, -P points to a password wordlist to try against it, "
        "and ssh://<target> sets the protocol and target. It tries each "
        "password in the list until one works or the list runs out. "
        "Worth using deliberately (a specific, plausible username) "
        "rather than blindly — brute-forcing SSH broadly is slow and "
        "often not the intended path on a well-designed CTF box."
    ),
}

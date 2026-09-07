"""Pre-authored ELI5 explanations for AutoRecon (github.com/Tib3rius/
AutoRecon) — a primary teaching goal per docs/FEATURES_BACKLOG.md, not a
minor mention. AutoRecon is a real, existing tool Trinity teaches about
and parses output FROM (see parsers/autorecon.py) — Trinity never
launches it on the operator's behalf. The operator runs it themselves in
their own terminal pane; these entries exist so someone who's never heard
of it can go 'as much or as little under the hood' as they want, per
Alexander's framing: invite the calculator once the arithmetic (manual
nmap -> gobuster -> ... reasoning) is understood, don't teach long
division forever."""
from __future__ import annotations

ENTRIES: dict[str, str] = {
    "autorecon <target>": (
        "AutoRecon (github.com/Tib3rius/AutoRecon) is a real, widely-used "
        "recon tool: point it at a target and it runs nmap first, then "
        "automatically fans out into the right follow-up tool for every "
        "open port it finds — gobuster/feroxbuster on HTTP, enum4linux-ng "
        "and smbclient on SMB, nikto and whatweb on web servers, and so "
        "on — all multi-threaded so multiple scans run at once instead of "
        "one after another. It's the exact 'find a service, run the "
        "obvious follow-up tool' pattern you do by hand, automated. You "
        "still run it yourself in your own terminal pane — Trinity never "
        "launches it — but Trinity will read the files it drops via "
        "`trinity parse-autorecon`."
    ),
    "when should I use autorecon": (
        "Reach for AutoRecon once the WHY behind each follow-up scan is "
        "boring, not before. If you're still working out why HTTP means "
        "'run gobuster next' or why an open SMB port means 'try "
        "enum4linux', do that by hand a few boxes first — that reasoning "
        "is the actual skill. Once it's automatic in your head, AutoRecon "
        "just saves you the typing and runs everything in parallel "
        "instead of serially, which matters a lot on boxes with a dozen "
        "open ports. Think of it as a calculator for arithmetic you've "
        "already learned, not a shortcut past learning it."
    ),
    "autorecon results directory": (
        "AutoRecon writes everything under `results/<target>/`, split "
        "into a few purpose-built folders: `scans/` has the raw output "
        "of every tool it ran (one file per port+service+tool, e.g. "
        "`tcp_80_http_gobuster.txt`), plus `scans/xml/` holding the "
        "nmap XML specifically; `loot/` is for anything you pull off the "
        "box (hashes, interesting files); `exploit/` is a scratch space "
        "for exploit code; and `report/` has `notes.txt`/`local.txt`/"
        "`proof.txt` stubs plus a `screenshots/` folder, meant to double "
        "as a report skeleton as you go. `scans/_commands.log` records "
        "every command it actually ran — the fastest way to see exactly "
        "what happened without opening a dozen files."
    ),
    "trinity parse-autorecon <results-dir> --box <name>": (
        "Once you've run AutoRecon yourself and it's finished, point "
        "Trinity at the results directory it created for one target and "
        "Trinity will walk `scans/` (and `scans/xml/`), recognize which "
        "files came from tools it already knows how to parse (nmap XML, "
        "gobuster text, and friends), and feed every finding through the "
        "same match engine and timeline as `trinity parse-nmap` — same "
        "output, same suggestions, just sourced from AutoRecon's batch "
        "run instead of one scan at a time. Files from tools Trinity "
        "doesn't have a parser for yet are skipped, not fatal."
    ),
}

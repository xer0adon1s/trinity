# Trinity

A local-first recon copilot for CTF/HTB/TryHackMe-style offensive
security practice — matches your scan output against a local knowledge
base and a live offline exploit database before ever spending an AI
token, suggests next commands, and explains anything in plain English.
Free and open source.

See [DESIGN.md](./DESIGN.md) for the full architecture, philosophy, and
roadmap.

## Quickstart

```bash
uv sync
uv run trinity init
uv run trinity parse-nmap <scan.xml> --box "MyBox" --target <ip> --platform htb
uv run trinity report --box "MyBox"
```

## Status

Early development. Core engine (parsing, matching, suggestions, ELI5
explanations, reports) is built and tested; see DESIGN.md's Roadmap for
what's next.

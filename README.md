# Trinity

A local-first lab partner for CTF/HTB/TryHackMe-style offensive
security practice — watches your recon output, matches it against a
local knowledge base and a live offline exploit database before ever
spending an AI token, and recommends the next move like a TA looking
over your shoulder. Free and open source.

See [DESIGN.md](./DESIGN.md) for the full architecture, philosophy, and
roadmap.

**Practice labs and authorized work only.** Trinity is a teaching tool,
not a substitute for a human pentest report.

## Quickstart (the actual first-box story)

```bash
uv sync
uv run trinity
```

That's it. The wizard asks a few questions (name, target, platform,
mode), then hands this pane straight to `watch` — leave it running here
and open a second terminal for the real recon tools. The wizard prints
the exact first `nmap` command to run there.

From then on: run the real tool in your own terminal, watch this pane
narrate what it means, and follow `trinity next` (or the dashboard's
`d`/`s`/`h` keys) for what to do next.

## Power user / how the engine works

Everything below still works standalone, no wizard required:

```bash
uv run trinity init                                            # (re-)seed the KB/explain/error libraries manually
uv run trinity parse-nmap <scan.xml> --box "MyBox" --target <ip> --platform htb
uv run trinity report --box "MyBox"
```

`trinity --help` lists every command — `next`/`hint`/`did`/`skip`/
`explain`/`error`/`watch`/`report`/`box-status`/`theme`/`share-export`
and more.

## Status

Early development. Core engine (parsing, matching, suggestions, ELI5
explanations, Instructor Mode, reports) is built and tested; see
DESIGN.md's Roadmap for what's next.

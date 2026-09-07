# Trinity

A local-first lab partner for CTF/HTB/TryHackMe-style offensive
security practice, **built to be paired with an agentic operating
system** (Omarchy recommended) — watches your recon output, matches it
against a local knowledge base and a live offline exploit database
before ever reaching for AI, and recommends the next move like a TA
looking over your shoulder. When it genuinely doesn't know something,
it asks YOUR agent CLI once, reviews the answer, and remembers it
forever — the local cache keeps growing so the same question is never
paid for twice. Free and open source.

See [DESIGN.md](./DESIGN.md) for the full architecture, philosophy, and
roadmap — including why this project exists (teach, get people excited
about hacking, and prepare the next generation for a world where
agent-vs-agent is the norm).

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

### Optional: put `trinity` on your PATH

`uv run trinity` only works from inside this repo. If you'd rather run
`trinity` from any directory/pane without `cd`-ing back here first:

```bash
uv tool install .
```

This builds a normal, isolated install and drops a `trinity` binary
onto your PATH (usually `~/.local/bin/trinity`) — the same command,
same local `~/.trinity/` database, just callable from anywhere. Purely
a convenience step; nothing about Trinity's behavior changes. If
you're actively developing Trinity itself rather than just using it,
use `uv tool install --editable .` instead so the global command
always reflects your live source tree.

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

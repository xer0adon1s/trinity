# Contributing to Trinity

Trinity is free and open source (MIT licensed), and most of what makes
it useful over time is community-contributed data, not just code. See
[DESIGN.md](./DESIGN.md) for the full architecture and philosophy
first — it explains *why* things are built the way they are, which
matters more here than in most projects.

## The easiest ways to contribute (no Python required)

These are plain data files — a PR adding one is genuinely welcome even
if you've never touched the Python code:

- **New platform** (`src/trinity/platforms.yaml`): add an entry for a
  CTF/lab platform Trinity doesn't know about yet — a university's
  CTFd instance, a wargame site, anything with a coherent scope
  definition. Copy an existing entry's shape.
- **New KB entry** (`src/trinity/kb/seed.py`): a known
  vulnerability/technique Trinity should recognize by
  product+version, with a plain-English summary.
- **New ELI5 explanation** (`src/trinity/explain_seed/*.py`): a
  command Trinity doesn't yet have a cached explanation for. Pick the
  right category file (or start a new one for a new category) and add
  an entry — see any existing file for the shape.

## Contributing code

- Every change should have a test. Run the suite with:
  ```bash
  uv run pytest test/unit -q
  ```
- Keep the "I do / we do" philosophy in mind (see DESIGN.md) — Trinity
  narrates and assists; it does not run exploits or solve boxes for
  the operator. Features that would replace hands-on learning are out
  of scope by design, not by oversight.
- Never commit anything that reproduces a platform's trademarked
  logo/wordmark, or scrapes/republishes third-party writeups — see
  DESIGN.md's licensing/scope notes for why.
- No secrets, credentials, or real target IPs/hostnames in test
  fixtures or commit messages.

## Reporting issues

Include what platform/box you were working (generically — "an HTB
Linux box," not the box's identifying details if that matters to you),
what command you ran, and what Trinity did vs. what you expected.

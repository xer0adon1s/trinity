"""Local GTFOBins lookup, backed by a full clone of the public GTFOBins
dataset (github.com/GTFOBins/GTFOBins.github.io, MIT licensed) synced
in via the Update Framework (docs/UPDATE_FRAMEWORK.md, "Part 1" —
see `sync()` below and its wiring in cli/main.py's group callback).

Scope: only the `sudo` and `suid` function blocks per binary are
ingested — that's what matters for privesc, per
docs/FEATURES_BACKLOG.md's GTFOBins scoping note. Binaries with no
sudo/suid vector documented upstream are skipped entirely, not stored
as empty entries.

Offline-first: if the repo has never synced successfully (first run,
no network) `lookup()`/`known_binaries()` fall back to a small
hand-authored seed set (the original 8-binary prototype list) rather
than returning nothing — zero-network operation is one of Trinity's
actual selling points, not just a nice-to-have.
"""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

import yaml
from pydantic import BaseModel

GTFOBINS_REPO_URL = "https://github.com/GTFOBins/GTFOBins.github.io.git"

# Where Trinity keeps its local, git-cloned mirror of GTFOBins --
# consistent with shoulder.py's SESSIONS_DIR and platform_registry.py's
# local override path, both under ~/.trinity/.
GTFOBINS_DIR = Path.home() / ".trinity" / "gtfobins-src"
# Parsed-and-cached output (sudo/suid entries only), read by lookup()
# on the hot path instead of re-parsing ~400 markdown files on every
# call -- same "parse once, read the cache" shape as kb/seed.py's
# insert-once seeding.
GTFOBINS_CACHE_PATH = Path.home() / ".trinity" / "gtfobins-cache.json"

_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?\n)(?:---|\.\.\.)\s*\n?", re.DOTALL)

# Hand-authored fallback/seed -- kept verbatim as the offline-safe
# default when the full dataset has never synced. Small and PR-able,
# same spirit as the original prototype this module replaces.
_FALLBACK_ENTRIES: dict[str, tuple[str, str]] = {
    "vim": (
        "If sudo allows vim, it can spawn a shell (`:!sh`) or write files as the privileged user.",
        "https://gtfobins.github.io/gtfobins/vim/",
    ),
    "find": (
        "If sudo allows find, `-exec` runs a command as that user.",
        "https://gtfobins.github.io/gtfobins/find/",
    ),
    "python": (
        "If sudo allows python, a one-liner can spawn a pty shell as that user.",
        "https://gtfobins.github.io/gtfobins/python/",
    ),
    "bash": (
        "If sudo allows bash, you already have the shell — run it.",
        "https://gtfobins.github.io/gtfobins/bash/",
    ),
    "less": (
        "If sudo allows less, `!sh` inside the pager is a shell.",
        "https://gtfobins.github.io/gtfobins/less/",
    ),
    "nmap": (
        "Older sudo nmap can `--interactive` then `!sh`; newer ones still write files via `-oG`.",
        "https://gtfobins.github.io/gtfobins/nmap/",
    ),
    "env": (
        "If sudo allows env, `sudo env /bin/sh` is enough.",
        "https://gtfobins.github.io/gtfobins/env/",
    ),
    "awk": (
        "If sudo allows awk, it can execute a shell snippet.",
        "https://gtfobins.github.io/gtfobins/awk/",
    ),
}


class GtfobinsHit(BaseModel):
    binary: str
    summary: str
    source_url: str


def _binary_url(name: str) -> str:
    return f"https://gtfobins.github.io/gtfobins/{name}/"


def parse_frontmatter(text: str) -> dict | None:
    """Extract and parse the YAML frontmatter block from a GTFOBins
    markdown file's contents. Returns None if there's no frontmatter
    block or it doesn't parse as a mapping."""
    match = _FRONTMATTER_RE.match(text)
    if not match:
        return None
    try:
        data = yaml.safe_load(match.group(1))
    except yaml.YAMLError:
        return None
    return data if isinstance(data, dict) else None


def extract_privesc_summary(frontmatter: dict, binary: str) -> str | None:
    """Given a parsed GTFOBins frontmatter dict, build a one-line
    Trinity-voice summary covering ONLY function entries that apply
    via a `sudo` or `suid` context (see module docstring + the
    "actual GTFOBins schema" note below) -- out-of-scope vectors like
    plain file-read/file-write with no sudo/suid context are skipped.
    Returns None if nothing in this file has a sudo/suid vector.

    NOTE on schema (deviation from the original task brief, which
    assumed sudo/suid were themselves top-level function names with a
    `description` field): the real upstream schema nests them as
    CONTEXT keys inside each function-category entry
    (`functions.<category>[].contexts.sudo` /
    `.suid`), and the human-readable text field is `comment` (often
    absent -- many entries are code-only). This function was adjusted
    to match the real, live GTFOBins.github.io data confirmed during
    the actual ingestion run, not the assumed shape.
    """
    functions = frontmatter.get("functions")
    if not isinstance(functions, dict):
        return None

    fragments: list[str] = []
    for func_name, raw_entries in functions.items():
        entries = raw_entries if isinstance(raw_entries, list) else [raw_entries]
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            contexts = entry.get("contexts")
            if not isinstance(contexts, dict):
                continue
            vectors = [v for v in ("sudo", "suid") if v in contexts]
            if not vectors:
                continue

            comment = (entry.get("comment") or "").strip()
            if comment:
                fragment = f"[{func_name}] {' '.join(comment.split())}"
            else:
                fragment = f"[{func_name}] via {'/'.join(vectors)}"
            fragments.append(fragment)
            break  # one fragment per function category is enough

    if not fragments:
        return None
    return f"If sudo/suid allows {binary}: " + "; ".join(fragments)


def _run_git(args: list[str], cwd: Path | None = None, timeout: int = 30) -> None:
    """Thin, defensively-timed wrapper around a single git invocation.
    Raises on any failure -- callers (sync()) are responsible for
    catching, per update_sync.py's silent-degrade contract."""
    subprocess.run(
        ["git", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
        timeout=timeout,
    )


def _clone_or_pull(repo_dir: Path = GTFOBINS_DIR, timeout: int = 30) -> None:
    if (repo_dir / ".git").exists():
        _run_git(["pull", "--ff-only"], cwd=repo_dir, timeout=timeout)
    else:
        repo_dir.parent.mkdir(parents=True, exist_ok=True)
        _run_git(["clone", "--depth", "1", GTFOBINS_REPO_URL, str(repo_dir)], timeout=timeout)


def _parse_repo_to_cache(repo_dir: Path = GTFOBINS_DIR) -> dict[str, tuple[str, str]]:
    """Parses every markdown file in the repo's `_gtfobins` directory,
    keeping only entries with a sudo/suid vector. Returns the same
    {binary: (summary, url)} shape the old hardcoded dict used."""
    entries: dict[str, tuple[str, str]] = {}
    src_dir = repo_dir / "_gtfobins"
    if not src_dir.is_dir():
        return entries

    for md_file in sorted(src_dir.iterdir()):
        if not md_file.is_file():
            continue
        binary = md_file.stem
        try:
            text = md_file.read_text(errors="replace")
        except OSError:
            continue
        frontmatter = parse_frontmatter(text)
        if frontmatter is None:
            continue
        summary = extract_privesc_summary(frontmatter, binary)
        if summary is None:
            continue
        entries[binary] = (summary, _binary_url(binary))

    return entries


def sync(repo_dir: Path = GTFOBINS_DIR, cache_path: Path = GTFOBINS_CACHE_PATH, timeout: int = 20) -> None:
    """Update Framework Part 1 sync function for source='gtfobins':
    shallow-clone (or pull) the public GTFOBins repo, parse it down to
    sudo/suid entries, and write that to the local JSON cache lookup()
    reads from. Registered with run_sync_if_due() in cli/main.py; any
    exception here is caught by that caller, never by us -- we let it
    propagate so run_sync_if_due can record the failure."""
    _clone_or_pull(repo_dir, timeout=timeout)
    entries = _parse_repo_to_cache(repo_dir)
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps(entries, indent=2, sort_keys=True))


def _load_entries(cache_path: Path | None = None) -> dict[str, tuple[str, str]]:
    """Read the parsed cache if it exists and is non-empty; otherwise
    fall back to the small hand-authored seed set so lookups keep
    working with zero network (first run, or every sync has failed).
    Reads the module-level GTFOBINS_CACHE_PATH at call time (rather
    than binding it as a default argument) so tests can monkeypatch
    it and callers overriding the path still see live changes."""
    if cache_path is None:
        cache_path = GTFOBINS_CACHE_PATH
    if cache_path.exists():
        try:
            raw = json.loads(cache_path.read_text())
            if isinstance(raw, dict) and raw:
                return {k: (v[0], v[1]) for k, v in raw.items()}
        except (OSError, json.JSONDecodeError, KeyError, IndexError, TypeError):
            pass
    return _FALLBACK_ENTRIES


def lookup(binary: str) -> GtfobinsHit | None:
    key = binary.strip().lower().rsplit("/", 1)[-1]
    entries = _load_entries()
    if key not in entries:
        return None
    summary, url = entries[key]
    return GtfobinsHit(binary=key, summary=summary, source_url=url)


def known_binaries() -> list[str]:
    return sorted(_load_entries())

"""Tests for GTFOBins ingestion: YAML-frontmatter parsing, sudo/suid
scoping, and the offline fallback-to-hardcoded-8 behavior when no
parsed cache exists yet (docs/UPDATE_FRAMEWORK.md Part 1 + Part B of
the GTFOBins ingestion work).

Fixtures below mirror the REAL upstream GTFOBins.github.io frontmatter
schema (confirmed against the live repo during ingestion): `sudo`/
`suid` are CONTEXT keys nested inside each function-category entry
(functions.<category>[].contexts.sudo/.suid), not top-level function
names, and the human-readable text field is `comment` (frequently
absent). This differs from the schema assumed in the original task
brief (`description` under top-level `sudo`/`suid` keys) -- adjusted
to match reality rather than the assumption.
"""
from __future__ import annotations

import json

from trinity import gtfobins


FIXTURE_WITH_SUDO_AND_SUID = """---
functions:
  shell:
  - code: |-
      find . -exec /bin/sh \\; -quit
    contexts:
      sudo:
      suid:
        code: |-
          find . -exec /bin/sh -p \\; -quit
        shell: false
      unprivileged:
  file-read:
  - code: |-
      find /path/to/input-file -exec cat {} \\;
    comment: |-
      This uses cat to actually read the file.
    contexts:
      unprivileged:
---

# find
"""

FIXTURE_NO_PRIVESC_VECTOR = """---
functions:
  file-read:
  - code: |-
      lessbin /path/to/input-file
    contexts:
      unprivileged:
---

# lessbin
"""

FIXTURE_NO_FRONTMATTER = "# just some markdown\nno frontmatter here.\n"


def test_parse_frontmatter_extracts_yaml_block():
    data = gtfobins.parse_frontmatter(FIXTURE_WITH_SUDO_AND_SUID)
    assert data is not None
    assert "functions" in data
    assert "shell" in data["functions"]
    assert "file-read" in data["functions"]


def test_parse_frontmatter_returns_none_without_a_block():
    assert gtfobins.parse_frontmatter(FIXTURE_NO_FRONTMATTER) is None


def test_extract_privesc_summary_includes_only_sudo_suid_contexts():
    data = gtfobins.parse_frontmatter(FIXTURE_WITH_SUDO_AND_SUID)
    assert data is not None
    summary = gtfobins.extract_privesc_summary(data, "find")
    assert summary is not None
    # `shell` has a sudo/suid context -> in scope.
    assert "[shell]" in summary
    # `file-read` here has ONLY an `unprivileged` context -> out of scope.
    assert "[file-read]" not in summary


def test_extract_privesc_summary_none_when_no_sudo_or_suid_context():
    data = gtfobins.parse_frontmatter(FIXTURE_NO_PRIVESC_VECTOR)
    assert data is not None
    assert gtfobins.extract_privesc_summary(data, "lessbin") is None


def test_lookup_falls_back_to_hardcoded_eight_when_no_cache(tmp_path, monkeypatch):
    missing_cache = tmp_path / "does-not-exist.json"
    monkeypatch.setattr(gtfobins, "GTFOBINS_CACHE_PATH", missing_cache)

    hit = gtfobins.lookup("vim")
    assert hit is not None
    assert "gtfobins.github.io" in hit.source_url

    binaries = gtfobins.known_binaries()
    assert binaries == sorted(gtfobins._FALLBACK_ENTRIES)
    assert len(binaries) == 8


def test_lookup_prefers_cache_over_fallback_when_cache_populated(tmp_path, monkeypatch):
    cache_path = tmp_path / "gtfobins-cache.json"
    cache_path.write_text(json.dumps({
        "totallynewbin": ["If sudo/suid allows totallynewbin: [shell] test.", "https://gtfobins.github.io/gtfobins/totallynewbin/"],
    }))
    monkeypatch.setattr(gtfobins, "GTFOBINS_CACHE_PATH", cache_path)

    hit = gtfobins.lookup("totallynewbin")
    assert hit is not None
    assert hit.binary == "totallynewbin"
    # Fallback entries are NOT merged in once a real cache exists.
    assert gtfobins.lookup("vim") is None
    assert gtfobins.known_binaries() == ["totallynewbin"]


def test_lookup_unknown_binary_returns_none(tmp_path, monkeypatch):
    monkeypatch.setattr(gtfobins, "GTFOBINS_CACHE_PATH", tmp_path / "missing.json")
    assert gtfobins.lookup("definitely-not-a-real-binary") is None


def test_parse_repo_to_cache_skips_files_with_no_privesc_vector(tmp_path):
    repo_dir = tmp_path / "repo"
    src_dir = repo_dir / "_gtfobins"
    src_dir.mkdir(parents=True)
    # Real GTFOBins source files have NO extension (e.g. `find`, not
    # `find.md`) -- exercised here deliberately.
    (src_dir / "find").write_text(FIXTURE_WITH_SUDO_AND_SUID)
    (src_dir / "lessbin").write_text(FIXTURE_NO_PRIVESC_VECTOR)

    entries = gtfobins._parse_repo_to_cache(repo_dir)
    assert "find" in entries
    assert "lessbin" not in entries
    summary, url = entries["find"]
    assert url == "https://gtfobins.github.io/gtfobins/find/"
    assert "[shell]" in summary

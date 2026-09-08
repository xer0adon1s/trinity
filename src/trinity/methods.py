"""PROTOTYPE — Methods Index read-side (docs/METHODS_INDEX.md steps 1–2).

Citation index of distinct methods on *retired* boxes. Never scraped
writeup text. Never shown by the wizard. `trinity methods-fetch` is
intentionally not implemented (offline pipeline, human review).

A Method without author + source_url is invalid and is dropped.
Summaries longer than ~2 sentences are rejected at load time.
"""
from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, field_validator

_INDEX_DIR = Path(__file__).parent / "methods_index"
_SUMMARY_CEILING = 400


class Method(BaseModel):
    category: str
    technique: str
    summary: str
    source_url: str
    author: str
    retrieved_at: str

    @field_validator("source_url", "author", mode="before")
    @classmethod
    def required_citation(cls, value: object) -> str:
        text = str(value or "").strip()
        if not text:
            raise ValueError("source_url and author are required")
        return text

    @field_validator("summary")
    @classmethod
    def short_paraphrase(cls, value: str) -> str:
        text = " ".join((value or "").split())
        if not text:
            raise ValueError("summary is required")
        if len(text) > _SUMMARY_CEILING:
            raise ValueError("summary exceeds the paraphrase ceiling")
        return text


class BoxMethodsIndex(BaseModel):
    box_name: str
    platform: str | None = None
    methods: list[Method]


def _load_file(path: Path) -> BoxMethodsIndex | None:
    raw = yaml.safe_load(path.read_text()) or {}
    try:
        return BoxMethodsIndex.model_validate(raw)
    except Exception:  # noqa: BLE001 -- malformed YAML/index entries are skipped
        return None


def load_all() -> list[BoxMethodsIndex]:
    if not _INDEX_DIR.exists():
        return []
    indexes: list[BoxMethodsIndex] = []
    for path in sorted(_INDEX_DIR.glob("*.yaml")):
        loaded = _load_file(path)
        if loaded is not None:
            indexes.append(loaded)
    return indexes


def lookup(name: str, platform: str | None = None) -> BoxMethodsIndex | None:
    """Case-insensitive box_name match. Optional platform filter."""
    needle = name.strip().lower()
    for index in load_all():
        if index.box_name.lower() != needle:
            continue
        if platform and index.platform and index.platform.lower() != platform.lower():
            continue
        return index
    return None


def format_index(index: BoxMethodsIndex) -> str:
    """Attribution is inline on every method. Never a hidden field."""
    lines = [
        f"Known method shapes for {index.box_name}"
        + (f" ({index.platform})" if index.platform else ""),
        "These are different public approaches — not the answer, not a walkthrough.",
        "",
    ]
    by_cat: dict[str, list[Method]] = {}
    for method in index.methods:
        by_cat.setdefault(method.category, []).append(method)
    for category, methods in by_cat.items():
        lines.append(f"## {category}")
        lines.append("")
        for method in methods:
            lines.append(f"- **{method.technique}**")
            lines.append(f"  {method.summary}")
            lines.append(f"  — {method.author}, {method.source_url} (retrieved {method.retrieved_at})")
            lines.append("")
    return "\n".join(lines)

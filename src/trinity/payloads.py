"""PROTOTYPE — tiny PayloadsAllTheThings-style technique index (DESIGN 4.2).

Titles + URLs only. Not a dump into any prompt. Not a scrape.
"""
from __future__ import annotations

from pydantic import BaseModel

_ENTRIES: list[tuple[str, str, str]] = [
    ("file-upload", "Insecure file upload", "https://github.com/swisskyrepo/PayloadsAllTheThings/tree/master/Upload%20Insecure%20Files"),
    ("sqli", "SQL injection", "https://github.com/swisskyrepo/PayloadsAllTheThings/tree/master/SQL%20Injection"),
    ("lfi", "Local file inclusion", "https://github.com/swisskyrepo/PayloadsAllTheThings/tree/master/File%20Inclusion"),
    ("ssti", "Server-side template injection", "https://github.com/swisskyrepo/PayloadsAllTheThings/tree/master/Server%20Side%20Template%20Injection"),
    ("xss", "Cross-site scripting", "https://github.com/swisskyrepo/PayloadsAllTheThings/tree/master/XSS%20Injection"),
]


class PayloadTopic(BaseModel):
    id: str
    title: str
    source_url: str


def list_topics() -> list[PayloadTopic]:
    return [PayloadTopic(id=i, title=t, source_url=u) for i, t, u in _ENTRIES]


def lookup(topic_id: str) -> PayloadTopic | None:
    needle = topic_id.strip().lower()
    for item in list_topics():
        if item.id == needle or needle in item.title.lower():
            return item
    return None

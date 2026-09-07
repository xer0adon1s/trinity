"""PROTOTYPE — curiosity unlocks (Trinity_suggestions.md 2.1).

Claude: gate content behind an explicit milestone; declining is the
default; do not auto-lecture; do not spoil box 1 with Methods Index
shapes (debate §2, 1.9). Handoff §D deferred the *content*; this is
a two-card draft so the mechanism exists for Claude to rewrite.

Cards are generic pedagogy, not technique spoilers.
"""
from __future__ import annotations

import sqlite3

from pydantic import BaseModel

from trinity.boxes import get_box


class UnlockCard(BaseModel):
    id: str
    trigger: str  # 'user' available after user-or-root; 'root' after root only
    title: str
    body: str
    source: str = "trinity_preseed"


CARDS: list[UnlockCard] = [
    UnlockCard(
        id="after_user_shell",
        trigger="user",
        title="Why the coach just switched to privilege escalation",
        body=(
            "A user shell means the front door is open. Everything before "
            "this was 'how do I get on the box.' Everything after is "
            "'what can this account already do.' That is why the next "
            "recommendations look different — not because the earlier "
            "ports stopped mattering, but because you already have a "
            "stronger place to stand. You can still go back."
        ),
    ),
    UnlockCard(
        id="after_root",
        trigger="root",
        title="What 'rooted' actually means",
        body=(
            "Rooted means you can act as the most privileged account on "
            "the machine — usually enough to read any flag and stop. "
            "It is a milestone, not a personality test. Plenty of people "
            "with real security jobs still take hours on an 'easy' box. "
            "If you want the engine now (why a specific service was the "
            "way in), that is what the walkthrough report is for. This "
            "card will not name a path you have not already walked."
        ),
    ),
]


def _trigger_met(shell_level: str | None, trigger: str) -> bool:
    if shell_level is None:
        return False
    if trigger == "user":
        return shell_level in ("user", "root")
    if trigger == "root":
        return shell_level == "root"
    return False


def available_cards(conn: sqlite3.Connection, box_id: int) -> list[UnlockCard]:
    """Cards whose milestone is met and that have not been taken or declined."""
    box = get_box(conn, box_id)
    if box is None:
        return []
    decided = {
        row["card_id"]
        for row in conn.execute(
            "SELECT card_id FROM unlock_state WHERE box_id = ?", (box_id,)
        )
    }
    return [
        card for card in CARDS
        if _trigger_met(box.shell_level, card.trigger) and card.id not in decided
    ]


def peek_card(conn: sqlite3.Connection, box_id: int) -> UnlockCard | None:
    cards = available_cards(conn, box_id)
    return cards[0] if cards else None


def take_card(conn: sqlite3.Connection, box_id: int, card_id: str) -> UnlockCard | None:
    card = next((c for c in available_cards(conn, box_id) if c.id == card_id), None)
    if card is None:
        return None
    conn.execute(
        "INSERT INTO unlock_state (box_id, card_id, status) VALUES (?, ?, 'taken')",
        (box_id, card_id),
    )
    conn.commit()
    return card


def decline_card(conn: sqlite3.Connection, box_id: int, card_id: str) -> bool:
    card = next((c for c in available_cards(conn, box_id) if c.id == card_id), None)
    if card is None:
        return False
    conn.execute(
        "INSERT INTO unlock_state (box_id, card_id, status) VALUES (?, ?, 'declined')",
        (box_id, card_id),
    )
    conn.commit()
    return True

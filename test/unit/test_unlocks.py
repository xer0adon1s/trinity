"""PROTOTYPE tests for curiosity unlock cards."""
from __future__ import annotations

from trinity.boxes import create_box
from trinity.milestones import record_shell
from trinity.unlocks import available_cards, decline_card, peek_card, take_card


def test_no_cards_before_a_shell(conn):
    box = create_box(conn, "NoUnlock")
    assert available_cards(conn, box.id) == []
    assert peek_card(conn, box.id) is None


def test_user_shell_unlocks_the_user_card_only(conn):
    box = create_box(conn, "UserUnlock")
    record_shell(conn, box.id, "user")
    ids = {c.id for c in available_cards(conn, box.id)}
    assert "after_user_shell" in ids
    assert "after_root" not in ids


def test_root_shell_unlocks_both_cards(conn):
    box = create_box(conn, "RootUnlock")
    record_shell(conn, box.id, "root")
    ids = {c.id for c in available_cards(conn, box.id)}
    assert ids == {"after_user_shell", "after_root"}


def test_take_removes_card_and_returns_body(conn):
    box = create_box(conn, "TakeUnlock")
    record_shell(conn, box.id, "user")
    card = peek_card(conn, box.id)
    taken = take_card(conn, box.id, card.id)
    assert taken is not None
    assert "privilege escalation" in taken.title.lower()
    assert "front door" in taken.body.lower()
    assert peek_card(conn, box.id) is None


def test_decline_is_the_quiet_path(conn):
    box = create_box(conn, "DeclineUnlock")
    record_shell(conn, box.id, "user")
    card = peek_card(conn, box.id)
    assert decline_card(conn, box.id, card.id) is True
    assert peek_card(conn, box.id) is None

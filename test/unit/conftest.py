"""Shared pytest fixtures — an in-memory Trinity DB with seed data, fresh
per test so nothing leaks between tests or touches the real ~/.trinity."""
from __future__ import annotations

import sqlite3

import pytest

from trinity.db import SCHEMA
from trinity.kb.seed import seed


@pytest.fixture
def conn() -> sqlite3.Connection:
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.executescript(SCHEMA)
    connection.commit()
    return connection


@pytest.fixture
def seeded_conn(conn: sqlite3.Connection) -> sqlite3.Connection:
    seed(conn)
    return conn

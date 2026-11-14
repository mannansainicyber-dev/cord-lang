"""
Tests for Cord persistent storage.
"""

import os
import pytest
from cord.storage import Store


def test_in_memory_store():
    store = Store(db_path=":memory:")
    store["count"] = 1
    assert store["count"] == 1
    assert store.get("count") == 1
    assert store.has("count")

    store.count += 1
    assert store["count"] == 2


def test_nested_store():
    store = Store(db_path=":memory:")
    store.users = {}
    store.users["123"] = {"xp": 50, "warns": 1}

    assert store.users["123"]["xp"] == 50
    store.users["123"]["xp"] += 25
    assert store.users["123"]["xp"] == 75


def test_sqlite_persistence(tmp_path):
    db_file = os.path.join(tmp_path, "test_cord.db")
    store1 = Store(db_path=db_file)
    store1["bot_name"] = "CordBot"
    store1.stats = {"guilds": 5, "active": True}
    store1.notify_update()

    # Create new store instance pointing to same DB file to simulate bot restart
    store2 = Store(db_path=db_file)
    assert store2["bot_name"] == "CordBot"
    assert store2.stats["guilds"] == 5
    assert store2.stats["active"] is True

"""Tests for local persistent memory (fabric-lite)."""

from tattva_swarm.memory import Memory


def test_add_search_roundtrip(tmp_path):
    mem = Memory(tmp_path / "m.sqlite3")
    try:
        entry_id = mem.add("The router prefers Nano for everyday calls", kind="note", tags=["router"])
        assert entry_id == 1
        hits = mem.search("router")
        assert len(hits) == 1
        assert "Nano" in hits[0]["text"]
        assert mem.count() == 1
        assert mem.recent(limit=1)[0]["id"] == 1
    finally:
        mem.close()


def test_search_miss_is_empty(tmp_path):
    mem = Memory(tmp_path / "m.sqlite3")
    try:
        mem.add("sovereign memory stays local")
        assert mem.search("zzyzx-not-here") == []
    finally:
        mem.close()

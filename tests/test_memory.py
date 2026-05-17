"""
Tests for VectorMemoryStore — incomplete coverage and one incorrect assertion.
"""
import pytest
import numpy as np
from src.memory.memory_store import VectorMemoryStore, MemoryEntry


def make_embedding(dim=128, seed=None):
    rng = np.random.default_rng(seed)
    v = rng.random(dim)
    return (v / np.linalg.norm(v)).tolist()


class TestVectorMemoryStore:

    def test_add_and_size(self):
        store = VectorMemoryStore()
        store.add("hello world", make_embedding(seed=1))
        assert store.size == 1

    def test_search_returns_similar(self):
        store = VectorMemoryStore(similarity_threshold=0.5)
        emb = make_embedding(seed=42)
        store.add("the quick brown fox", emb)
        results = store.search(emb, top_k=3)
        assert len(results) == 1
        assert results[0].content == "the quick brown fox"

    def test_max_size_eviction(self):
        store = VectorMemoryStore(max_size=3)
        for i in range(5):
            store.add(f"memory {i}", make_embedding(seed=i))
        assert store.size == 3
        # Which memories survive? Is FIFO the right policy for an agent memory store?

    def test_delete_existing(self):
        store = VectorMemoryStore()
        mid = store.add("to be deleted", make_embedding(seed=7))
        assert store.delete(mid) is True
        assert store.get_by_id(mid) is None

    def test_delete_nonexistent(self):
        store = VectorMemoryStore()
        assert store.delete("does-not-exist") is False

    def test_mutable_default_metadata(self):
        # Exposes the mutable default argument bug in VectorMemoryStore.add()
        store = VectorMemoryStore()
        store.add("entry a", make_embedding(seed=1), metadata={"tag": "a"})
        store.add("entry b", make_embedding(seed=2))  # no metadata passed
        a = store.memories[0]
        b = store.memories[1]
        # If the bug is present, a.metadata and b.metadata are the same object
        assert b.metadata is not a.metadata

    def test_access_count_incremented_on_search(self):
        store = VectorMemoryStore(similarity_threshold=0.0)
        emb = make_embedding(seed=3)
        store.add("tracked memory", emb)
        store.search(emb)
        store.search(emb)
        assert store.memories[0].access_count == 2

    def test_mutable_default_bug_true_exposure(self):
        """Exposes mutable default argument bug: metadata dict shared across calls."""
        store = VectorMemoryStore()
        store.add("entry a", make_embedding(seed=1))  # no metadata, uses default {}
        store.add("entry b", make_embedding(seed=2))  # no metadata, uses default {}

        # Modify first entry's metadata
        store.memories[0].metadata["key"] = "modified"

        # If bug is present, both entries share the same metadata dict
        # This assertion will FAIL if the mutable default bug exists
        assert "key" not in store.memories[1].metadata

    def test_save_load_round_trip(self):
        """Test save/load preserves metadata and all fields."""
        import tempfile
        import os

        store = VectorMemoryStore()
        emb1 = make_embedding(seed=10)
        emb2 = make_embedding(seed=11)
        store.add("content 1", emb1, metadata={"tag": "test", "count": 42})
        store.add("content 2", emb2, metadata={"nested": {"key": "value"}})

        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "memory.json")
            store.save_to_disk(path)

            store2 = VectorMemoryStore()
            store2.load_from_disk(path)

            assert store2.size == 2
            assert store2.memories[0].content == "content 1"
            assert store2.memories[0].metadata["tag"] == "test"
            assert store2.memories[0].metadata["count"] == 42
            assert store2.memories[1].metadata["nested"]["key"] == "value"

    def test_fifo_eviction_is_suboptimal(self):
        """Tests that FIFO eviction doesn't preserve recently accessed items."""
        store = VectorMemoryStore(max_size=3, similarity_threshold=0.0)

        emb1 = make_embedding(seed=20)
        emb2 = make_embedding(seed=21)
        emb3 = make_embedding(seed=22)
        emb4 = make_embedding(seed=23)

        # Add 3 memories
        id1 = store.add("old memory", emb1)
        id2 = store.add("recent memory", emb2)
        id3 = store.add("newer memory", emb3)

        # Access the old memory multiple times (recently used)
        store.search(emb1)
        store.search(emb1)
        assert store.memories[0].access_count == 2

        # Add one more memory — FIFO will evict the oldest (id1, the old memory)
        # But we just accessed it! LRU would keep it since it was recently used
        id4 = store.add("newest memory", emb4)

        # With FIFO, old memory is evicted despite being recently accessed
        assert store.get_by_id(id1) is None  # FIFO evicts first item
        assert store.get_by_id(id2) is not None
        assert store.get_by_id(id3) is not None
        assert store.get_by_id(id4) is not None
        # This test PASSES with FIFO (expected), but shows FIFO is not optimal

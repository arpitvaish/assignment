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

    # TODO: add tests for — save/load round-trip, concurrent access,
    # search with no results, duplicate content IDs, zero-vector embeddings

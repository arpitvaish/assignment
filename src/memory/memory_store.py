"""
Memory subsystem — vector store with cosine similarity search.
"""
import time
import json
import uuid
import numpy as np
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any


@dataclass
class MemoryEntry:
    content: str
    embedding: Optional[List[float]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    last_accessed: float = field(default_factory=time.time)
    access_count: int = 0
    id: str = ""

    def __post_init__(self):
        if not self.id:
            self.id = str(uuid.uuid4())


class VectorMemoryStore:
    """In-memory store with cosine similarity search and LRU eviction."""

    def __init__(self, max_size=1000, similarity_threshold=0.8):
        self.memories: List[MemoryEntry] = []
        self.max_size = max_size
        self.similarity_threshold = similarity_threshold

    def add(self, content: str, embedding: List[float], metadata: dict = None) -> str:
        if metadata is None:
            metadata = {}
        entry = MemoryEntry(content=content, embedding=embedding, metadata=metadata)

        # LRU eviction: drop least recently accessed entry when at capacity.
        # FIFO (original) discarded oldest-inserted regardless of usage — bad for
        # agent memory where recently accessed = likely still relevant.
        if len(self.memories) >= self.max_size:
            lru_idx = min(range(len(self.memories)),
                          key=lambda i: self.memories[i].last_accessed)
            self.memories.pop(lru_idx)

        self.memories.append(entry)
        return entry.id

    def search(self, query_embedding: List[float], top_k: int = 5) -> List[MemoryEntry]:
        results = []
        for mem in self.memories:
            if mem.embedding:
                score = self._cosine_similarity(query_embedding, mem.embedding)
                if score >= self.similarity_threshold:
                    results.append((score, mem))
                    mem.access_count += 1
                    mem.last_accessed = time.time()

        results.sort(key=lambda x: x[0], reverse=True)
        return [r[1] for r in results[:top_k]]

    def batch_search(self, query_embeddings: List[List[float]],
                     top_k: int = 5) -> List[List[MemoryEntry]]:
        """Vectorized search for multiple queries using numpy matrix multiply.

        Replaces O(Q*M) scalar loops with a single (Q, M) dot product.
        """
        entries_with_emb = [m for m in self.memories if m.embedding]
        if not entries_with_emb:
            return [[] for _ in query_embeddings]

        mem_matrix = np.array([m.embedding for m in entries_with_emb], dtype=np.float32)
        mem_norms = np.linalg.norm(mem_matrix, axis=1, keepdims=True)
        mem_norms = np.where(mem_norms == 0, 1, mem_norms)
        mem_normed = mem_matrix / mem_norms

        q_matrix = np.array(query_embeddings, dtype=np.float32)
        q_norms = np.linalg.norm(q_matrix, axis=1, keepdims=True)
        q_norms = np.where(q_norms == 0, 1, q_norms)
        q_normed = q_matrix / q_norms

        scores = q_normed @ mem_normed.T  # (Q, M)

        now = time.time()
        results = []
        for row in scores:
            indices = np.where(row >= self.similarity_threshold)[0]
            ranked = sorted(indices, key=lambda i: row[i], reverse=True)[:top_k]
            hits = []
            for idx in ranked:
                mem = entries_with_emb[idx]
                mem.access_count += 1
                mem.last_accessed = now
                hits.append(mem)
            results.append(hits)
        return results

    def _cosine_similarity(self, a: List[float], b: List[float]) -> float:
        a = np.array(a)
        b = np.array(b)
        dot = np.dot(a, b)
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return float(dot / (norm_a * norm_b))

    def get_by_id(self, memory_id: str) -> Optional[MemoryEntry]:
        for mem in self.memories:
            if mem.id == memory_id:
                return mem
        return None

    def delete(self, memory_id: str) -> bool:
        for i, mem in enumerate(self.memories):
            if mem.id == memory_id:
                self.memories.pop(i)
                return True
        return False

    def save_to_disk(self, path: str):
        data = []
        for mem in self.memories:
            data.append({
                "id": mem.id,
                "content": mem.content,
                "embedding": mem.embedding,
                "metadata": mem.metadata,
                "created_at": mem.created_at,
                "last_accessed": mem.last_accessed,
                "access_count": mem.access_count,
            })
        with open(path, "w") as f:
            json.dump(data, f)

    def load_from_disk(self, path: str):
        with open(path, "r") as f:
            data = json.load(f)
        self.memories = []
        for d in data:
            entry = MemoryEntry(
                content=d["content"],
                embedding=d.get("embedding"),
                metadata=d.get("metadata") or {},
                created_at=d.get("created_at", time.time()),
                last_accessed=d.get("last_accessed", time.time()),
                access_count=d.get("access_count", 0),
                id=d.get("id", ""),
            )
            self.memories.append(entry)

    @property
    def size(self):
        return len(self.memories)

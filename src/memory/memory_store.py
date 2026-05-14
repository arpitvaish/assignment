"""
Memory subsystem — naive implementation with performance and correctness bugs.
"""
import time
import json
import numpy as np
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
import hashlib


@dataclass
class MemoryEntry:
    content: str
    embedding: Optional[List[float]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    access_count: int = 0
    id: str = ""

    def __post_init__(self):
        if not self.id:
            self.id = hashlib.md5(self.content.encode()).hexdigest()


class VectorMemoryStore:
    """In-memory store with cosine similarity search."""

    def __init__(self, max_size=1000, similarity_threshold=0.8):
        self.memories: List[MemoryEntry] = []
        self.max_size = max_size
        self.similarity_threshold = similarity_threshold

    def add(self, content: str, embedding: List[float], metadata: dict = {}) -> str:
        entry = MemoryEntry(content=content, embedding=embedding, metadata=metadata)

        # evict if at capacity — just drop the first one (FIFO, not LRU)
        if len(self.memories) >= self.max_size:
            self.memories.pop(0)

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

        results.sort(key=lambda x: x[0], reverse=True)
        return [r[1] for r in results[:top_k]]

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
                "access_count": mem.access_count,
            })
        with open(path, "w") as f:
            json.dump(data, f)

    def load_from_disk(self, path: str):
        with open(path, "r") as f:
            data = json.load(f)
        self.memories = []
        for d in data:
            self.memories.append(MemoryEntry(**d))

    @property
    def size(self):
        return len(self.memories)

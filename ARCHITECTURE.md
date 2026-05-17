# Architecture: Agentic AI System

## System Overview

```
┌─────────────────────────────────────────────────────────┐
│                    Agent Pipeline                        │
│  (Orchestrates async steps with dependency tracking)    │
└────────────┬────────────────────────────────┬───────────┘
             │                                │
    ┌────────▼────────┐          ┌────────────▼─────────┐
    │  Agents         │          │  Tools               │
    │  - BaseAgent    │          │  - Tool wrapper      │
    │  - ToolCalling  │          │  - Registry          │
    │                 │          │  - Metadata          │
    └────────┬────────┘          └──────────┬──────────┘
             │                              │
             └──────────────┬───────────────┘
                            │
                    ┌───────▼────────┐
                    │  Memory Store  │
                    │  - Vector DB   │
                    │  - Similarity  │
                    │  - Persistence│
                    └────────────────┘
```

## Module Breakdown

### 1. `src/agents/base_agent.py` (171 LOC)

**Purpose**: LLM agent abstraction with retry logic and cost tracking

**Classes**:
- `BaseAgent`: Makes LLM calls, tracks history, costs, errors
  - Methods: `run()`, `_call_llm()`, `add_tool()`, `get_stats()`
  - State: history, total_tokens, total_cost, errors

- `ToolCallingAgent(BaseAgent)`: Extends to call tools in a loop
  - Methods: `run()`, `_call_llm_with_tools()`, `_execute_tool()`
  - Handles tool selection and result feeding back to LLM

**Key Issues Fixed**:
- ✅ Global `_agent_registry` never cleaned up (memory leak)
- ✅ Hardcoded cost rate `0.00001` per token (unrealistic)
- ✅ Code duplication in `_call_llm()` vs `_call_llm_with_tools()`

**Design Decisions**:
- Global registry for agent discovery (trade-off: memory leak risk)
- Synchronous LLM calls (could use async/await for scale)
- History stored in-memory (no persistence)

---

### 2. `src/memory/memory_store.py` (103 LOC)

**Purpose**: In-memory vector database with cosine similarity search

**Classes**:
- `MemoryEntry`: Dataclass for stored items
  - Fields: content, embedding, metadata, created_at, access_count, id
  - Auto-generates ID from content hash

- `VectorMemoryStore`: Searchable memory with eviction
  - Methods: `add()`, `search()`, `get_by_id()`, `delete()`, `save_to_disk()`, `load_from_disk()`
  - Similarity: cosine distance between embeddings
  - Eviction: FIFO when max_size exceeded

**Key Issues Fixed**:
- ✅ Mutable default argument `metadata: dict = {}` (shared across calls)
- ⚠️ FIFO eviction not optimal for agent memory (should be LRU)
- ⚠️ `load_from_disk()` fragile for complex metadata types

**Design Decisions**:
- Numpy for similarity calculations (vectorized)
- In-memory storage (no DB overhead, limited by RAM)
- Metadata as generic dict (flexible but untyped)
- FIFO eviction simple but poor UX (loses recent items)

**Future Improvements**:
- LRU eviction based on access_count
- Batch similarity search (vectorized queries)
- Thread-safe access with locks
- Persistence to disk with type safety

---

### 3. `src/tools/tool_base.py` (101 LOC)

**Purpose**: Tool abstraction and registry for agent tool use

**Classes**:
- `Tool`: Wraps callable with metadata
  - Properties: name, description, parameters, call_count, avg_latency
  - Methods: `run()`, `to_schema()`
  - Tracks: execution time, call count

- `ToolRegistry`: Registry for tool lookup
  - Methods: `register()`, `get()`, `list_tools()`, `clear()`
  - Scope: per-instance (not global)

**Functions**:
- `@tool()` decorator: Extracts type hints and builds JSON schema for tool calling

**Key Issues Fixed**:
- ✅ Class variable `_tools` shared across instances (registry isolation bug)

**Design Decisions**:
- Decorator pattern for easy tool registration
- JSON schema generation from type hints
- Per-instance registry (allows multiple isolated registries)
- No parameter validation (minimal overhead)

---

### 4. `src/infra/pipeline.py` (137 LOC)

**Purpose**: DAG-based step orchestration with async execution

**Classes**:
- `StepStatus`: Enum for step states (PENDING, RUNNING, SUCCESS, FAILED, SKIPPED)

- `StepResult`: Result data for each step
  - Fields: step_name, status, output, error, duration_ms, metadata

- `PipelineContext`: Mutable state threaded through pipeline
  - Fields: inputs, outputs, metadata

- `PipelineStep`: Async step wrapper
  - Methods: `execute(context)` with retry logic
  - Supports both async and sync functions

- `AgentPipeline`: DAG runner
  - Methods: `add_step()`, `add_hook()`, `run()`, `visualize()`
  - Hooks: before_step, after_step, on_failure
  - Dependency resolution and step skipping

**Key Issues Fixed**:
- ✅ Broken dependency skip logic (continue in wrong loop)

**Design Decisions**:
- Dependency tracking via `depends_on` list
- Context mutation (trade-off: rollback complexity)
- Serial execution (could be parallel for independent steps)
- No per-step timeout (could deadlock)

**Future Improvements**:
- Parallel execution for independent steps
- Per-step timeout and cancellation
- Context rollback on failure
- Observability hooks (timing, errors)

---

## Data Flow

### Agent Execution
```
User Input
    ↓
Agent.run(input)
    ↓
LLM Call (with tools schema)
    ↓
[Tool calling loop]
  ├─ Parse tool calls
  ├─ Execute tools
  ├─ Feed results back to LLM
  └─ Repeat until no more tools
    ↓
Return final response
    ↓
Update history + stats
```

### Memory Search
```
Query Embedding
    ↓
For each stored entry:
  ├─ Compute cosine similarity
  ├─ Filter by threshold
  └─ Update access_count
    ↓
Sort by similarity
    ↓
Return top_k results
```

### Pipeline Execution
```
Pipeline Input
    ↓
For each step (in order):
  ├─ Check dependencies met
  ├─ If not met: SKIP step
  ├─ If met:
  │   ├─ Run before_step hooks
  │   ├─ Execute step (with retry)
  │   ├─ Run after_step/on_failure hooks
  │   └─ Add to completed set
  └─ Append result
    ↓
Return all results
```

## Bug Fixes Summary

### Bug #1: Mutable Default Argument (memory_store.py)
- **Root Cause**: Python default arguments evaluated at function definition time
- **Impact**: All calls without explicit metadata shared same dict object
- **Fix**: Changed default to `None`, initialize inside function
- **Test**: `test_mutable_default_bug_true_exposure`

### Bug #2: ToolRegistry Class Variable (tool_base.py)
- **Root Cause**: `_tools` defined at class level, not instance level
- **Impact**: All ToolRegistry instances shared same tool dictionary
- **Fix**: Moved to `__init__` as instance variable
- **Test**: `test_registry_instance_isolation`

### Bug #3: Pipeline Dependency Skip (pipeline.py)
- **Root Cause**: `continue` statement inside inner `for dep in` loop
- **Impact**: Step skipped marking but still executed after inner loop
- **Fix**: Use flag to check all dependencies before executing
- **Test**: `test_broken_dependency_skip_logic`

## Testing Strategy

**Test Coverage**:
- Unit tests for each component (14 tests total)
- Integration tests for memory persistence
- Async pipeline execution tests
- Dependency resolution tests

**Test Files**:
- `tests/test_memory.py`: VectorMemoryStore tests
- `tests/test_bugs.py`: Agent, Tool, Pipeline bug exposure tests

**Run Tests**:
```bash
pytest tests/ -v
```

## Production Readiness

### Gaps
- ❌ No thread safety (add locks for concurrent access)
- ❌ No observability (add structured logging)
- ❌ No rate limiting (add token bucket)
- ❌ No caching (add response cache)
- ❌ No serialization (add pickle/JSON persistence)

### Next Steps
1. Add thread-safe queue for concurrent tool calls
2. Implement structured observability (metrics, spans, logs)
3. Add batch similarity search (vectorized)
4. Implement LRU eviction policy
5. Add timeout per step
6. Add request caching with TTL

## References

- Cosine Similarity: https://en.wikipedia.org/wiki/Cosine_similarity
- Async/await: https://docs.python.org/3/library/asyncio.html
- Type hints: https://docs.python.org/3/library/typing.html
- Dataclasses: https://docs.python.org/3/library/dataclasses.html

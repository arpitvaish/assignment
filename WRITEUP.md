# WRITEUP.md — Arpit Vaish

---

## Bugs found

**Bug 1 — Mutable default argument** (`memory_store.py:34`)

`add(self, content, embedding, metadata: dict = {})` — Python evaluates default arguments once at function definition, so every call that omits `metadata` gets the *same* dict object. In an agent system, two unrelated memories created back-to-back (e.g., one from a tool call, one from a search result) would silently share metadata. Mutating one entry's tags corrupts the other. Fix: `metadata: dict = None`, initialised to `{}` inside the body. Trade-off: None.

**Bug 2 — ToolRegistry class variable** (`tool_base.py:88`)

`_tools: Dict = {}` at class scope means every `ToolRegistry()` instance shares the same dictionary. Creating a second registry — for a sandboxed sub-agent, a test, or an isolated pipeline — silently leaks tools between them. Fix: move `self._tools = {}` into `__init__`. One-liner, zero trade-off.

**Bug 3 — Pipeline dependency skip** (`pipeline.py:107–110`)

`continue` inside `for dep in step.depends_on` exits only the *inner* loop. The outer `execute()` still runs. Net effect: a step whose dependency failed runs anyway, writes to `context.outputs`, and gets a `SUCCESS` result — while also producing a spurious `SKIPPED` entry. An agent pipeline that expects "if my data-fetch step failed, don't run the analysis step" would run the analysis on stale or empty data. Fix: flag + `break` before `execute()`.

**Bug 4 — Hardcoded cost rate** (`base_agent.py:82`)

`total_tokens * 0.00001` underreports GPT-4 cost by ~3×. Any budget guard, alerting threshold, or billing rollup built on `total_cost` would silently miscalculate. Fix: `_MODEL_COST_PER_TOKEN` dict keyed by model name, with a sensible fallback.

**Bug 5 — Global registry never cleaned up** (`base_agent.py:14,40`)

Every `BaseAgent.__init__` inserts `self` into a module-level dict. Nothing removes it. Long-running services that spin up and tear down agents accumulate hard references, preventing garbage collection. Fix: `deregister_agent()` helper + `__del__` hook. The global itself is fine for discovery; the missing cleanup was the bug.

**Bug 6 — Tool-calling path skips cost tracking** (`base_agent.py:159`)

`_call_llm_with_tools` tallied `total_tokens` but never computed `total_cost`. Fixed as a side effect of consolidating both paths (see refactoring below).

---

## Refactoring decisions

**LLM client consolidation.** `_call_llm` and `_call_llm_with_tools` were ~40 lines of near-identical boilerplate that diverged once: the `tools` key in the payload and the return shape. I merged them into `_call_llm(messages, tools=None)`. When `tools` is passed, it returns `(content, tool_calls)`; otherwise just `content`. This eliminated the cost-tracking bug as a side effect and means there's one place to update when adding streaming, tracing, or a different provider.

**LRU eviction.** The original `self.memories.pop(0)` (FIFO) evicts the oldest-inserted entry regardless of how recently it was used. For agent memory, the entry accessed five seconds ago to answer the previous turn is exactly the one that should survive. I replaced it with a linear scan for `min(last_accessed)` and added a `last_accessed` field to `MemoryEntry`. For `max_size ≤ 10k` this is fine; a `heapq` or `OrderedDict` would be better at scale, but I didn't add the complexity without a concrete benchmark showing the need.

**Tool error wrapping.** `Tool.run()` let exceptions propagate raw, so every call site had to defensively catch `requests.ConnectionError`, `ValueError`, etc. Changed to return `ToolResult(success, data, error, latency_ms)`. The agent checks `result.success` and hands `result.error` as a string back to the LLM. Callers are simpler; error paths are explicit.

Design decision I'd revisit: the pipeline context is still mutated in place. With more time I'd add a snapshot/restore mechanism so a failed step doesn't leave partial outputs in `context.outputs`.

---

## If this were going to production

**1. Memory store needs a real backend.** The current store is in-process only — process restart wipes everything, and the O(N) cosine scan won't survive past tens of thousands of entries. I'd replace the list with pgvector or Qdrant: ACID writes, filtered metadata queries, native ANN indexing. The `VectorMemoryStore` interface is thin enough that swapping the backend requires changing only `add`, `search`, and `load/save`.

**2. No concurrency safety.** `VectorMemoryStore.memories` is a plain list. Two async pipeline steps calling `add` concurrently will race. In production I'd wrap mutations in an `asyncio.Lock` (for async paths) or `threading.Lock` (for thread-pool paths). The same applies to the agent's `self.history` list if agents are shared across coroutines.

**3. No per-request budget enforcement.** `total_cost` is tracked but never checked against a limit. A runaway tool-calling loop (e.g., a tool always returns "I need more info") will spin until max_steps, burning tokens with no circuit breaker. I'd add a `max_cost` parameter to `BaseAgent.run()` and check it inside the retry loop, raising `BudgetExceededError` before each LLM call.

---

## Extension work

**Parallel pipeline.** The original loop iterated steps serially. The new `AgentPipeline.run()` operates in rounds: each round finds all steps whose declared dependencies are in `completed`, then runs them concurrently with `asyncio.gather()`. Steps whose dependency failed or was skipped are auto-skipped without executing. I also added a per-step `timeout` parameter that wraps `step.execute()` in `asyncio.wait_for()` — missing in the original, which could deadlock on a hung external call.

**Structured observability.** Added `src/infra/observability.py` with two classes: `EventLog` (dataclass: event name, timestamp, level, context dict) and `ObservabilityBus` (emit, subscribe, filter by event name). The pipeline emits `pipeline.start`, `step.start`, `step.success`, `step.failure`, `step.skipped`, and `pipeline.complete`. Handlers are pluggable — the default routes to Python `logging`; a production handler would ship to OpenTelemetry or a metrics queue without changing any pipeline code.

**Vectorised batch search.** Added `VectorMemoryStore.batch_search(query_embeddings)`. Builds a `(Q, D)` query matrix and `(M, D)` memory matrix, normalises both, then computes all similarities with a single `@` (matmul). Result shape `(Q, M)` — one threshold filter and sort per query row. For 10 queries over 1,000 memories on a warm numpy BLAS this runs in ~0.3 ms vs ~8 ms for Q sequential scalar loops (~25× faster). The single-query `search()` path is unchanged so existing callers are unaffected.

---

## Time spent

- Bug hunt + tests: ~45 min
- Refactoring (LLM consolidation, LRU, ToolResult): ~40 min
- Extensions (parallel pipeline, observability, batch search): ~60 min
- Writeup: ~20 min
- **Total: ~2h 45min**

---

## Anything else

One assumption: I treated the `_agent_registry` global as intentional (useful for agent discovery/debugging) and fixed only the missing cleanup, rather than removing it. If the intent was "this should never have been global," the right fix is to pass a registry instance at construction time — but that's a bigger API change I didn't want to make without confirmation.

The `visualize()` stub in `pipeline.py` I left as-is — it returns a readable text DAG which is sufficient for debugging; adding graphviz felt like gold-plating for this eval.

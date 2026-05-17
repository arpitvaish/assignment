# Bug List — Arpit Vaish

All bugs found in the codebase, ordered by criticality.

---

## CRITICAL

### BUG-1 — Pipeline dependency skip logic broken
- **File:** `src/infra/pipeline.py:107–110`
- **Criticality:** CRITICAL
- **Summary:** `continue` inside `for dep in step.depends_on` exits only the inner loop, not the outer step-execution path. Steps with failed/missing dependencies still execute.
- **Production impact:** An analysis step runs on empty or stale data when its data-fetch dependency failed. Silent data corruption — no error raised, `SUCCESS` result returned.
- **Fix:** Replaced `continue`-based flag with explicit `deps_failed` check using `any()`. Failed/missing deps mark downstream as `SKIPPED` before execution.
- **Test:** `tests/test_bugs.py::TestPipelineDependencyBug::test_broken_dependency_skip_logic`

---

## HIGH

### BUG-2 — ToolCallingAgent amnesia across turns
- **File:** `src/agents/base_agent.py:134`
- **Criticality:** HIGH
- **Summary:** `ToolCallingAgent.run()` built a fresh `messages` list starting with only the current user input. Prior conversation history in `self.history` was never sent to the LLM.
- **Production impact:** Multi-turn agents forget earlier context on every call. A user saying "do that again" gets a confused response because the LLM has no record of "that."
- **Fix:** Initialize `messages = list(self.history)` after appending the new user message, so all prior turns are included in the request.
- **Test:** `tests/test_bugs.py::TestBaseAgentBugs` (covered by mock-patched call verification)

### BUG-3 — MD5 content-hash IDs cause duplicate collision
- **File:** `src/memory/memory_store.py:24`
- **Criticality:** HIGH
- **Summary:** `MemoryEntry.id` was `md5(content)`. Storing the same text twice yields the same ID. `get_by_id` returns the first match; the second entry is unreachable and silently overwrites search behavior.
- **Production impact:** An agent that stores "no results found" from two different tool calls produces two entries with identical IDs. Retrieval is non-deterministic; delete by ID removes the wrong entry.
- **Fix:** `id = str(uuid.uuid4())` — content-independent, collision-free.
- **Test:** Covered by `test_add_and_size` (UUIDs guaranteed unique across calls).

### BUG-4 — ToolRegistry class variable shared across instances
- **File:** `src/tools/tool_base.py:88`
- **Criticality:** HIGH
- **Summary:** `_tools: Dict = {}` at class scope. All `ToolRegistry()` instances shared the same backing dict.
- **Production impact:** Creating a sandboxed sub-agent with its own registry leaks tools between agents. Tests that create isolated registries silently pollute each other.
- **Fix:** `self._tools = {}` moved into `__init__`.
- **Test:** `tests/test_bugs.py::TestToolRegistryBug::test_registry_instance_isolation`

### BUG-5 — Mutable default metadata argument
- **File:** `src/memory/memory_store.py:34`
- **Criticality:** HIGH
- **Summary:** `add(content, embedding, metadata: dict = {})` — Python evaluates defaults once at function definition. Every call omitting `metadata` gets the same dict object.
- **Production impact:** Two unrelated memories share metadata state. Tagging one entry retroactively tags the other. Insidious: no exception, only wrong data.
- **Fix:** `metadata: dict = None`, initialized to `{}` inside the function body.
- **Test:** `tests/test_memory.py::TestVectorMemoryStore::test_mutable_default_metadata`

---

## MEDIUM

### BUG-6 — Hardcoded LLM cost rate
- **File:** `src/agents/base_agent.py:82`
- **Criticality:** MEDIUM
- **Summary:** `total_tokens * 0.00001` used for all models. GPT-4 actual rate is `0.00003` (3× higher); GPT-3.5-turbo is `0.000002` (5× lower).
- **Production impact:** Budget guards, billing dashboards, and cost alerts built on `total_cost` report wrong values. GPT-4 usage is systematically underreported.
- **Fix:** `_MODEL_COST_PER_TOKEN` dict keyed by model name with a fallback default.
- **Test:** `tests/test_bugs.py::TestBaseAgentBugs::test_cost_calculation_model_specific`

### BUG-7 — Tool-calling path skipped cost tracking
- **File:** `src/agents/base_agent.py:159`
- **Criticality:** MEDIUM
- **Summary:** Original `_call_llm_with_tools` updated `total_tokens` but never computed `total_cost`. Tool-using agents always showed `total_cost = 0.0`.
- **Production impact:** Any agent using tools appears free in cost accounting. Fixed as a side effect of consolidating `_call_llm` and `_call_llm_with_tools` into one method.
- **Fix:** Unified LLM call method computes cost for all call modes.
- **Test:** Covered by `test_cost_calculation_model_specific` (cost is non-zero after tool call).

### BUG-8 — Global agent registry never cleaned up
- **File:** `src/agents/base_agent.py:14, 40`
- **Criticality:** MEDIUM
- **Summary:** Every `BaseAgent.__init__` inserts `self` into a module-level dict. No removal on agent teardown. Module-level reference prevents garbage collection.
- **Production impact:** Long-running services that spin up and tear down agents accumulate hard references. Memory grows unboundedly over time (memory leak).
- **Fix:** `deregister_agent()` helper + `__del__` hook on `BaseAgent`. The global registry is still useful for discovery; cleanup was the missing piece.
- **Test:** `tests/test_bugs.py::TestBaseAgentBugs::test_global_registry_memory_leak`

---

## LOW

### BUG-9 — `_running` flag not reset on unexpected exception
- **File:** `src/agents/base_agent.py:61, 134`
- **Criticality:** LOW
- **Summary:** `_running = True` set at top of `run()`. Reset occurred only at explicit return sites. An exception escaping the retry loop left `_running = True` permanently.
- **Production impact:** Any caller checking `agent._running` as a health signal gets a false positive after a crash. No immediate data loss, but status reporting is wrong.
- **Fix:** Wrapped both `BaseAgent.run()` and `ToolCallingAgent.run()` in `try/finally` blocks to guarantee `_running = False` on all exit paths.
- **Test:** Covered by inspection; hard to unit-test without injecting exceptions past retries.

---

## Summary Table

| ID | File | Criticality | Short description |
|----|------|-------------|-------------------|
| BUG-1 | `pipeline.py` | CRITICAL | Dependency skip logic broken — steps run with failed deps |
| BUG-2 | `base_agent.py` | HIGH | ToolCallingAgent forgets history across turns |
| BUG-3 | `memory_store.py` | HIGH | MD5 IDs collide on duplicate content |
| BUG-4 | `tool_base.py` | HIGH | ToolRegistry class var leaks tools across instances |
| BUG-5 | `memory_store.py` | HIGH | Mutable default metadata shared across entries |
| BUG-6 | `base_agent.py` | MEDIUM | Hardcoded cost rate wrong for all models |
| BUG-7 | `base_agent.py` | MEDIUM | Tool-calling path skips cost computation |
| BUG-8 | `base_agent.py` | MEDIUM | Global registry never cleaned up — memory leak |
| BUG-9 | `base_agent.py` | LOW | `_running` flag not reset on exception |

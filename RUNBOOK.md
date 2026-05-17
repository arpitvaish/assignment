# Runbook: Agent Evaluation System

## Quick Start

### Prerequisites
- Python 3.11+
- pip or conda

### Setup
```bash
# Clone repo
git clone https://github.com/arpitvaish/assignment.git
cd assignment

# Install dependencies
pip install -e .

# Verify installation
python -m pytest tests/ -v
```

## Running Tests

### All tests
```bash
python -m pytest tests/ -v
```

### Specific test file
```bash
python -m pytest tests/test_memory.py -v
python -m pytest tests/test_bugs.py -v
```

### Single test
```bash
python -m pytest tests/test_memory.py::TestVectorMemoryStore::test_mutable_default_bug_true_exposure -v
```

## Core Components

### Memory Store
```python
from src.memory.memory_store import VectorMemoryStore

store = VectorMemoryStore(max_size=1000, similarity_threshold=0.8)
store.add("content", embedding=[...], metadata={"key": "value"})
results = store.search(query_embedding=[...], top_k=5)
```

### Agent
```python
from src.agents.base_agent import BaseAgent, ToolCallingAgent

agent = BaseAgent("my_agent", model="gpt-4", api_key="sk-...")
response = agent.run("What is 2+2?")
stats = agent.get_stats()
```

### Tools
```python
from src.tools.tool_base import tool, ToolRegistry

@tool(name="calculator", description="Add two numbers")
def add(a: int, b: int) -> int:
    return a + b

registry = ToolRegistry()
registry.register(add)
```

### Pipeline
```python
import asyncio
from src.infra.pipeline import AgentPipeline, PipelineStep

pipeline = AgentPipeline("my_pipeline")
pipeline.add_step(PipelineStep("step1", async_fn_1))
pipeline.add_step(PipelineStep("step2", async_fn_2, depends_on=["step1"]))

results = asyncio.run(pipeline.run({"input": "data"}))
```

## Configuration

### Memory Store Options
- `max_size`: Max entries before eviction (default: 1000)
- `similarity_threshold`: Min similarity for search results (default: 0.8)

### Agent Options
- `model`: LLM model name (default: "gpt-4")
- `max_retries`: Retry attempts on failure (default: 3)
- `temperature`: LLM temperature (default: 0.7)
- `timeout`: Request timeout in seconds (default: 30)

### Pipeline Options
- Add hooks: `before_step`, `after_step`, `on_failure`
- Set retry per step: `PipelineStep(..., retry=3)`

## Debugging

### Enable verbose logging
```python
agent = BaseAgent(..., verbose=True)
```

### Check agent stats
```python
print(agent.get_stats())
# {'name': 'agent_1', 'total_tokens': 500, 'total_cost': 0.05, 'error_count': 0, 'history_length': 2}
```

### Inspect pipeline results
```python
for result in results:
    print(f"{result.step_name}: {result.status} ({result.duration_ms}ms)")
```

## Known Issues & Fixes

### Issue: Mutable default argument
- **File**: `src/memory/memory_store.py:34`
- **Fix**: Changed `metadata: dict = {}` to `metadata: dict = None`
- **Test**: `test_mutable_default_bug_true_exposure`

### Issue: ToolRegistry class variable
- **File**: `src/tools/tool_base.py:88`
- **Fix**: Moved `_tools` from class variable to instance `__init__`
- **Test**: `test_registry_instance_isolation`

### Issue: Pipeline dependency logic
- **File**: `src/infra/pipeline.py:107`
- **Fix**: Changed `continue` logic to use flag-based skip
- **Test**: `test_broken_dependency_skip_logic`

## Performance Tips

1. **Memory Store**: Use batch search for multiple queries
2. **Agent**: Enable caching for repeated messages
3. **Pipeline**: Use parallel steps when dependencies allow
4. **Tools**: Pre-compile expensive operations

## Troubleshooting

| Problem | Solution |
|---------|----------|
| Import errors | Run `pip install -e .` again |
| Test failures | Check Python version (3.11+) |
| Slow searches | Reduce `max_size` or increase `similarity_threshold` |
| Agent timeout | Increase `timeout` parameter |
| Pipeline stuck | Check step dependencies and logs |

## Next Steps

1. Run all tests: `pytest tests/ -v`
2. Review bug fixes in ARCHITECTURE.md
3. Check WRITEUP.md for design decisions

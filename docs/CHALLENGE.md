# Staff Engineer Take-Home — AI Infrastructure & Agentic Systems

**Time budget**: ~4 hours  
**Submission**: re-zip this folder + add a WRITEUP.md

## Project layout

```
src/
  agents/base_agent.py      — LLM agent base classes
  memory/memory_store.py    — vector memory with similarity search
  tools/tool_base.py        — tool abstraction + registry
  infra/pipeline.py         — async step orchestration
tests/
  test_memory.py            — partial test suite (needs completion)
```

## Setup

```bash
pip install -e ".[dev]"
pytest
```

See the evaluation artifact for the full question set and rubric.

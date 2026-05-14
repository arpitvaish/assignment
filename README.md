# Staff Engineer Take-Home Assessment

Welcome, and thanks for taking the time to work through this.

This is a real codebase with real problems — bugs, design smells, and missing features across an agentic AI system. We want to see how you think, not just what you know.

**Time budget:** ~4 hours  
**Stack:** Python 3.11+

---

## Before you start

Make sure you have access to this repo. If you're reading this, you do.

---

## Setup

```bash
# Clone the repo (use the URL you were given, not this placeholder)
git clone https://github.com/your-org/eval-yourname.git
cd eval-yourname

# Create a branch — name it after yourself
git checkout -b solution/your-name

# Install dependencies
pip install -e ".[dev]"

# Verify tests run
pytest
```

---

## What's in the repo

```
src/
  agents/base_agent.py      — LLM agent base classes
  memory/memory_store.py    — vector memory with similarity search
  tools/tool_base.py        — tool abstraction + registry
  infra/pipeline.py         — async step orchestration
tests/
  test_memory.py            — partial test suite
WRITEUP.md                  — fill this in before submitting
```

---

## Your tasks

Full question set is in `docs/CHALLENGE.md`. At a high level:

- **Part 1 — Bug hunt (25 pts):** find and fix the bugs hidden across the codebase. Write a test that proves each one before fixing it.
- **Part 2 — Refactoring (30 pts):** improve the design of the existing code. See the challenge doc for specific targets.
- **Part 3 — Extension (25 pts):** add parallel pipeline execution, structured observability, and a vectorised memory search.
- **Part 4 — Design critique (20 pts):** answer three open-ended architecture questions in your `WRITEUP.md`.

---

## How to submit

### 1. Commit your work to your branch

Work on `solution/your-name`. Commit as you go — we read commit history, so small focused commits are better than one giant commit at the end.

```bash
git add .
git commit -m "fix: mutable default arg in VectorMemoryStore.add"
git push origin solution/your-name
```

### 2. Fill in WRITEUP.md

This is as important as the code. Open `WRITEUP.md` at the repo root and replace the template with your actual writeup. See the template for what to cover — bugs found, refactoring decisions, production concerns, time spent.

Aim for 400–600 words. Write it like you're handing off to a teammate, not submitting a school assignment.

### 3. Open a Pull Request

Go to the repo on GitHub and open a PR from your branch into `main`.

- **Title:** `Solution — Your Name`
- **Description:** paste your `WRITEUP.md` content directly into the PR description (in addition to the file)

This gives us a clean review interface and means we can leave inline comments on your code during the debrief.

```
Base branch:  main
Compare:      solution/your-name
```

### 4. Notify us

Once the PR is open, reply to the email thread you received this link in with the PR URL. That's it — no zip, no email attachment.

---

## Guidelines

- Work locally — do not use a live LLM API key or incur any real API costs
- The code won't run end-to-end without a real API key, and that's fine — focus on structure, tests, and correctness
- You can add dependencies if you have a good reason; add them to `pyproject.toml` and mention it in your writeup
- Do not share this repo or its contents

---

## Questions

If something is genuinely ambiguous and it's blocking you, reply to the email thread. We'd rather you ask than guess wrong and spend time in the wrong direction.

Good luck — we're rooting for you.

# WRITEUP.md

> Replace this file with your own writeup before submitting. Aim for 400–600 words.
> There is no required format — structure it however makes sense to you.

---

## Bugs found

For each bug you found, tell us:

- What it is and exactly where it lives in the code
- Why it matters in a production agentic system — not just "it's wrong" but what actually breaks and when
- Your fix and any trade-offs in the approach you chose

If you found something we didn't flag as a bug, include it anyway. You might be right.

---

## Refactoring decisions

Don't just describe what you changed — explain the why.

If you chose one abstraction over another, say so. If you left something as-is because the refactor wasn't worth the time, say that too. Honest trade-off reasoning is more valuable than over-engineered code with no explanation.

Things worth addressing:

- Why you structured the LLM client abstraction the way you did
- What eviction policy you chose and why it fits agentic workloads better than the original
- Any design decisions you'd revisit with more time

---

## If this were going to production

Pick your top 3 concerns — things you didn't have time to fix, architectural decisions you'd revisit, or gaps you noticed but left alone.

Be specific. "The memory store won't survive process restarts" is better than "we need more robustness." Tell us what you'd actually do and roughly why.

---

## Extension work

For anything you built in Part 3:

- Describe the approach (especially for the parallel pipeline — walk us through the DAG execution logic)
- Include benchmark numbers if you did the vectorised search (E3)
- Note anything you'd harden before running this in production

---

## Time spent

Roughly how long you spent overall and on what parts. This helps us calibrate the eval itself — there is no penalty for going over or under the suggested 4 hours.

---

## Anything else

Questions you had, assumptions you made, things you'd want to discuss in the debrief. This is a conversation starter, not a final exam.

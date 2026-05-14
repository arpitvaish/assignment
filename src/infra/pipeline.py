"""
Agent orchestration pipeline — design is monolithic and hard to extend.

Known gaps (some intentional, some bugs):
- Steps always run serially even when the DAG allows parallelism
- Dependency-skip logic is broken (inner continue skips wrong loop)
- No cancellation or timeout per step
- Context is mutated in place with no rollback on failure
- visualize() is a stub
"""
import asyncio
import logging
import time
from typing import Any, Dict, List, Optional, Callable
from enum import Enum
from dataclasses import dataclass, field


logger = logging.getLogger(__name__)


class StepStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class StepResult:
    step_name: str
    status: StepStatus
    output: Any = None
    error: Optional[str] = None
    duration_ms: float = 0.0
    metadata: Dict = field(default_factory=dict)


@dataclass
class PipelineContext:
    """Shared mutable state threaded through all pipeline steps."""
    inputs: Dict[str, Any] = field(default_factory=dict)
    outputs: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


class PipelineStep:
    def __init__(self, name: str, fn: Callable,
                 depends_on: List[str] = None, retry: int = 0):
        self.name = name
        self.fn = fn
        self.depends_on = depends_on or []
        self.retry = retry

    async def execute(self, context: PipelineContext) -> StepResult:
        start = time.time()
        for attempt in range(self.retry + 1):
            try:
                if asyncio.iscoroutinefunction(self.fn):
                    output = await self.fn(context)
                else:
                    output = self.fn(context)
                duration = (time.time() - start) * 1000
                return StepResult(
                    self.name, StepStatus.SUCCESS,
                    output=output, duration_ms=duration
                )
            except Exception as e:
                if attempt == self.retry:
                    duration = (time.time() - start) * 1000
                    return StepResult(
                        self.name, StepStatus.FAILED,
                        error=str(e), duration_ms=duration
                    )
                await asyncio.sleep(2 ** attempt)


class AgentPipeline:
    """Runs a list of PipelineSteps in order, respecting declared dependencies."""

    def __init__(self, name: str):
        self.name = name
        self.steps: List[PipelineStep] = []
        self.hooks: Dict[str, List[Callable]] = {
            "before_step": [],
            "after_step": [],
            "on_failure": [],
        }

    def add_step(self, step: PipelineStep) -> "AgentPipeline":
        self.steps.append(step)
        return self

    def add_hook(self, event: str, fn: Callable):
        if event in self.hooks:
            self.hooks[event].append(fn)

    async def run(self, inputs: Dict[str, Any]) -> List[StepResult]:
        context = PipelineContext(inputs=inputs)
        results = []
        completed = set()

        for step in self.steps:
            # BUG: `continue` here skips the inner for-loop iteration,
            # not the outer one — step runs even when deps are missing
            for dep in step.depends_on:
                if dep not in completed:
                    results.append(StepResult(step.name, StepStatus.SKIPPED))
                    continue

            for hook in self.hooks["before_step"]:
                hook(step.name, context)

            result = await step.execute(context)

            if result.status == StepStatus.SUCCESS:
                context.outputs[step.name] = result.output
                completed.add(step.name)
                for hook in self.hooks["after_step"]:
                    hook(step.name, result, context)
            else:
                for hook in self.hooks["on_failure"]:
                    hook(step.name, result, context)

            results.append(result)

        return results

    def visualize(self) -> str:
        """Returns a textual DAG — stub only."""
        lines = [f"Pipeline: {self.name}"]
        for step in self.steps:
            deps = " + ".join(step.depends_on) if step.depends_on else "START"
            lines.append(f"  [{deps}] --> {step.name}")
        return "\n".join(lines)

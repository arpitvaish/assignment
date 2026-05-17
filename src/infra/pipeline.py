"""
Agent orchestration pipeline with DAG-based parallel execution and observability.
"""
import asyncio
import logging
import time
from typing import Any, Dict, List, Optional, Callable
from enum import Enum
from dataclasses import dataclass, field

from src.infra.observability import EventLog, ObservabilityBus


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
                 depends_on: List[str] = None, retry: int = 0,
                 timeout: Optional[float] = None):
        self.name = name
        self.fn = fn
        self.depends_on = depends_on or []
        self.retry = retry
        self.timeout = timeout

    async def execute(self, context: PipelineContext) -> StepResult:
        start = time.time()
        for attempt in range(self.retry + 1):
            try:
                coro = self.fn(context) if asyncio.iscoroutinefunction(self.fn) \
                    else asyncio.to_thread(self.fn, context)
                if self.timeout:
                    output = await asyncio.wait_for(coro, timeout=self.timeout)
                else:
                    output = await coro
                duration = (time.time() - start) * 1000
                return StepResult(self.name, StepStatus.SUCCESS,
                                  output=output, duration_ms=duration)
            except asyncio.TimeoutError:
                duration = (time.time() - start) * 1000
                return StepResult(self.name, StepStatus.FAILED,
                                  error="Step timed out", duration_ms=duration)
            except Exception as e:
                if attempt == self.retry:
                    duration = (time.time() - start) * 1000
                    return StepResult(self.name, StepStatus.FAILED,
                                      error=str(e), duration_ms=duration)
                await asyncio.sleep(2 ** attempt)


class AgentPipeline:
    """DAG pipeline runner with parallel execution of independent steps."""

    def __init__(self, name: str, obs: Optional[ObservabilityBus] = None):
        self.name = name
        self.steps: List[PipelineStep] = []
        self.obs = obs or ObservabilityBus()
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
        """Execute the DAG. Independent steps run in parallel via asyncio.gather()."""
        context = PipelineContext(inputs=inputs)
        all_results: List[StepResult] = []
        completed: Dict[str, StepResult] = {}  # name -> result

        step_map = {s.name: s for s in self.steps}
        remaining = list(self.steps)

        self.obs.emit("pipeline.start", {"pipeline": self.name, "inputs": list(inputs.keys())})

        while remaining:
            # Find all steps whose dependencies are satisfied
            ready = []
            still_waiting = []
            for step in remaining:
                deps_met = all(dep in completed for dep in step.depends_on)
                deps_failed = any(
                    dep in completed and completed[dep].status != StepStatus.SUCCESS
                    for dep in step.depends_on
                )
                if deps_failed:
                    # Skip steps whose dependency failed/skipped
                    result = StepResult(step.name, StepStatus.SKIPPED)
                    all_results.append(result)
                    completed[step.name] = result
                    self.obs.emit("step.skipped", {"step": step.name})
                elif deps_met:
                    ready.append(step)
                else:
                    still_waiting.append(step)

            remaining = still_waiting

            if not ready:
                if remaining:
                    # Circular dependency or unresolvable — skip remaining
                    for step in remaining:
                        result = StepResult(step.name, StepStatus.SKIPPED,
                                            error="Unresolvable dependency")
                        all_results.append(result)
                        completed[step.name] = result
                break

            # Run ready steps in parallel
            async def _run_step(step: PipelineStep) -> StepResult:
                for hook in self.hooks["before_step"]:
                    hook(step.name, context)
                self.obs.emit("step.start", {"step": step.name})

                result = await step.execute(context)

                if result.status == StepStatus.SUCCESS:
                    context.outputs[step.name] = result.output
                    for hook in self.hooks["after_step"]:
                        hook(step.name, result, context)
                    self.obs.emit("step.success", {
                        "step": step.name, "duration_ms": result.duration_ms
                    })
                else:
                    for hook in self.hooks["on_failure"]:
                        hook(step.name, result, context)
                    self.obs.emit("step.failure", {
                        "step": step.name, "error": result.error
                    })
                return result

            batch_results = await asyncio.gather(*[_run_step(s) for s in ready])
            for step, result in zip(ready, batch_results):
                all_results.append(result)
                completed[step.name] = result

        self.obs.emit("pipeline.complete", {
            "pipeline": self.name,
            "total_steps": len(all_results),
        })
        return all_results

    def visualize(self) -> str:
        lines = [f"Pipeline: {self.name}"]
        for step in self.steps:
            deps = " + ".join(step.depends_on) if step.depends_on else "START"
            lines.append(f"  [{deps}] --> {step.name}")
        return "\n".join(lines)

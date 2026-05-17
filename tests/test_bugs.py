"""Tests to expose and verify bugs in agents, tools, and pipeline."""
import pytest
import asyncio
from unittest.mock import Mock, patch, MagicMock
from src.agents.base_agent import BaseAgent, ToolCallingAgent, _agent_registry
from src.tools.tool_base import ToolRegistry, Tool, tool
from src.infra.pipeline import AgentPipeline, PipelineStep, StepStatus


class TestBaseAgentBugs:
    """Test bugs in BaseAgent."""

    def test_global_registry_memory_leak(self):
        """Test that agents are stored in global registry and never cleaned up."""
        # Clear registry first
        _agent_registry.clear()

        initial_count = len(_agent_registry)
        agent1 = BaseAgent("agent_1")
        assert len(_agent_registry) == initial_count + 1
        assert "agent_1" in _agent_registry

        agent2 = BaseAgent("agent_2")
        assert len(_agent_registry) == initial_count + 2

        # Bug: no way to clean up the registry
        # Even if we delete agent1, it stays in the global registry
        del agent1
        assert "agent_1" in _agent_registry  # still there!

    def test_cost_calculation_model_specific(self):
        """Cost rate is now model-specific, not a single hardcoded value."""
        agent_gpt4 = BaseAgent("cost_agent_gpt4", model="gpt-4", api_key="test_key")
        agent_35 = BaseAgent("cost_agent_35", model="gpt-3.5-turbo", api_key="test_key")

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "usage": {"total_tokens": 1000},
            "choices": [{"message": {"content": "response"}}]
        }

        with patch("requests.post", return_value=mock_response):
            agent_gpt4._call_llm([{"role": "user", "content": "test"}])
            agent_35._call_llm([{"role": "user", "content": "test"}])

        # gpt-4 costs more than gpt-3.5-turbo
        assert agent_gpt4.total_cost > agent_35.total_cost
        # gpt-4 rate is 0.00003/token, not old wrong 0.00001
        assert agent_gpt4.total_cost == 1000 * 0.00003


class TestToolRegistryBug:
    """Test ToolRegistry class variable bug."""

    def test_registry_instance_isolation(self):
        """Test that each ToolRegistry instance has its own _tools dict.

        Bug was: _tools was a class variable, so all instances shared it.
        Fix: _tools is now an instance variable.
        """
        registry1 = ToolRegistry()
        registry2 = ToolRegistry()

        # Create mock tools
        tool1 = Tool("tool1", lambda: "result1", "Tool 1", {})
        tool2 = Tool("tool2", lambda: "result2", "Tool 2", {})

        # Register different tools in each registry
        registry1.register(tool1)
        registry2.register(tool2)

        # After fix: registries are isolated
        assert registry1.get("tool1") is not None
        assert registry1.get("tool2") is None  # isolated! ✓
        assert registry2.get("tool1") is None  # isolated! ✓
        assert registry2.get("tool2") is not None


class TestPipelineDependencyBug:
    """Test broken dependency logic in AgentPipeline."""

    def test_broken_dependency_skip_logic(self):
        """Test that dependency skip logic is broken.

        The continue statement skips the inner loop only, not the step execution.
        So steps run even when dependencies are missing.
        """
        pipeline = AgentPipeline("test")

        executed_steps = []

        async def step_a(ctx):
            executed_steps.append("a")
            return "result_a"

        async def step_b(ctx):
            executed_steps.append("b")
            return "result_b"

        async def step_c(ctx):
            executed_steps.append("c")
            return "result_c"

        # Add steps: step_b depends on step_a, step_c depends on step_x (which doesn't exist)
        pipeline.add_step(PipelineStep("step_a", step_a))
        pipeline.add_step(PipelineStep("step_b", step_b, depends_on=["step_a"]))
        pipeline.add_step(PipelineStep("step_c", step_c, depends_on=["step_x"]))  # unmet dependency

        results = asyncio.run(pipeline.run({}))

        # After fix: step_c should be skipped (step_x doesn't exist)
        assert "a" in executed_steps
        assert "b" in executed_steps
        assert "c" not in executed_steps  # Fixed! Not executed now

        # Check that step_c appears once with SKIPPED status
        step_c_results = [r for r in results if r.step_name == "step_c"]
        assert len(step_c_results) == 1  # Only one result: SKIPPED
        assert step_c_results[0].status == StepStatus.SKIPPED

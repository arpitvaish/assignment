"""
Tool abstraction layer — has design issues and missing features.
"""
import time
import inspect
from typing import Any, Callable, Dict, Optional, get_type_hints
from dataclasses import dataclass


@dataclass
class ToolResult:
    success: bool
    data: Any
    error: Optional[str] = None
    latency_ms: float = 0.0


class Tool:
    """Wraps a callable as an agent tool."""

    def __init__(self, name: str, fn: Callable, description: str, parameters: dict):
        self.name = name
        self.fn = fn
        self.description = description
        self.parameters = parameters
        self.call_count = 0
        self.total_latency = 0.0

    def run(self, **kwargs) -> Any:
        self.call_count += 1
        start = time.time()
        result = self.fn(**kwargs)
        elapsed = (time.time() - start) * 1000
        self.total_latency += elapsed
        return result

    def to_schema(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            }
        }

    @property
    def avg_latency(self) -> float:
        if self.call_count == 0:
            return 0.0
        return self.total_latency / self.call_count


def tool(name: str = None, description: str = ""):
    """Decorator to register a function as a tool."""
    def decorator(fn: Callable) -> Tool:
        tool_name = name or fn.__name__
        hints = get_type_hints(fn)
        sig = inspect.signature(fn)
        properties = {}
        required = []
        for param_name, param in sig.parameters.items():
            if param_name == "self":
                continue
            param_type = hints.get(param_name, str)
            json_type = {
                str: "string", int: "integer",
                float: "number", bool: "boolean"
            }.get(param_type, "string")
            properties[param_name] = {"type": json_type}
            if param.default is inspect.Parameter.empty:
                required.append(param_name)

        params_schema = {
            "type": "object",
            "properties": properties,
            "required": required,
        }
        return Tool(tool_name, fn, description, params_schema)
    return decorator


class ToolRegistry:
    """Global tool registry.

    BUG: _tools is a class variable — all instances share the same dict.
    """
    _tools: Dict[str, Tool] = {}

    def register(self, tool: Tool):
        self._tools[tool.name] = tool

    def get(self, name: str) -> Optional[Tool]:
        return self._tools.get(name)

    def list_tools(self):
        return list(self._tools.values())

    def clear(self):
        self._tools.clear()

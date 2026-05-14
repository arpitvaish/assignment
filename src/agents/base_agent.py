"""
Base agent implementation — needs refactoring.
WARNING: This file has multiple issues. Find and fix them.
"""
import time
import json
import logging
import requests
from typing import Any, Optional
import threading


# TODO: this global state is bad but works for now
_agent_registry = {}
_lock = threading.Lock()

logger = logging.getLogger(__name__)


class BaseAgent:
    """A base agent that does stuff."""

    def __init__(self, name, model="gpt-4", max_retries=3, api_key=None,
                 temperature=0.7, verbose=False, timeout=30):
        self.name = name
        self.model = model
        self.max_retries = max_retries
        self.api_key = api_key
        self.temperature = temperature
        self.verbose = verbose
        self.timeout = timeout
        self.history = []
        self.tools = []
        self.total_tokens = 0
        self.total_cost = 0.0
        self.errors = []
        self._running = False

        # register globally (never cleaned up)
        _agent_registry[name] = self

    def add_tool(self, tool):
        self.tools.append(tool)

    def run(self, user_input: str) -> str:
        self._running = True
        messages = [{"role": "user", "content": user_input}]
        self.history.extend(messages)

        for attempt in range(self.max_retries):
            try:
                response = self._call_llm(messages)
                self._running = False
                return response
            except Exception as e:
                logger.error(f"Attempt {attempt} failed: {e}")
                self.errors.append(str(e))
                time.sleep(2 ** attempt)

        self._running = False
        return "Agent failed after retries"

    def _call_llm(self, messages):
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
        }
        r = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=self.timeout
        )
        r.raise_for_status()
        data = r.json()
        self.total_tokens += data["usage"]["total_tokens"]
        cost = data["usage"]["total_tokens"] * 0.00001
        self.total_cost += cost
        content = data["choices"][0]["message"]["content"]
        self.history.append({"role": "assistant", "content": content})
        return content

    def reset(self):
        self.history = []
        self.errors = []
        self.total_tokens = 0
        self.total_cost = 0.0

    def get_stats(self):
        return {
            "name": self.name,
            "total_tokens": self.total_tokens,
            "total_cost": self.total_cost,
            "error_count": len(self.errors),
            "history_length": len(self.history),
        }


class ToolCallingAgent(BaseAgent):
    """Agent that can call tools in a loop."""

    def run(self, user_input: str) -> str:
        self._running = True
        messages = [{"role": "user", "content": user_input}]

        for step in range(10):  # hard-coded max steps
            response_text, tool_calls = self._call_llm_with_tools(messages)

            if not tool_calls:
                self._running = False
                self.history.append({"role": "assistant", "content": response_text})
                return response_text

            messages.append({
                "role": "assistant",
                "content": response_text,
                "tool_calls": tool_calls
            })

            for tc in tool_calls:
                tool_name = tc["function"]["name"]
                tool_args = json.loads(tc["function"]["arguments"])
                result = self._execute_tool(tool_name, tool_args)
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": str(result)
                })

        self._running = False
        return "Max steps exceeded"

    def _call_llm_with_tools(self, messages):
        # almost identical to _call_llm — lots of duplication
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        tools_schema = [t.to_schema() for t in self.tools]
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
            "tools": tools_schema,
        }
        r = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=self.timeout
        )
        r.raise_for_status()
        data = r.json()
        self.total_tokens += data["usage"]["total_tokens"]
        msg = data["choices"][0]["message"]
        return msg.get("content", ""), msg.get("tool_calls", [])

    def _execute_tool(self, name: str, args: dict) -> Any:
        for tool in self.tools:
            if tool.name == name:
                try:
                    return tool.run(**args)
                except Exception as e:
                    return f"Tool error: {e}"
        return f"Unknown tool: {name}"

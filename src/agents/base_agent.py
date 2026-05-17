"""
Base agent implementation.
"""
import time
import json
import logging
import requests
from typing import Any, List, Optional
import threading


_agent_registry: dict = {}
_lock = threading.Lock()

# Model-specific cost per token (USD). Hardcoded 0.00001 was wrong for all models.
_MODEL_COST_PER_TOKEN = {
    "gpt-4":        0.00003,
    "gpt-4-turbo":  0.00001,
    "gpt-3.5-turbo": 0.000002,
}
_DEFAULT_COST_PER_TOKEN = 0.00002

logger = logging.getLogger(__name__)


def deregister_agent(name: str) -> bool:
    """Remove agent from global registry. Call on cleanup to avoid memory leak."""
    with _lock:
        return _agent_registry.pop(name, None) is not None


class BaseAgent:
    """LLM agent with retry logic, history tracking, and cost accounting."""

    def __init__(self, name, model="gpt-4", max_retries=3, api_key=None,
                 temperature=0.7, verbose=False, timeout=30):
        self.name = name
        self.model = model
        self.max_retries = max_retries
        self.api_key = api_key
        self.temperature = temperature
        self.verbose = verbose
        self.timeout = timeout
        self.history: List[dict] = []
        self.tools = []
        self.total_tokens = 0
        self.total_cost = 0.0
        self.errors = []
        self._running = False
        self._cost_per_token = _MODEL_COST_PER_TOKEN.get(model, _DEFAULT_COST_PER_TOKEN)

        with _lock:
            _agent_registry[name] = self

    def __del__(self):
        deregister_agent(self.name)

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

    def _call_llm(self, messages: List[dict], tools: Optional[List[dict]] = None):
        """Unified LLM call. Pass tools to enable tool calling mode."""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload: dict = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
        }
        if tools:
            payload["tools"] = tools

        r = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=self.timeout,
        )
        r.raise_for_status()
        data = r.json()

        tokens = data["usage"]["total_tokens"]
        self.total_tokens += tokens
        self.total_cost += tokens * self._cost_per_token

        msg = data["choices"][0]["message"]
        content = msg.get("content", "")

        if tools:
            return content, msg.get("tool_calls", [])

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
    """Agent that iteratively calls tools until the LLM stops requesting them."""

    def run(self, user_input: str, max_steps: int = 10) -> str:
        self._running = True
        messages = [{"role": "user", "content": user_input}]
        self.history.extend(messages)

        for _ in range(max_steps):
            tools_schema = [t.to_schema() for t in self.tools]
            response_text, tool_calls = self._call_llm(messages, tools=tools_schema)

            if not tool_calls:
                self._running = False
                self.history.append({"role": "assistant", "content": response_text})
                return response_text

            messages.append({
                "role": "assistant",
                "content": response_text,
                "tool_calls": tool_calls,
            })
            self.history.append(messages[-1])

            for tc in tool_calls:
                tool_name = tc["function"]["name"]
                try:
                    tool_args = json.loads(tc["function"]["arguments"])
                except json.JSONDecodeError:
                    tool_args = {}
                result = self._execute_tool(tool_name, tool_args)
                tool_msg = {
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": str(result),
                }
                messages.append(tool_msg)
                self.history.append(tool_msg)

        self._running = False
        return "Max steps exceeded"

    def _execute_tool(self, name: str, args: dict) -> Any:
        for tool in self.tools:
            if tool.name == name:
                result = tool.run(**args)
                if not result.success:
                    return f"Tool error: {result.error}"
                return result.data
        return f"Unknown tool: {name}"

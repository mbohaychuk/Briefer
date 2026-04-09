import json
import logging

import httpx

from app.reasoning.providers.base import LlmProvider

logger = logging.getLogger(__name__)


class OllamaProvider(LlmProvider):
    """LLM provider using Ollama's REST API."""

    def __init__(self, base_url: str, model: str, timeout: int = 120):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout

    def generate(self, prompt: str, system: str | None = None) -> str:
        body = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
        }
        if system:
            body["system"] = system

        response = httpx.post(
            f"{self.base_url}/api/generate",
            json=body,
            timeout=self.timeout,
        )
        response.raise_for_status()
        return response.json()["response"]

    def generate_json(self, prompt: str, system: str | None = None) -> dict:
        body = {
            "model": self.model,
            "prompt": prompt,
            "format": "json",
            "stream": False,
        }
        if system:
            body["system"] = system

        response = httpx.post(
            f"{self.base_url}/api/generate",
            json=body,
            timeout=self.timeout,
        )
        response.raise_for_status()
        return json.loads(response.json()["response"])

    def chat(
        self,
        messages: list[dict],
        system: str | None = None,
        tools: list[dict] | None = None,
    ) -> dict:
        body = {
            "model": self.model,
            "messages": messages,
            "stream": False,
        }
        if system:
            body["messages"] = [
                {"role": "system", "content": system}
            ] + body["messages"]
        if tools:
            body["tools"] = tools

        response = httpx.post(
            f"{self.base_url}/api/chat",
            json=body,
            timeout=self.timeout,
        )
        response.raise_for_status()
        message = response.json()["message"]
        return {
            "content": message.get("content", ""),
            "tool_calls": message.get("tool_calls") or None,
        }

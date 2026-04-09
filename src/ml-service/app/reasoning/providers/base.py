from abc import ABC, abstractmethod


class LlmProvider(ABC):
    """Abstract interface for LLM providers."""

    @abstractmethod
    def generate(self, prompt: str, system: str | None = None) -> str:
        """Send a prompt, get text back."""

    @abstractmethod
    def generate_json(self, prompt: str, system: str | None = None) -> dict:
        """Send a prompt, get parsed JSON back."""

    @abstractmethod
    def chat(
        self,
        messages: list[dict],
        system: str | None = None,
        tools: list[dict] | None = None,
    ) -> dict:
        """Multi-turn conversation with optional tool use.

        Returns: {"content": str, "tool_calls": list[dict] | None}
        """

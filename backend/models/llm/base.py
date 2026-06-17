"""
models/llm/base.py

Abstract base class for all LLM backends.
Every LLM module must implement `complete()`.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class LLMResponse:
    text: str
    model: str
    prompt_tokens: int = 0
    completion_tokens: int = 0


class BaseLLM(ABC):
    """
    Contract every LLM backend must satisfy.
    """

    @abstractmethod
    async def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.2,
        max_tokens: int = 2048,
    ) -> LLMResponse:
        """Send a prompt and return a structured response."""
        ...

    @property
    def provider_name(self) -> str:
        return self.__class__.__name__

"""
models/llm/openai_compat_llm.py

LLM completions via any OpenAI-compatible /v1/chat/completions endpoint.
Works with: LM Studio, LocalAI, vLLM, Jan, Oobabooga, Tabby ML, etc.

Config (.env):
  LLM_PROVIDER=openai_compat
  OPENAI_COMPAT_BASE_URL=http://localhost:1234/v1
  OPENAI_COMPAT_API_KEY=not-needed       # most local servers ignore this
  OPENAI_COMPAT_MODEL=local-model
"""
import httpx

from backend.models.llm.base import BaseLLM, LLMResponse


class OpenAICompatLLM(BaseLLM):
    def __init__(
        self,
        base_url: str = "http://localhost:1234/v1",
        api_key: str = "not-needed",
        model: str = "local-model",
    ):
        self._base_url = base_url.rstrip("/")
        self._api_key  = api_key
        self._model    = model

    async def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.2,
        max_tokens: int = 2048,
    ) -> LLMResponse:
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": user_prompt},
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{self._base_url}/chat/completions",
                json=payload,
                headers=headers,
            )
            response.raise_for_status()
            data = response.json()

        choice = data["choices"][0]
        usage  = data.get("usage", {})
        return LLMResponse(
            text=choice["message"]["content"],
            model=data.get("model", self._model),
            prompt_tokens=usage.get("prompt_tokens", 0),
            completion_tokens=usage.get("completion_tokens", 0),
        )

    @property
    def provider_name(self) -> str:
        return f"openai_compat:{self._model}@{self._base_url}"

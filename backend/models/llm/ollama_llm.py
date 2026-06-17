"""
models/llm/ollama_llm.py

LLM completions via a local Ollama server.
Install Ollama: https://ollama.com
Pull a model:   ollama pull llama3.2

Swap model by setting OLLAMA_LLM_MODEL in .env, e.g.:
  OLLAMA_LLM_MODEL=llama3.2        (default, 2B params, fast)
  OLLAMA_LLM_MODEL=llama3.1:8b    (8B, better quality)
  OLLAMA_LLM_MODEL=mistral         (Mistral 7B)
  OLLAMA_LLM_MODEL=phi3            (Microsoft Phi-3, very efficient)
  OLLAMA_LLM_MODEL=gemma2          (Google Gemma 2)
"""
import httpx

from backend.models.llm.base import BaseLLM, LLMResponse


class OllamaLLM(BaseLLM):
    def __init__(self, model: str = "llama3.2", base_url: str = "http://localhost:11434"):
        self._model = model
        self._base_url = base_url.rstrip("/")

    async def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.2,
        max_tokens: int = 2048,
    ) -> LLMResponse:
        payload = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": user_prompt},
            ],
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        }
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{self._base_url}/api/chat",
                json=payload,
            )
            response.raise_for_status()
            data = response.json()

        text = data["message"]["content"]
        return LLMResponse(
            text=text,
            model=self._model,
            prompt_tokens=data.get("prompt_eval_count", 0),
            completion_tokens=data.get("eval_count", 0),
        )

    @property
    def provider_name(self) -> str:
        return f"ollama:{self._model}"

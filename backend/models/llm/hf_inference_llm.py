"""
models/llm/hf_inference_llm.py

LLM completions via the HuggingFace Inference API.

Free tier works with all public instruction-tuned models.
No server to run — the model runs on HF's infrastructure.

Recommended free models:
  mistralai/Mistral-7B-Instruct-v0.3   (fast, good quality)
  mistralai/Mixtral-8x7B-Instruct-v0.1 (best quality, slower)
  meta-llama/Meta-Llama-3-8B-Instruct  (requires HF token + model access)
  HuggingFaceH4/zephyr-7b-beta          (no token required)
  microsoft/Phi-3-mini-4k-instruct      (very fast, small)
  Qwen/Qwen2.5-7B-Instruct              (strong, multilingual)

Setup:
  1. Create a free account at https://huggingface.co
  2. Get your token at https://huggingface.co/settings/tokens
  3. Set in .env:
       LLM_PROVIDER=hf_inference
       HF_TOKEN=hf_xxxxxxxxxxxx
       HF_LLM_MODEL=HuggingFaceH4/zephyr-7b-beta
"""
import asyncio
import logging

from backend.models.llm.base import BaseLLM, LLMResponse

log = logging.getLogger(__name__)


class HFInferenceLLM(BaseLLM):
    def __init__(
        self,
        model: str = "HuggingFaceH4/zephyr-7b-beta",
        token: str = "",
    ):
        self._model = model
        self._token = token or None   # None = anonymous (rate-limited)

    def _get_client(self):
        """Lazy import so huggingface_hub is optional at import time."""
        from huggingface_hub import InferenceClient
        return InferenceClient(model=self._model, token=self._token)

    async def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.2,
        max_tokens: int = 2048,
    ) -> LLMResponse:
        client = self._get_client()
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": user_prompt},
        ]

        loop = asyncio.get_running_loop()
        try:
            result = await loop.run_in_executor(
                None,
                lambda: client.chat_completion(
                    messages    = messages,
                    max_tokens  = max_tokens,
                    temperature = temperature,
                ),
            )
            text = result.choices[0].message.content
        except Exception as exc:
            log.error("HF Inference API error: %s", exc)
            raise

        return LLMResponse(
            text              = text,
            model             = self._model,
            completion_tokens = result.usage.completion_tokens if result.usage else 0,
            prompt_tokens     = result.usage.prompt_tokens     if result.usage else 0,
        )

    @property
    def provider_name(self) -> str:
        return f"hf_inference:{self._model}"

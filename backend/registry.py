"""
registry.py

Factory functions that read config and return the correct provider instance.
THIS IS THE ONLY FILE YOU NEED TO EDIT to add a new provider.

Adding a new embedding provider
  1. Implement BaseEmbedder in models/embedding/your_provider.py
  2. Add an elif branch in get_embedder() below
  3. Set EMBEDDING_PROVIDER=your_provider in .env

Adding a new LLM provider
  1. Implement BaseLLM in models/llm/your_provider.py
  2. Add an elif branch in get_llm() below
  3. Set LLM_PROVIDER=your_provider in .env
"""
from functools import lru_cache

from backend.config import Settings
from backend.models.embedding.base import BaseEmbedder
from backend.models.llm.base import BaseLLM


@lru_cache(maxsize=1)
def get_embedder(settings: Settings | None = None) -> BaseEmbedder:
    from backend.config import settings as _s
    cfg = settings or _s

    p = cfg.embedding_provider.lower()

    if p == "sentence_transformer":
        from backend.models.embedding.sentence_transformer_embed import SentenceTransformerEmbedder
        return SentenceTransformerEmbedder(cfg.st_model)

    elif p == "ollama":
        from backend.models.embedding.ollama_embed import OllamaEmbedder
        return OllamaEmbedder(cfg.ollama_embed_model, cfg.ollama_base_url)

    elif p == "hf_inference_embed":
        from backend.models.embedding.hf_inference_embed import HFInferenceEmbedder
        return HFInferenceEmbedder(cfg.hf_embed_model, cfg.hf_token)

    else:
        raise ValueError(
            f"Unknown EMBEDDING_PROVIDER='{p}'. "
            "Valid: sentence_transformer, ollama, hf_inference_embed"
        )


@lru_cache(maxsize=1)
def get_llm(settings: Settings | None = None) -> BaseLLM:
    from backend.config import settings as _s
    cfg = settings or _s

    p = cfg.llm_provider.lower()

    if p == "ollama":
        from backend.models.llm.ollama_llm import OllamaLLM
        return OllamaLLM(cfg.ollama_llm_model, cfg.ollama_base_url)

    elif p == "openai_compat":
        from backend.models.llm.openai_compat_llm import OpenAICompatLLM
        return OpenAICompatLLM(
            cfg.openai_compat_base_url,
            cfg.openai_compat_api_key,
            cfg.openai_compat_model,
        )

    elif p == "hf_inference":
        from backend.models.llm.hf_inference_llm import HFInferenceLLM
        return HFInferenceLLM(cfg.hf_llm_model, cfg.hf_token)

    else:
        raise ValueError(
            f"Unknown LLM_PROVIDER='{p}'. "
            "Valid: ollama, openai_compat, hf_inference"
        )


def provider_info() -> dict:
    """Return active provider summary for /api/config."""
    from backend.config import settings as cfg
    embed_model = {
        "sentence_transformer": cfg.st_model,
        "ollama":               cfg.ollama_embed_model,
        "hf_inference_embed":   cfg.hf_embed_model,
    }.get(cfg.embedding_provider, cfg.st_model)

    llm_model = {
        "ollama":        cfg.ollama_llm_model,
        "openai_compat": cfg.openai_compat_model,
        "hf_inference":  cfg.hf_llm_model,
    }.get(cfg.llm_provider, cfg.ollama_llm_model)

    return {
        "embedding": {"provider": cfg.embedding_provider, "model": embed_model},
        "llm":       {"provider": cfg.llm_provider,       "model": llm_model},
    }

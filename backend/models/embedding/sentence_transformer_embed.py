"""
models/embedding/sentence_transformer_embed.py

Fully local embedding using sentence-transformers.
No API key, no network call — model is downloaded once and cached.

Default model: all-MiniLM-L6-v2
  - 22 MB download
  - 384-dimensional vectors
  - ~14k sentences/second on CPU

Swap model by changing ST_MODEL in .env, e.g.:
  ST_MODEL=all-mpnet-base-v2          (768-dim, slower, better quality)
  ST_MODEL=paraphrase-multilingual    (multilingual support)
"""
import asyncio
from functools import lru_cache
from typing import Any

from backend.models.embedding.base import BaseEmbedder


@lru_cache(maxsize=1)
def _load_model(model_name: str) -> Any:
    """Load and cache the SentenceTransformer model (heavy import kept lazy)."""
    from sentence_transformers import SentenceTransformer
    return SentenceTransformer(model_name)


class SentenceTransformerEmbedder(BaseEmbedder):
    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        self._model_name = model_name
        self._dim: int | None = None

    def _model(self):
        return _load_model(self._model_name)

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Run encoding in a thread pool so the event loop is not blocked."""
        if not texts:
            return []
        loop = asyncio.get_running_loop()
        vectors = await loop.run_in_executor(
            None,
            lambda: self._model().encode(texts, convert_to_numpy=True).tolist(),
        )
        return vectors

    def dimension(self) -> int:
        if self._dim is None:
            self._dim = self._model().get_sentence_embedding_dimension()
        return self._dim

    @property
    def provider_name(self) -> str:
        return f"sentence_transformer:{self._model_name}"

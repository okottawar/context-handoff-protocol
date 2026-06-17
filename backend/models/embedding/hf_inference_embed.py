"""
models/embedding/hf_inference_embed.py

Embeddings via the HuggingFace Inference API.
Good fallback when sentence-transformers can't download the model
(e.g. air-gapped networks) or when you want a specific hosted model.

Recommended free embedding models:
  sentence-transformers/all-MiniLM-L6-v2    (384-dim, very fast)
  sentence-transformers/all-mpnet-base-v2   (768-dim, higher quality)
  BAAI/bge-small-en-v1.5                    (384-dim, good retrieval quality)
  BAAI/bge-base-en-v1.5                     (768-dim)

Setup (.env):
  EMBEDDING_PROVIDER=hf_inference_embed
  HF_TOKEN=hf_xxxxxxxxxxxx
  HF_EMBED_MODEL=sentence-transformers/all-MiniLM-L6-v2
"""
import asyncio
import logging

from backend.models.embedding.base import BaseEmbedder

log = logging.getLogger(__name__)

_DIM_MAP = {
    "sentence-transformers/all-MiniLM-L6-v2":  384,
    "sentence-transformers/all-mpnet-base-v2": 768,
    "BAAI/bge-small-en-v1.5":                  384,
    "BAAI/bge-base-en-v1.5":                   768,
    "BAAI/bge-large-en-v1.5":                 1024,
}


class HFInferenceEmbedder(BaseEmbedder):
    def __init__(
        self,
        model: str = "sentence-transformers/all-MiniLM-L6-v2",
        token: str = "",
    ):
        self._model = model
        self._token = token or None

    def _get_client(self):
        from huggingface_hub import InferenceClient
        return InferenceClient(model=self._model, token=self._token)

    async def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        client = self._get_client()
        loop   = asyncio.get_running_loop()

        # HF Inference API feature_extraction returns a 2D list
        vectors = await loop.run_in_executor(
            None,
            lambda: client.feature_extraction(texts),
        )
        # Normalise to plain Python list[list[float]]
        import numpy as np
        arr    = np.array(vectors, dtype=np.float32)
        norms  = np.linalg.norm(arr, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        return (arr / norms).tolist()

    def dimension(self) -> int:
        return _DIM_MAP.get(self._model, 384)

    @property
    def provider_name(self) -> str:
        return f"hf_inference_embed:{self._model}"

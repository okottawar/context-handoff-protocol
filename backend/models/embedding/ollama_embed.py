"""
models/embedding/ollama_embed.py

Embedding via a local Ollama server.
Install Ollama: https://ollama.com
Pull a model:   ollama pull nomic-embed-text

Swap model by setting OLLAMA_EMBED_MODEL in .env, e.g.:
  OLLAMA_EMBED_MODEL=mxbai-embed-large   (1024-dim)
  OLLAMA_EMBED_MODEL=nomic-embed-text    (768-dim, default)
"""
import httpx

from backend.models.embedding.base import BaseEmbedder

_DIM_MAP = {
    "nomic-embed-text": 768,
    "mxbai-embed-large": 1024,
    "all-minilm": 384,
}


class OllamaEmbedder(BaseEmbedder):
    def __init__(self, model: str = "nomic-embed-text", base_url: str = "http://localhost:11434"):
        self._model = model
        self._base_url = base_url.rstrip("/")

    async def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        vectors = []
        async with httpx.AsyncClient(timeout=60.0) as client:
            for text in texts:
                response = await client.post(
                    f"{self._base_url}/api/embed",
                    json={"model": self._model, "input": text},
                )
                response.raise_for_status()
                data = response.json()
                # Ollama returns {"embeddings": [[...]] }
                vectors.append(data["embeddings"][0])
        return vectors

    def dimension(self) -> int:
        return _DIM_MAP.get(self._model, 768)

    @property
    def provider_name(self) -> str:
        return f"ollama:{self._model}"

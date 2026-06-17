"""
models/embedding/base.py

Abstract base class for all embedding providers.
Swap providers by implementing this interface and registering in registry.py.
"""
from abc import ABC, abstractmethod


class BaseEmbedder(ABC):
    """
    Contract every embedding backend must satisfy.
    Input:  list of strings
    Output: list of float lists (one vector per string)
    """

    @abstractmethod
    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Return a vector for every text in the input list."""
        ...

    @abstractmethod
    def dimension(self) -> int:
        """Return the vector dimensionality produced by this model."""
        ...

    @property
    def provider_name(self) -> str:
        return self.__class__.__name__

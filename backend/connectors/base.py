"""
connectors/base.py

Abstract base class for all data source connectors.
Each connector fetches raw signals and normalises them
into a list of RawEvent dicts before the pipeline ingests them.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class RawEvent:
    """Normalised signal from any data source."""
    source: str           # slack | github | notion | email | calendar | mock
    content: str          # human-readable text representation
    timestamp: datetime
    url: str = ""
    metadata: dict = field(default_factory=dict)


class BaseConnector(ABC):
    """
    Implement this interface to add a new data source.
    """

    @abstractmethod
    async def fetch(self, user_id: str, days_back: int = 30) -> list[RawEvent]:
        """
        Pull signals for user_id covering the last `days_back` days.
        Return a list of RawEvent, sorted newest-first is preferred but not required.
        """
        ...

    @property
    def source_name(self) -> str:
        return self.__class__.__name__

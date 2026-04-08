from abc import ABC, abstractmethod

from app.ingestion.models import RawArticle


class SourcePlugin(ABC):
    @abstractmethod
    def fetch(self) -> list[RawArticle]:
        """Fetch new articles from this source."""
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable plugin name."""
        ...

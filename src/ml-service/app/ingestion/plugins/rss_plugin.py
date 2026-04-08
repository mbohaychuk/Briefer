import logging
from datetime import datetime, timezone

import feedparser

from app.ingestion.models import RawArticle
from app.ingestion.plugin_base import SourcePlugin

logger = logging.getLogger(__name__)


class RssPlugin(SourcePlugin):
    def __init__(self, feeds: list[dict]):
        self.feeds = feeds

    @property
    def name(self) -> str:
        return "RSS"

    def fetch(self) -> list[RawArticle]:
        articles = []
        for feed_config in self.feeds:
            try:
                feed = feedparser.parse(feed_config["url"])
                for entry in feed.entries:
                    url = getattr(entry, "link", "")
                    title = getattr(entry, "title", "")
                    if not url or not title:
                        continue
                    articles.append(
                        RawArticle(
                            url=url,
                            title=title,
                            source_name=feed_config["name"],
                            author=getattr(entry, "author", None),
                            published_at=self._parse_date(entry),
                            summary=getattr(entry, "summary", None),
                        )
                    )
            except Exception:
                logger.warning(
                    "Failed to fetch feed %s", feed_config["url"], exc_info=True
                )
        return articles

    def _parse_date(self, entry) -> datetime | None:
        parsed = getattr(entry, "published_parsed", None)
        if not parsed:
            return None
        try:
            return datetime(*parsed[:6], tzinfo=timezone.utc)
        except (TypeError, ValueError):
            return None

import logging
from datetime import datetime, timezone

import feedparser
import httpx

from app.ingestion.models import RawArticle
from app.ingestion.plugin_base import SourcePlugin

logger = logging.getLogger(__name__)

USER_AGENT = "Mozilla/5.0 (compatible; NewsBriefer/1.0)"
FEED_TIMEOUT = 15


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
                # Use httpx with a real user-agent to avoid blocks (e.g. CBC),
                # then hand the content to feedparser for parsing.
                response = httpx.get(
                    feed_config["url"],
                    headers={"User-Agent": USER_AGENT},
                    timeout=FEED_TIMEOUT,
                    follow_redirects=True,
                )
                response.raise_for_status()
                feed = feedparser.parse(response.text)
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

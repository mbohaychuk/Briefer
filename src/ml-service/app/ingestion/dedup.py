import logging

from rapidfuzz import fuzz

from app.ingestion.models import NormalizedArticle
from app.ingestion.repository import ArticleRepository

logger = logging.getLogger(__name__)

TITLE_SIMILARITY_THRESHOLD = 90


class Deduplicator:
    """Three-layer deduplication: exact URL, content hash, fuzzy title+author."""

    def __init__(self, repository: ArticleRepository):
        self.repository = repository

    def is_duplicate(self, article: NormalizedArticle) -> bool:
        if self.repository.exists_by_url(article.url):
            return True

        if article.content_hash and self.repository.exists_by_content_hash(
            article.content_hash
        ):
            return True

        recent = self.repository.find_recent_for_dedup(days=7)
        for existing in recent:
            title_sim = fuzz.ratio(
                article.title_normalized, existing["title_normalized"] or ""
            )
            if title_sim >= TITLE_SIMILARITY_THRESHOLD:
                # Per spec: same title + different author = different article
                if (
                    article.author_normalized
                    and existing["author_normalized"]
                    and article.author_normalized != existing["author_normalized"]
                ):
                    continue
                return True

        return False

    def filter_duplicates(
        self, articles: list[NormalizedArticle]
    ) -> list[NormalizedArticle]:
        seen_urls: set[str] = set()
        result = []
        for article in articles:
            if article.url in seen_urls:
                continue
            if self.is_duplicate(article):
                continue
            seen_urls.add(article.url)
            result.append(article)
        return result

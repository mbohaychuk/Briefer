import logging
from typing import Callable
from uuid import UUID

from app.ingestion.dedup import Deduplicator
from app.ingestion.embedder import ArticleEmbedder
from app.ingestion.extractor import FullTextExtractor
from app.ingestion.models import IngestionResult, NormalizedArticle, RawArticle
from app.ingestion.plugin_base import SourcePlugin
from app.ingestion.repository import ArticleRepository

logger = logging.getLogger(__name__)

_pipeline_instance: "IngestionPipeline | None" = None


class IngestionPipeline:
    def __init__(
        self,
        plugins: list[SourcePlugin],
        extractor: FullTextExtractor,
        normalizer_fn: Callable[[RawArticle, str], NormalizedArticle],
        dedup: Deduplicator,
        repository: ArticleRepository,
        embedder: ArticleEmbedder,
    ):
        self.plugins = plugins
        self.extractor = extractor
        self.normalizer_fn = normalizer_fn
        self.dedup = dedup
        self.repository = repository
        self.embedder = embedder

    def run(self) -> IngestionResult:
        # 1. Fetch from all plugins
        raw_articles: list[RawArticle] = []
        for plugin in self.plugins:
            try:
                raw_articles.extend(plugin.fetch())
            except Exception:
                logger.exception("Plugin %s failed", plugin.name)

        logger.info("Fetched %d raw articles", len(raw_articles))

        # 2. Extract full text + normalize
        normalized: list[NormalizedArticle] = []
        for raw in raw_articles:
            full_text = self.extractor.extract(raw.url)
            if full_text:
                article = self.normalizer_fn(raw, full_text)
                normalized.append(article)

        logger.info("Extracted %d / %d articles", len(normalized), len(raw_articles))

        if not normalized:
            return IngestionResult(fetched=len(raw_articles))

        # 3. Deduplicate
        new_articles = self.dedup.filter_duplicates(normalized)
        logger.info("After dedup: %d new articles", len(new_articles))

        if not new_articles:
            return IngestionResult(
                fetched=len(raw_articles), extracted=len(normalized)
            )

        # 4. Store in PostgreSQL
        self.repository.insert_batch(new_articles)

        # 5. Embed and store in Qdrant
        embedded_ids = self.embedder.embed_and_store(new_articles)

        # 6. Update qdrant_point_ids and commit
        self.repository.update_qdrant_point_ids(embedded_ids)
        self.repository.commit()

        return IngestionResult(
            fetched=len(raw_articles),
            extracted=len(normalized),
            new=len(new_articles),
            embedded=len(embedded_ids),
        )


def get_pipeline() -> "IngestionPipeline":
    if _pipeline_instance is None:
        raise RuntimeError("Pipeline not initialized. Call init_pipeline() first.")
    return _pipeline_instance


def init_pipeline(
    plugins: list[SourcePlugin],
    extractor: FullTextExtractor,
    normalizer_fn: Callable,
    dedup: Deduplicator,
    repository: ArticleRepository,
    embedder: ArticleEmbedder,
) -> None:
    global _pipeline_instance
    _pipeline_instance = IngestionPipeline(
        plugins=plugins,
        extractor=extractor,
        normalizer_fn=normalizer_fn,
        dedup=dedup,
        repository=repository,
        embedder=embedder,
    )
    logger.info("Ingestion pipeline initialized")

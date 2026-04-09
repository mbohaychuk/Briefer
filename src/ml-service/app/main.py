import json
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.middleware import ApiKeyMiddleware
from app.routers import health, ingestion

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    if os.environ.get("TESTING") == "1":
        yield
        return

    from app.config import settings
    from app.database import get_connection, init_schema
    from app.ingestion.dedup import Deduplicator
    from app.ingestion.embedder import ArticleEmbedder
    from app.ingestion.extractor import FullTextExtractor
    from app.ingestion.normalizer import normalize_article
    from app.ingestion.pipeline import init_pipeline
    from app.ingestion.plugins.rss_plugin import RssPlugin
    from app.ingestion.repository import ArticleRepository
    from app.ingestion.scheduler import start_scheduler, stop_scheduler

    # Initialize database schema
    init_schema()

    # Load feed configuration
    with open(settings.feeds_path) as f:
        feeds = json.load(f)["feeds"]

    # Build pipeline components
    conn = get_connection()
    repository = ArticleRepository(conn)
    plugins = [RssPlugin(feeds)]
    extractor = FullTextExtractor()
    dedup = Deduplicator(repository)
    embedder = ArticleEmbedder(
        model_name=settings.embedding_model,
        qdrant_url=settings.qdrant_url,
        collection=settings.qdrant_collection,
        embedding_dim=settings.embedding_dim,
    )

    init_pipeline(
        plugins=plugins,
        extractor=extractor,
        normalizer_fn=normalize_article,
        dedup=dedup,
        repository=repository,
        embedder=embedder,
    )

    # Start background scheduler
    start_scheduler(settings.ingestion_interval_minutes)

    logger.info("ML Service started successfully")
    yield

    stop_scheduler()
    conn.close()


app = FastAPI(title="News Searcher ML Service", lifespan=lifespan)

app.add_middleware(ApiKeyMiddleware)
app.include_router(health.router)
app.include_router(ingestion.router)

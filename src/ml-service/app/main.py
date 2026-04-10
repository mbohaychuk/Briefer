import json
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.middleware import ApiKeyMiddleware
from app.routers import health, ingestion, scoring

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

    # Build scoring pipeline components
    from app.reasoning.cascade_router import CascadeRouter
    from app.reasoning.llm_scorer import LlmScorer
    from app.reasoning.llm_summarizer import LlmSummarizer
    from app.reasoning.normalizer import ScoreNormalizer
    from app.reasoning.pipeline import init_scoring_pipeline, ScoringPipeline
    from app.reasoning.profile_loader import ProfileLoader
    from app.reasoning.reranker import ArticleReranker
    from app.reasoning.repository import ScoringRepository
    from app.reasoning.retriever import ArticleRetriever

    profile_loader = ProfileLoader(model_name=settings.embedding_model)
    profiles = profile_loader.load_from_file(settings.profiles_path)
    scoring.set_profiles(profiles)

    if settings.llm_provider == "openai":
        from app.reasoning.providers.openai import OpenAiProvider

        llm_provider = OpenAiProvider(
            api_key=settings.openai_api_key,
            model=settings.openai_model,
            timeout=settings.openai_timeout,
        )
        logger.info("Using OpenAI provider (model=%s)", settings.openai_model)
    else:
        from app.reasoning.providers.ollama import OllamaProvider

        llm_provider = OllamaProvider(
            base_url=settings.ollama_base_url,
            model=settings.ollama_model,
            timeout=settings.ollama_timeout,
        )
        logger.info("Using Ollama provider (model=%s)", settings.ollama_model)

    scoring_repo = ScoringRepository(conn=conn)
    retriever = ArticleRetriever(
        qdrant_client=embedder.client,
        collection=settings.qdrant_collection,
        conn=conn,
        top_k=settings.retriever_top_k,
        date_days=settings.retriever_date_days,
    )
    reranker = ArticleReranker(model_name=settings.reranker_model)
    cascade_router = CascadeRouter(
        clear_pass_count=settings.scoring_clear_pass_count,
        safety_net_count=settings.scoring_safety_net_count,
    )
    llm_scorer = LlmScorer(
        provider=llm_provider,
        threshold=settings.scoring_llm_threshold,
    )
    llm_summarizer = LlmSummarizer(provider=llm_provider)
    score_normalizer = ScoreNormalizer()

    scoring_pipeline = ScoringPipeline(
        retriever=retriever,
        reranker=reranker,
        router=cascade_router,
        scorer=llm_scorer,
        summarizer=llm_summarizer,
        normalizer=score_normalizer,
        repository=scoring_repo,
    )
    init_scoring_pipeline(scoring_pipeline)

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
app.include_router(scoring.router)

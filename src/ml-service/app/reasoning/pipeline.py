import logging

from app.reasoning.cascade_router import CascadeRouter
from app.reasoning.llm_scorer import LlmScorer
from app.reasoning.llm_summarizer import LlmSummarizer
from app.reasoning.models import ScoringResult, UserProfile
from app.reasoning.normalizer import ScoreNormalizer
from app.reasoning.repository import ScoringRepository
from app.reasoning.retriever import ArticleRetriever
from app.reasoning.reranker import ArticleReranker

logger = logging.getLogger(__name__)

_pipeline_instance: "ScoringPipeline | None" = None


class ScoringPipeline:
    """Orchestrates the four-tier scoring cascade."""

    def __init__(
        self,
        retriever: ArticleRetriever,
        reranker: ArticleReranker,
        router: CascadeRouter,
        scorer: LlmScorer,
        summarizer: LlmSummarizer,
        normalizer: ScoreNormalizer,
        repository: ScoringRepository,
    ):
        self.retriever = retriever
        self.reranker = reranker
        self.router = router
        self.scorer = scorer
        self.summarizer = summarizer
        self.normalizer = normalizer
        self.repository = repository

    def run(self, profile: UserProfile) -> ScoringResult:
        result = ScoringResult(user_id=profile.user_id)

        # Tier 1: Vector retrieval
        candidates = self.retriever.retrieve(profile)
        result.candidates_retrieved = len(candidates)
        logger.info("Tier 1: Retrieved %d candidates", len(candidates))

        if not candidates:
            return result

        # Tier 2: Cross-encoder reranking
        reranked = self.reranker.rerank(candidates, profile)
        result.reranked = len(reranked)
        logger.info("Tier 2: Reranked %d articles", len(reranked))

        # Route to Tier 3 buckets
        route_result = self.router.route(reranked)
        to_score = route_result.clear_pass + route_result.borderline + route_result.safety_net
        logger.info(
            "Router: %d clear-pass, %d borderline, %d safety-net",
            len(route_result.clear_pass),
            len(route_result.borderline),
            len(route_result.safety_net),
        )

        if not to_score:
            return result

        # Tier 3: LLM scoring
        passed = self.scorer.score(to_score, profile)
        result.llm_scored = len(passed)
        logger.info("Tier 3: %d articles passed LLM scoring", len(passed))

        if not passed:
            return result

        # Tier 4: LLM summarization
        summarized = self.summarizer.summarize(passed, profile)
        result.summarized = sum(1 for a in summarized if a.summary)
        logger.info("Tier 4: Summarized %d articles", result.summarized)

        # Normalize scores and rank
        ranked = self.normalizer.normalize(summarized)

        # Store results
        self.repository.insert_batch(profile.user_id, ranked, status="ready")
        self.repository.commit()
        result.stored = len(ranked)

        logger.info(
            "Scoring complete for '%s': %d stored", profile.name, result.stored
        )
        return result


def get_scoring_pipeline() -> "ScoringPipeline":
    if _pipeline_instance is None:
        raise RuntimeError(
            "Scoring pipeline not initialized. Call init_scoring_pipeline() first."
        )
    return _pipeline_instance


def init_scoring_pipeline(pipeline: "ScoringPipeline") -> None:
    global _pipeline_instance
    _pipeline_instance = pipeline
    logger.info("Scoring pipeline initialized")

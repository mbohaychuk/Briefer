import logging

from app.reasoning.models import ScoredArticle, UserProfile
from app.reasoning.providers.base import LlmProvider

logger = logging.getLogger(__name__)

SCORING_SYSTEM_PROMPT = """You are a news relevance scorer. Given a user's interest profile and an article, assess how relevant the article is to the user.

Respond with JSON only:
{
  "score": <integer 1-10>,
  "explanation": "<1-2 sentences explaining why this is or isn't relevant>",
  "priority": "<routine|important|critical>"
}

Score guide:
- 1-3: Not relevant to the user's interests
- 4-5: Tangentially related, background awareness only
- 6-7: Relevant, the user should know about this
- 8-9: Highly relevant, directly impacts their work
- 10: Critical, requires immediate attention"""

CASCADE_MISS_THRESHOLD = 7


class LlmScorer:
    """Tier 3: LLM-based relevance scoring."""

    def __init__(self, provider: LlmProvider, threshold: int = 5):
        self.provider = provider
        self.threshold = threshold

    def score(
        self, articles: list[ScoredArticle], profile: UserProfile
    ) -> list[ScoredArticle]:
        profile_text = self._format_profile(profile)
        passed = []

        for scored in articles:
            try:
                result = self._score_one(scored, profile_text)
                if result is None:
                    continue

                scored.llm_score = result["score"]
                scored.llm_explanation = result["explanation"]
                scored.priority = result["priority"]

                # Log cascade misses from safety net
                if (
                    scored.route == "safety_net"
                    and scored.llm_score >= CASCADE_MISS_THRESHOLD
                ):
                    logger.warning(
                        "CASCADE MISS: Article '%s' scored %d by LLM but was "
                        "rejected by reranker (rerank_score=%.3f)",
                        scored.article.title,
                        scored.llm_score,
                        scored.rerank_score or 0,
                    )

                if scored.llm_score >= self.threshold:
                    passed.append(scored)

            except Exception:
                logger.warning(
                    "LLM scoring failed for '%s'",
                    scored.article.title,
                    exc_info=True,
                )

        logger.info(
            "LLM scored %d articles, %d passed threshold",
            len(articles),
            len(passed),
        )
        return passed

    def _score_one(self, scored: ScoredArticle, profile_text: str) -> dict | None:
        prompt = (
            f"## User Profile\n\n{profile_text}\n\n"
            f"## Article\n\n"
            f"**Title:** {scored.article.title}\n"
            f"**Source:** {scored.article.source_name}\n"
            f"**Author:** {scored.article.author or 'Unknown'}\n\n"
            f"{scored.article.raw_content[:2000]}"
        )

        result = self.provider.generate_json(prompt, system=SCORING_SYSTEM_PROMPT)

        if "score" not in result or "explanation" not in result:
            logger.warning("LLM returned incomplete JSON: %s", result)
            return None

        return result

    def _format_profile(self, profile: UserProfile) -> str:
        lines = [f"**Name:** {profile.name}\n"]
        for block in profile.interest_blocks:
            lines.append(f"**{block.label}:** {block.text}")
        return "\n\n".join(lines)

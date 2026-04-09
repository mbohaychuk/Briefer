import logging

from app.reasoning.models import ScoredArticle, UserProfile
from app.reasoning.providers.base import LlmProvider

logger = logging.getLogger(__name__)

SUMMARY_SYSTEM_PROMPT = """You are a news briefing assistant. Given a user's interest profile and an article, write a concise 2-3 sentence summary focused on why this article matters to this specific user. Do not include generic summaries — explain the relevance to their work."""


class LlmSummarizer:
    """Tier 4: Generates personalized per-article summaries."""

    def __init__(self, provider: LlmProvider):
        self.provider = provider

    def summarize(
        self, articles: list[ScoredArticle], profile: UserProfile
    ) -> list[ScoredArticle]:
        profile_text = self._format_profile(profile)

        for scored in articles:
            try:
                prompt = (
                    f"## User Profile\n\n{profile_text}\n\n"
                    f"## Article\n\n"
                    f"**Title:** {scored.article.title}\n"
                    f"**Source:** {scored.article.source_name}\n\n"
                    f"{scored.article.raw_content[:2000]}\n\n"
                    f"Write a 2-3 sentence summary explaining why this article "
                    f"matters to this user."
                )
                scored.summary = self.provider.generate(
                    prompt, system=SUMMARY_SYSTEM_PROMPT
                )
            except Exception:
                logger.warning(
                    "Summarization failed for '%s'",
                    scored.article.title,
                    exc_info=True,
                )

        logger.info(
            "Summarized %d / %d articles",
            sum(1 for a in articles if a.summary),
            len(articles),
        )
        return articles

    def _format_profile(self, profile: UserProfile) -> str:
        lines = [f"**Name:** {profile.name}\n"]
        for block in profile.interest_blocks:
            lines.append(f"**{block.label}:** {block.text}")
        return "\n\n".join(lines)

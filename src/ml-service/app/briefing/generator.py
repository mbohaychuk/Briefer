import logging

from app.briefing.models import BriefingArticle
from app.reasoning.models import UserProfile
from app.reasoning.providers.base import LlmProvider

logger = logging.getLogger(__name__)

EXECUTIVE_SUMMARY_SYSTEM = """You are an executive briefing assistant. Given a user's professional profile and a list of scored news articles with their personalized summaries, write a concise executive briefing paragraph (3-5 sentences).

Rules:
- Lead with the most critical or time-sensitive item
- Reference specific articles by title when making key points
- Explain why the collection of articles matters to this user's work today
- Use direct, professional language — no filler phrases
- Do not repeat individual article summaries verbatim; synthesize across them"""


class BriefingGenerator:
    """Generates executive summary briefings from scored articles."""

    def __init__(self, provider: LlmProvider):
        self.provider = provider

    def generate_summary(
        self,
        articles: list[BriefingArticle],
        profile: UserProfile,
    ) -> str | None:
        """Generate an executive summary from the top briefing articles.

        Returns the summary text, or None if generation fails.
        """
        if not articles:
            return None

        try:
            prompt = self._build_prompt(articles, profile)
            summary = self.provider.generate(
                prompt, system=EXECUTIVE_SUMMARY_SYSTEM
            )
            logger.info(
                "Generated executive summary for '%s' (%d articles)",
                profile.name,
                len(articles),
            )
            return summary
        except Exception:
            logger.warning(
                "Executive summary generation failed for '%s'",
                profile.name,
                exc_info=True,
            )
            return None

    def _build_prompt(
        self,
        articles: list[BriefingArticle],
        profile: UserProfile,
    ) -> str:
        profile_text = self._format_profile(profile)

        article_lines = []
        for art in articles[:15]:  # Cap at 15 to stay within context limits
            priority_tag = f" [{art.priority.upper()}]" if art.priority else ""
            line = f"**{art.rank}. {art.title}** ({art.source_name}){priority_tag}"
            if art.summary:
                line += f"\n   {art.summary}"
            article_lines.append(line)

        articles_text = "\n\n".join(article_lines)

        return (
            f"## User Profile\n\n{profile_text}\n\n"
            f"## Today's Articles ({len(articles)} total)\n\n"
            f"{articles_text}\n\n"
            f"Write a 3-5 sentence executive briefing for this user."
        )

    def _format_profile(self, profile: UserProfile) -> str:
        lines = [f"**Name:** {profile.name}\n"]
        for block in profile.interest_blocks:
            lines.append(f"**{block.label}:** {block.text}")
        return "\n\n".join(lines)

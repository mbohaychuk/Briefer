import logging

from sentence_transformers import CrossEncoder

from app.reasoning.models import ScoredArticle, UserProfile

logger = logging.getLogger(__name__)

CONTENT_TRUNCATE_LENGTH = 512


class ArticleReranker:
    """Tier 2: Cross-encoder reranking of candidate articles."""

    def __init__(self, model_name: str):
        self.model = CrossEncoder(model_name)

    def rerank(
        self, articles: list[ScoredArticle], profile: UserProfile
    ) -> list[ScoredArticle]:
        if not articles:
            return []

        interests = profile.interest_blocks

        # Build all (interest_text, article_text) pairs
        pairs = []
        for interest in interests:
            for scored in articles:
                article_text = (
                    scored.article.title
                    + "\n"
                    + scored.article.raw_content[:CONTENT_TRUNCATE_LENGTH]
                )
                pairs.append((interest.text, article_text))

        # Score all pairs in one batch
        scores = self.model.predict(pairs)

        # For each article, keep the best score across all interests
        num_interests = len(interests)
        for i, scored in enumerate(articles):
            article_scores = [
                float(scores[j * len(articles) + i])
                for j in range(num_interests)
            ]
            scored.rerank_score = max(article_scores)

        return articles

import logging

from app.reasoning.models import ScoredArticle

logger = logging.getLogger(__name__)

RERANK_DISCOUNT = 0.85
VECTOR_DISCOUNT = 0.70
CLEAR_PASS_IMPUTE_PERCENTILE = 0.75


class ScoreNormalizer:
    """Normalizes scores across tiers using percentiles and confidence discounting."""

    def normalize(self, articles: list[ScoredArticle]) -> list[ScoredArticle]:
        if not articles:
            return []

        # Collect raw scores per tier
        vector_scores = [a.vector_score for a in articles if a.vector_score is not None]
        rerank_scores = [a.rerank_score for a in articles if a.rerank_score is not None]
        llm_scores = [a.llm_score for a in articles if a.llm_score is not None]

        # Impute clear-pass articles missing LLM scores
        if llm_scores:
            imputed = _percentile(llm_scores, CLEAR_PASS_IMPUTE_PERCENTILE)
            for a in articles:
                if a.route == "clear_pass" and a.llm_score is None:
                    a.llm_score = imputed
                    llm_scores.append(imputed)

        # Compute display score for each article
        for a in articles:
            if a.llm_score is not None and llm_scores:
                a.display_score = _to_percentile(a.llm_score, llm_scores)
            elif a.rerank_score is not None and rerank_scores:
                a.display_score = _to_percentile(a.rerank_score, rerank_scores) * RERANK_DISCOUNT
            elif a.vector_score is not None and vector_scores:
                a.display_score = _to_percentile(a.vector_score, vector_scores) * VECTOR_DISCOUNT
            else:
                a.display_score = 0.0

        # Sort by display_score descending
        articles.sort(key=lambda a: a.display_score or 0, reverse=True)

        return articles


def _to_percentile(value: float, all_values: list[float]) -> float:
    """Convert a raw value to its percentile rank (0.0–1.0) within a list."""
    if not all_values:
        return 0.0
    if len(all_values) == 1:
        return 1.0
    count_below = sum(1 for v in all_values if v < value)
    return count_below / (len(all_values) - 1)


def _percentile(values: list[float], pct: float) -> float:
    """Calculate the value at a given percentile."""
    if not values:
        return 0.0
    sorted_vals = sorted(values)
    idx = int(len(sorted_vals) * pct)
    idx = min(idx, len(sorted_vals) - 1)
    return sorted_vals[idx]

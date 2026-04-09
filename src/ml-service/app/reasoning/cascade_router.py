import logging
import random
from dataclasses import dataclass, field

from app.reasoning.models import ScoredArticle

logger = logging.getLogger(__name__)

BORDERLINE_LOW_PERCENTILE = 0.30
BORDERLINE_HIGH_PERCENTILE = 0.70


@dataclass
class RouteResult:
    """Result of routing Tier 2 output into cascade buckets."""

    clear_pass: list[ScoredArticle] = field(default_factory=list)
    borderline: list[ScoredArticle] = field(default_factory=list)
    safety_net: list[ScoredArticle] = field(default_factory=list)


class CascadeRouter:
    """Routes Tier 2 reranked articles into clear-pass, borderline, and safety-net."""

    def __init__(self, clear_pass_count: int = 5, safety_net_count: int = 12):
        self.clear_pass_count = clear_pass_count
        self.safety_net_count = safety_net_count

    def route(self, articles: list[ScoredArticle]) -> RouteResult:
        if not articles:
            return RouteResult()

        # Sort by rerank_score descending
        sorted_articles = sorted(
            articles, key=lambda a: a.rerank_score or 0, reverse=True
        )

        # Clear-pass: top N
        clear_pass = sorted_articles[: self.clear_pass_count]
        for a in clear_pass:
            a.route = "clear_pass"

        remaining = sorted_articles[self.clear_pass_count :]

        if not remaining:
            return RouteResult(clear_pass=clear_pass)

        # Calculate percentile thresholds from remaining articles
        scores = [a.rerank_score or 0 for a in remaining]
        low_threshold = _percentile(scores, BORDERLINE_LOW_PERCENTILE)

        borderline = []
        rejected = []
        for a in remaining:
            score = a.rerank_score or 0
            if score >= low_threshold:
                a.route = "borderline"
                borderline.append(a)
            else:
                a.route = "rejected"
                rejected.append(a)

        # Safety-net: random sample from rejected
        sample_size = min(self.safety_net_count, len(rejected))
        safety_net = random.sample(rejected, sample_size) if sample_size > 0 else []
        for a in safety_net:
            a.route = "safety_net"

        logger.info(
            "Routed: %d clear-pass, %d borderline, %d safety-net, %d rejected",
            len(clear_pass),
            len(borderline),
            len(safety_net),
            len(rejected) - len(safety_net),
        )

        return RouteResult(
            clear_pass=clear_pass,
            borderline=borderline,
            safety_net=safety_net,
        )


def _percentile(values: list[float], pct: float) -> float:
    """Calculate percentile value from a sorted-ascending list."""
    if not values:
        return 0.0
    sorted_vals = sorted(values)
    idx = int(len(sorted_vals) * pct)
    idx = min(idx, len(sorted_vals) - 1)
    return sorted_vals[idx]

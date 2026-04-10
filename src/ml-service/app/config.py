import logging
import os

logger = logging.getLogger(__name__)


class Settings:
    def __init__(self):
        self.database_url = os.environ.get(
            "DATABASE_URL",
            "postgresql://newssearcher:changeme_dev@localhost:5432/newssearcher",
        )
        self.qdrant_url = os.environ.get("QDRANT_URL", "http://localhost:6333")
        self.qdrant_collection = os.environ.get("QDRANT_COLLECTION", "articles")
        self.embedding_model = os.environ.get(
            "EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2"
        )
        self.embedding_dim = int(os.environ.get("EMBEDDING_DIM", "384"))
        self.ml_api_key = os.environ.get("ML_SERVICE_API_KEY", "")
        self.ingestion_interval_minutes = int(
            os.environ.get("INGESTION_INTERVAL_MINUTES", "360")
        )
        self.feeds_path = os.environ.get("FEEDS_PATH", "feeds.json")

        # LLM provider settings
        self.llm_provider = os.environ.get("LLM_PROVIDER", "ollama")
        self.ollama_base_url = os.environ.get(
            "OLLAMA_BASE_URL", "http://localhost:11434"
        )
        self.ollama_model = os.environ.get("OLLAMA_MODEL", "gemma4")
        self.ollama_timeout = int(os.environ.get("OLLAMA_TIMEOUT", "120"))
        self.openai_api_key = os.environ.get("OPENAI_API_KEY", "")
        self.openai_model = os.environ.get("OPENAI_MODEL", "gpt-4.1-nano")
        self.openai_timeout = int(os.environ.get("OPENAI_TIMEOUT", "120"))
        self.reranker_model = os.environ.get(
            "RERANKER_MODEL", "BAAI/bge-reranker-v2-m3"
        )
        self.retriever_top_k = int(os.environ.get("RETRIEVER_TOP_K", "50"))
        self.retriever_date_days = int(
            os.environ.get("RETRIEVER_DATE_DAYS", "7")
        )
        self.scoring_llm_threshold = int(
            os.environ.get("SCORING_LLM_THRESHOLD", "5")
        )
        self.scoring_clear_pass_count = int(
            os.environ.get("SCORING_CLEAR_PASS_COUNT", "5")
        )
        self.scoring_safety_net_count = int(
            os.environ.get("SCORING_SAFETY_NET_COUNT", "12")
        )
        self.profiles_path = os.environ.get("PROFILES_PATH", "profiles.json")

        self._warn_insecure()

    def _warn_insecure(self):
        if os.environ.get("TESTING") == "1":
            return
        if not self.ml_api_key:
            logger.warning(
                "ML_SERVICE_API_KEY is not set — API endpoints are unauthenticated"
            )
        if self.llm_provider == "openai" and not self.openai_api_key:
            logger.warning(
                "LLM_PROVIDER=openai but OPENAI_API_KEY is not set"
            )


settings = Settings()

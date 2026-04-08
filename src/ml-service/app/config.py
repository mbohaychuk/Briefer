import os


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


settings = Settings()

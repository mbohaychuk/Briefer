import logging
from uuid import UUID

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams
from sentence_transformers import SentenceTransformer

from app.ingestion.models import NormalizedArticle

logger = logging.getLogger(__name__)


class ArticleEmbedder:
    """Embeds articles with sentence-transformers and stores vectors in Qdrant."""

    def __init__(
        self,
        model_name: str,
        qdrant_url: str,
        collection: str,
        embedding_dim: int,
    ):
        self.model = SentenceTransformer(model_name)
        self.client = QdrantClient(url=qdrant_url)
        self.collection = collection
        self._ensure_collection(embedding_dim)

    def _ensure_collection(self, embedding_dim: int) -> None:
        collections = [
            c.name for c in self.client.get_collections().collections
        ]
        if self.collection not in collections:
            self.client.create_collection(
                collection_name=self.collection,
                vectors_config=VectorParams(
                    size=embedding_dim, distance=Distance.COSINE
                ),
            )
            logger.info("Created Qdrant collection: %s", self.collection)

    def embed_and_store(
        self, articles: list[NormalizedArticle]
    ) -> list[UUID]:
        if not articles:
            return []

        texts = [a.raw_content for a in articles]
        embeddings = self.model.encode(texts)

        points = [
            PointStruct(
                id=str(article.id),
                vector=embedding.tolist(),
                payload={
                    "title": article.title,
                    "source_name": article.source_name,
                    "url": article.url,
                    "published_at": (
                        article.published_at.isoformat()
                        if article.published_at
                        else None
                    ),
                },
            )
            for article, embedding in zip(articles, embeddings)
        ]

        self.client.upsert(
            collection_name=self.collection, points=points
        )
        logger.info("Embedded and stored %d articles in Qdrant", len(articles))

        return [a.id for a in articles]

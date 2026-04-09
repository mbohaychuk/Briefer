from unittest.mock import MagicMock, patch
from uuid import uuid4

import numpy as np

from conftest import make_normalized_article

from app.ingestion.embedder import ArticleEmbedder


@patch("app.ingestion.embedder.QdrantClient")
@patch("app.ingestion.embedder.SentenceTransformer")
def test_embed_and_store_single_article(mock_st_class, mock_qdrant_class):
    mock_model = MagicMock()
    mock_model.encode.return_value = np.array([[0.1] * 384])
    mock_st_class.return_value = mock_model

    mock_client = MagicMock()
    mock_client.get_collections.return_value = MagicMock(collections=[])
    mock_qdrant_class.return_value = mock_client

    embedder = ArticleEmbedder(
        model_name="test-model",
        qdrant_url="http://test:6333",
        collection="test_articles",
        embedding_dim=384,
    )
    article = make_normalized_article()
    result = embedder.embed_and_store([article])

    assert len(result) == 1
    assert result[0] == article.id
    mock_model.encode.assert_called_once()
    mock_client.upsert.assert_called_once()


@patch("app.ingestion.embedder.QdrantClient")
@patch("app.ingestion.embedder.SentenceTransformer")
def test_embed_empty_list_returns_empty(mock_st_class, mock_qdrant_class):
    mock_client = MagicMock()
    mock_client.get_collections.return_value = MagicMock(collections=[])
    mock_qdrant_class.return_value = mock_client
    mock_st_class.return_value = MagicMock()

    embedder = ArticleEmbedder(
        model_name="test-model",
        qdrant_url="http://test:6333",
        collection="test_articles",
        embedding_dim=384,
    )
    result = embedder.embed_and_store([])
    assert result == []


@patch("app.ingestion.embedder.QdrantClient")
@patch("app.ingestion.embedder.SentenceTransformer")
def test_embed_creates_collection_if_missing(mock_st_class, mock_qdrant_class):
    mock_client = MagicMock()
    mock_client.get_collections.return_value = MagicMock(collections=[])
    mock_qdrant_class.return_value = mock_client
    mock_st_class.return_value = MagicMock()

    ArticleEmbedder(
        model_name="test-model",
        qdrant_url="http://test:6333",
        collection="new_collection",
        embedding_dim=384,
    )
    mock_client.create_collection.assert_called_once()


@patch("app.ingestion.embedder.QdrantClient")
@patch("app.ingestion.embedder.SentenceTransformer")
def test_embed_skips_collection_creation_if_exists(mock_st_class, mock_qdrant_class):
    existing = MagicMock()
    existing.name = "test_articles"
    mock_client = MagicMock()
    mock_client.get_collections.return_value = MagicMock(collections=[existing])
    mock_qdrant_class.return_value = mock_client
    mock_st_class.return_value = MagicMock()

    ArticleEmbedder(
        model_name="test-model",
        qdrant_url="http://test:6333",
        collection="test_articles",
        embedding_dim=384,
    )
    mock_client.create_collection.assert_not_called()

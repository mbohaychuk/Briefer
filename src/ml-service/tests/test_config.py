import logging
import os
from unittest.mock import patch


def test_default_values():
    """Settings should use default values when no env vars are set."""
    env = {
        "TESTING": "1",
    }
    with patch.dict(os.environ, env, clear=True):
        from app.config import Settings

        s = Settings()

    assert s.qdrant_url == "http://localhost:6333"
    assert s.qdrant_collection == "articles"
    assert s.embedding_model == "sentence-transformers/all-MiniLM-L6-v2"
    assert s.embedding_dim == 384
    assert s.ml_api_key == ""
    assert s.ingestion_interval_minutes == 360
    assert s.feeds_path == "feeds.json"
    assert s.llm_provider == "ollama"
    assert s.ollama_base_url == "http://localhost:11434"
    assert s.ollama_model == "gemma4"
    assert s.ollama_timeout == 120
    assert s.openai_api_key == ""
    assert s.openai_model == "gpt-4.1-nano"
    assert s.openai_timeout == 120
    assert s.retriever_top_k == 50
    assert s.retriever_date_days == 7
    assert s.scoring_llm_threshold == 5
    assert s.scoring_clear_pass_count == 5
    assert s.scoring_safety_net_count == 12
    assert s.profiles_path == "profiles.json"


def test_custom_values():
    """Settings should pick up values from environment variables."""
    env = {
        "TESTING": "1",
        "QDRANT_URL": "http://qdrant:6333",
        "QDRANT_COLLECTION": "my_articles",
        "EMBEDDING_MODEL": "custom-model",
        "EMBEDDING_DIM": "768",
        "ML_SERVICE_API_KEY": "secret123",
        "INGESTION_INTERVAL_MINUTES": "60",
        "FEEDS_PATH": "/etc/feeds.json",
        "LLM_PROVIDER": "openai",
        "OLLAMA_BASE_URL": "http://ollama:11434",
        "OLLAMA_MODEL": "llama3",
        "OLLAMA_TIMEOUT": "60",
        "OPENAI_API_KEY": "sk-test",
        "OPENAI_MODEL": "gpt-4o",
        "OPENAI_TIMEOUT": "90",
        "RETRIEVER_TOP_K": "100",
        "RETRIEVER_DATE_DAYS": "14",
        "SCORING_LLM_THRESHOLD": "7",
        "SCORING_CLEAR_PASS_COUNT": "10",
        "SCORING_SAFETY_NET_COUNT": "20",
        "PROFILES_PATH": "/etc/profiles.json",
    }
    with patch.dict(os.environ, env, clear=True):
        from app.config import Settings

        s = Settings()

    assert s.qdrant_url == "http://qdrant:6333"
    assert s.qdrant_collection == "my_articles"
    assert s.embedding_model == "custom-model"
    assert s.embedding_dim == 768
    assert s.ml_api_key == "secret123"
    assert s.ingestion_interval_minutes == 60
    assert s.feeds_path == "/etc/feeds.json"
    assert s.llm_provider == "openai"
    assert s.ollama_base_url == "http://ollama:11434"
    assert s.ollama_model == "llama3"
    assert s.ollama_timeout == 60
    assert s.openai_api_key == "sk-test"
    assert s.openai_model == "gpt-4o"
    assert s.openai_timeout == 90
    assert s.retriever_top_k == 100
    assert s.retriever_date_days == 14
    assert s.scoring_llm_threshold == 7
    assert s.scoring_clear_pass_count == 10
    assert s.scoring_safety_net_count == 20
    assert s.profiles_path == "/etc/profiles.json"


def test_integer_parsing():
    """Integer settings should be properly parsed from string env vars."""
    env = {
        "TESTING": "1",
        "EMBEDDING_DIM": "1024",
        "RETRIEVER_TOP_K": "200",
        "RETRIEVER_DATE_DAYS": "30",
        "OLLAMA_TIMEOUT": "300",
        "OPENAI_TIMEOUT": "180",
        "SCORING_LLM_THRESHOLD": "3",
        "SCORING_CLEAR_PASS_COUNT": "8",
        "SCORING_SAFETY_NET_COUNT": "15",
    }
    with patch.dict(os.environ, env, clear=True):
        from app.config import Settings

        s = Settings()

    assert isinstance(s.embedding_dim, int) and s.embedding_dim == 1024
    assert isinstance(s.retriever_top_k, int) and s.retriever_top_k == 200
    assert isinstance(s.retriever_date_days, int) and s.retriever_date_days == 30
    assert isinstance(s.ollama_timeout, int) and s.ollama_timeout == 300
    assert isinstance(s.openai_timeout, int) and s.openai_timeout == 180
    assert isinstance(s.scoring_llm_threshold, int) and s.scoring_llm_threshold == 3


def test_warn_insecure_logs_missing_api_key(caplog):
    """Should warn when ML_SERVICE_API_KEY is not set."""
    env = {k: v for k, v in os.environ.items()}
    env.pop("TESTING", None)
    env.pop("ML_SERVICE_API_KEY", None)
    with patch.dict(os.environ, env, clear=True):
        from app.config import Settings

        with caplog.at_level(logging.WARNING, logger="app.config"):
            Settings()

    assert "ML_SERVICE_API_KEY is not set" in caplog.text


def test_warn_insecure_logs_missing_openai_key(caplog):
    """Should warn when LLM_PROVIDER=openai but OPENAI_API_KEY is empty."""
    env = {k: v for k, v in os.environ.items()}
    env.pop("TESTING", None)
    env["LLM_PROVIDER"] = "openai"
    env.pop("OPENAI_API_KEY", None)
    env.pop("ML_SERVICE_API_KEY", None)
    with patch.dict(os.environ, env, clear=True):
        from app.config import Settings

        with caplog.at_level(logging.WARNING, logger="app.config"):
            Settings()

    assert "LLM_PROVIDER=openai but OPENAI_API_KEY is not set" in caplog.text


def test_warn_insecure_skips_when_testing(caplog):
    """No warnings should be emitted when TESTING=1."""
    env = {
        "TESTING": "1",
    }
    with patch.dict(os.environ, env, clear=True):
        from app.config import Settings

        with caplog.at_level(logging.WARNING, logger="app.config"):
            Settings()

    assert "ML_SERVICE_API_KEY" not in caplog.text
    assert "OPENAI_API_KEY" not in caplog.text

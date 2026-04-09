# Plan 2: Article Ingestion Pipeline — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the Python-side article ingestion pipeline that fetches articles from RSS feeds, extracts full text with trafilatura, deduplicates, generates embeddings with sentence-transformers, and stores articles in PostgreSQL + Qdrant.

**Architecture:** The ingestion pipeline runs inside the existing Python ML service (FastAPI). Source plugins fetch raw articles from RSS feeds. trafilatura extracts full-text content from article URLs. Articles are deduplicated against PostgreSQL using three checks: exact URL, content hash, and fuzzy title+author matching. New articles are embedded using sentence-transformers and stored in both PostgreSQL (metadata) and Qdrant (vectors). An internal API allows the ASP.NET service to trigger ingestion on-demand. A background scheduler triggers runs on a configurable interval.

**Tech Stack:** Python 3.12, FastAPI, feedparser, trafilatura, sentence-transformers, psycopg3, qdrant-client, rapidfuzz, pytest

**Important notes:**
- The `sentence-transformers` package pulls in PyTorch (~2GB). First `pip install` will take several minutes.
- The embedding model (`all-MiniLM-L6-v2`, ~80MB) downloads on first use. Subsequent runs use the local cache.
- All tests mock external dependencies (no real DB, Qdrant, or network calls needed for unit tests).
- Python manages the `articles` table schema directly (not EF Core). The .NET side will map to this table later when briefing endpoints are built.

---

## File Structure

```
src/ml-service/
├── app/
│   ├── __init__.py                         # (existing, unchanged)
│   ├── main.py                             # (modify) Add lifespan event, ingestion router
│   ├── middleware.py                        # (existing, unchanged)
│   ├── config.py                           # Settings from environment variables
│   ├── database.py                         # PostgreSQL connection + schema init
│   ├── routers/
│   │   ├── __init__.py                     # (existing, unchanged)
│   │   ├── health.py                       # (modify) Add real DB + Qdrant connectivity checks
│   │   └── ingestion.py                    # Ingestion trigger / status / feed list endpoints
│   └── ingestion/
│       ├── __init__.py
│       ├── models.py                       # RawArticle, NormalizedArticle, IngestionResult
│       ├── normalizer.py                   # Text normalization, content hashing
│       ├── plugin_base.py                  # Abstract SourcePlugin interface
│       ├── plugins/
│       │   ├── __init__.py
│       │   └── rss_plugin.py              # RSS feed reader (feedparser)
│       ├── extractor.py                    # trafilatura full-text extraction
│       ├── dedup.py                        # Three-layer deduplication
│       ├── embedder.py                     # sentence-transformers + Qdrant storage
│       ├── repository.py                   # PostgreSQL article CRUD
│       ├── pipeline.py                     # Orchestrates full ingestion flow
│       └── scheduler.py                    # Background ingestion scheduler
├── feeds.json                              # RSS feed configuration
├── tests/
│   ├── __init__.py                         # (existing, unchanged)
│   ├── conftest.py                         # Shared test fixtures + env setup
│   ├── test_health.py                      # (existing, unchanged)
│   └── ingestion/
│       ├── __init__.py
│       ├── test_normalizer.py
│       ├── test_rss_plugin.py
│       ├── test_extractor.py
│       ├── test_dedup.py
│       ├── test_embedder.py
│       ├── test_repository.py
│       └── test_pipeline.py
├── requirements.txt                        # (modify) Add new dependencies
└── Dockerfile                              # (existing, unchanged)
```

---

## Task 1: Dependencies, Configuration & Test Fixtures

**Files:**
- Modify: `src/ml-service/requirements.txt`
- Create: `src/ml-service/app/config.py`
- Create: `src/ml-service/feeds.json`
- Create: `src/ml-service/tests/conftest.py`

- [ ] **Step 1: Update requirements.txt**

```
fastapi==0.115.0
uvicorn[standard]==0.30.0
httpx==0.27.0
psycopg[binary]==3.3.3
qdrant-client==1.11.0
pytest==8.3.0
feedparser==6.0.11
trafilatura==2.0.0
sentence-transformers==3.4.1
rapidfuzz==3.12.1
```

- [ ] **Step 2: Install dependencies**

Run from `src/ml-service/`:
```bash
pip install -r requirements.txt
```

Expected: All packages install successfully. PyTorch download may take several minutes on first install.

- [ ] **Step 3: Create config.py**

```python
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
```

- [ ] **Step 4: Create feeds.json**

```json
{
  "feeds": [
    {
      "url": "https://www.cbc.ca/webfeed/rss/rss-topstories",
      "name": "CBC Top Stories"
    },
    {
      "url": "https://rss.cbc.ca/lineup/canada.xml",
      "name": "CBC Canada"
    },
    {
      "url": "https://feeds.bbci.co.uk/news/rss.xml",
      "name": "BBC News"
    },
    {
      "url": "https://www.theguardian.com/world/rss",
      "name": "The Guardian World"
    }
  ]
}
```

- [ ] **Step 5: Create tests/conftest.py**

This sets environment variables before any app code imports, preventing the lifespan from connecting to real services during tests.

```python
import os

os.environ["TESTING"] = "1"
os.environ["ML_SERVICE_API_KEY"] = "test-api-key"
```

- [ ] **Step 6: Verify existing tests still pass**

Run from `src/ml-service/`:
```bash
python -m pytest tests/test_health.py -v
```

Expected: 1 test passes.

- [ ] **Step 7: Commit**

```bash
git add src/ml-service/requirements.txt src/ml-service/app/config.py src/ml-service/feeds.json src/ml-service/tests/conftest.py
git commit -m "feat: add ingestion dependencies, configuration, and feed list"
```

---

## Task 2: Article Data Models & Text Normalizer

**Files:**
- Create: `src/ml-service/app/ingestion/__init__.py`
- Create: `src/ml-service/app/ingestion/models.py`
- Create: `src/ml-service/app/ingestion/normalizer.py`
- Create: `src/ml-service/tests/ingestion/__init__.py`
- Create: `src/ml-service/tests/ingestion/test_normalizer.py`
- Modify: `src/ml-service/tests/conftest.py`

- [ ] **Step 1: Create model and test directory stubs**

Create `src/ml-service/app/ingestion/__init__.py` (empty file).

Create `src/ml-service/tests/ingestion/__init__.py` (empty file).

- [ ] **Step 2: Create models.py**

```python
from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import UUID, uuid4


@dataclass
class RawArticle:
    """Raw article from a source plugin, before full-text extraction."""

    url: str
    title: str
    source_name: str
    author: str | None = None
    published_at: datetime | None = None
    summary: str | None = None


@dataclass
class NormalizedArticle:
    """Article with full text, content hash, and normalized fields for dedup."""

    id: UUID = field(default_factory=uuid4)
    url: str = ""
    title: str = ""
    title_normalized: str = ""
    raw_content: str = ""
    content_hash: str = ""
    source_name: str = ""
    author: str | None = None
    author_normalized: str | None = None
    published_at: datetime | None = None
    fetched_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


@dataclass
class IngestionResult:
    """Summary of a single ingestion run."""

    fetched: int = 0
    extracted: int = 0
    new: int = 0
    embedded: int = 0
```

- [ ] **Step 3: Add factory functions to tests/conftest.py**

Append to the existing `tests/conftest.py`:

```python
import hashlib
from datetime import datetime, timezone
from uuid import uuid4

from app.ingestion.models import NormalizedArticle, RawArticle


def make_raw_article(**kwargs):
    defaults = {
        "url": f"http://example.com/article-{uuid4().hex[:8]}",
        "title": "Test Article Title",
        "source_name": "Test Source",
        "author": "Test Author",
        "published_at": datetime(2026, 4, 8, 12, 0, 0, tzinfo=timezone.utc),
        "summary": "A test article summary.",
    }
    defaults.update(kwargs)
    return RawArticle(**defaults)


def make_normalized_article(**kwargs):
    defaults = {
        "id": uuid4(),
        "url": f"http://example.com/article-{uuid4().hex[:8]}",
        "title": "Test Article Title",
        "title_normalized": "test article title",
        "raw_content": "This is the full text of the test article. " * 10,
        "content_hash": hashlib.sha256(b"test content").hexdigest(),
        "source_name": "Test Source",
        "author": "Test Author",
        "author_normalized": "test author",
        "published_at": datetime(2026, 4, 8, 12, 0, 0, tzinfo=timezone.utc),
    }
    defaults.update(kwargs)
    return NormalizedArticle(**defaults)
```

- [ ] **Step 4: Write normalizer tests**

Create `tests/ingestion/test_normalizer.py`:

```python
from datetime import datetime, timezone

from app.ingestion.models import RawArticle
from app.ingestion.normalizer import content_hash, normalize_article, normalize_text


def test_normalize_text_lowercases():
    assert normalize_text("Hello World") == "hello world"


def test_normalize_text_strips_punctuation():
    assert normalize_text("hello, world! test.") == "hello world test"


def test_normalize_text_collapses_whitespace():
    assert normalize_text("hello   world  test") == "hello world test"


def test_normalize_text_strips_accents():
    assert normalize_text("café résumé") == "cafe resume"


def test_content_hash_deterministic():
    assert content_hash("Hello World") == content_hash("Hello World")


def test_content_hash_case_insensitive():
    assert content_hash("Hello World") == content_hash("hello world")


def test_content_hash_differs_for_different_text():
    assert content_hash("Hello") != content_hash("World")


def test_normalize_article_populates_all_fields():
    raw = RawArticle(
        url="http://example.com/article",
        title="Breaking News: Test Article!",
        source_name="Test Source",
        author="John Doe",
        published_at=datetime(2026, 4, 8, tzinfo=timezone.utc),
    )
    result = normalize_article(raw, "Full article text content here.")

    assert result.url == raw.url
    assert result.title == raw.title
    assert result.title_normalized == "breaking news test article"
    assert result.author_normalized == "john doe"
    assert result.raw_content == "Full article text content here."
    assert len(result.content_hash) == 64  # SHA-256 hex
    assert result.id is not None


def test_normalize_article_handles_none_author():
    raw = RawArticle(url="http://example.com", title="Title", source_name="Src")
    result = normalize_article(raw, "Article text.")
    assert result.author_normalized is None
```

- [ ] **Step 5: Run tests to verify they fail**

```bash
python -m pytest tests/ingestion/test_normalizer.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'app.ingestion.normalizer'`

- [ ] **Step 6: Implement normalizer.py**

```python
import hashlib
import re
import unicodedata
from uuid import uuid4

from app.ingestion.models import NormalizedArticle, RawArticle


def normalize_text(text: str) -> str:
    """Lowercase, strip accents and punctuation, collapse whitespace."""
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("ascii")
    text = text.lower()
    text = re.sub(r"[^\w\s]", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def content_hash(text: str) -> str:
    """SHA-256 hash of normalized text content."""
    normalized = normalize_text(text)
    return hashlib.sha256(normalized.encode()).hexdigest()


def normalize_article(raw: RawArticle, full_text: str) -> NormalizedArticle:
    """Convert a RawArticle + extracted full text into a NormalizedArticle."""
    return NormalizedArticle(
        id=uuid4(),
        url=raw.url,
        title=raw.title,
        title_normalized=normalize_text(raw.title),
        raw_content=full_text,
        content_hash=content_hash(full_text),
        source_name=raw.source_name,
        author=raw.author,
        author_normalized=normalize_text(raw.author) if raw.author else None,
        published_at=raw.published_at,
    )
```

- [ ] **Step 7: Run tests to verify they pass**

```bash
python -m pytest tests/ingestion/test_normalizer.py -v
```

Expected: All 9 tests pass.

- [ ] **Step 8: Commit**

```bash
git add src/ml-service/app/ingestion/ src/ml-service/tests/ingestion/ src/ml-service/tests/conftest.py
git commit -m "feat: add article data models and text normalizer with tests"
```

---

## Task 3: Source Plugin Interface & RSS Plugin

**Files:**
- Create: `src/ml-service/app/ingestion/plugin_base.py`
- Create: `src/ml-service/app/ingestion/plugins/__init__.py`
- Create: `src/ml-service/app/ingestion/plugins/rss_plugin.py`
- Create: `src/ml-service/tests/ingestion/test_rss_plugin.py`

- [ ] **Step 1: Create plugin_base.py**

```python
from abc import ABC, abstractmethod

from app.ingestion.models import RawArticle


class SourcePlugin(ABC):
    @abstractmethod
    def fetch(self) -> list[RawArticle]:
        """Fetch new articles from this source."""
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable plugin name."""
        ...
```

- [ ] **Step 2: Create plugins/__init__.py (empty file)**

- [ ] **Step 3: Write RSS plugin tests**

Create `tests/ingestion/test_rss_plugin.py`:

```python
import time
from types import SimpleNamespace
from unittest.mock import patch

from app.ingestion.plugins.rss_plugin import RssPlugin


def _make_entry(
    title="Test Article",
    link="http://example.com/1",
    author="Test Author",
    published_parsed=None,
):
    return SimpleNamespace(
        title=title,
        link=link,
        author=author,
        summary="A summary",
        published_parsed=published_parsed
        or time.struct_time((2026, 4, 8, 12, 0, 0, 1, 99, 0)),
    )


def _make_feed(entries):
    return SimpleNamespace(entries=entries, bozo=False)


@patch("app.ingestion.plugins.rss_plugin.feedparser.parse")
def test_fetch_returns_articles(mock_parse):
    mock_parse.return_value = _make_feed([_make_entry()])
    plugin = RssPlugin([{"url": "http://test.rss", "name": "Test Feed"}])
    articles = plugin.fetch()
    assert len(articles) == 1
    assert articles[0].title == "Test Article"
    assert articles[0].url == "http://example.com/1"
    assert articles[0].source_name == "Test Feed"
    assert articles[0].author == "Test Author"
    assert articles[0].published_at is not None


@patch("app.ingestion.plugins.rss_plugin.feedparser.parse")
def test_fetch_multiple_feeds(mock_parse):
    mock_parse.return_value = _make_feed([_make_entry()])
    feeds = [
        {"url": "http://feed1.rss", "name": "Feed 1"},
        {"url": "http://feed2.rss", "name": "Feed 2"},
    ]
    plugin = RssPlugin(feeds)
    articles = plugin.fetch()
    assert len(articles) == 2
    assert mock_parse.call_count == 2


@patch("app.ingestion.plugins.rss_plugin.feedparser.parse")
def test_fetch_skips_entries_without_link(mock_parse):
    mock_parse.return_value = _make_feed([_make_entry(link="")])
    plugin = RssPlugin([{"url": "http://test.rss", "name": "Test Feed"}])
    articles = plugin.fetch()
    assert len(articles) == 0


@patch("app.ingestion.plugins.rss_plugin.feedparser.parse")
def test_fetch_skips_entries_without_title(mock_parse):
    mock_parse.return_value = _make_feed([_make_entry(title="")])
    plugin = RssPlugin([{"url": "http://test.rss", "name": "Test Feed"}])
    articles = plugin.fetch()
    assert len(articles) == 0


@patch("app.ingestion.plugins.rss_plugin.feedparser.parse")
def test_fetch_handles_missing_published_date(mock_parse):
    entry = _make_entry()
    entry.published_parsed = None
    mock_parse.return_value = _make_feed([entry])
    plugin = RssPlugin([{"url": "http://test.rss", "name": "Test Feed"}])
    articles = plugin.fetch()
    assert len(articles) == 1
    assert articles[0].published_at is None


@patch("app.ingestion.plugins.rss_plugin.feedparser.parse")
def test_fetch_survives_feed_error(mock_parse):
    mock_parse.side_effect = Exception("Network error")
    plugin = RssPlugin([{"url": "http://bad.rss", "name": "Bad Feed"}])
    articles = plugin.fetch()
    assert len(articles) == 0
```

- [ ] **Step 4: Run tests to verify they fail**

```bash
python -m pytest tests/ingestion/test_rss_plugin.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'app.ingestion.plugins.rss_plugin'`

- [ ] **Step 5: Implement rss_plugin.py**

```python
import logging
from datetime import datetime, timezone

import feedparser

from app.ingestion.models import RawArticle
from app.ingestion.plugin_base import SourcePlugin

logger = logging.getLogger(__name__)


class RssPlugin(SourcePlugin):
    def __init__(self, feeds: list[dict]):
        self.feeds = feeds

    @property
    def name(self) -> str:
        return "RSS"

    def fetch(self) -> list[RawArticle]:
        articles = []
        for feed_config in self.feeds:
            try:
                feed = feedparser.parse(feed_config["url"])
                for entry in feed.entries:
                    url = getattr(entry, "link", "")
                    title = getattr(entry, "title", "")
                    if not url or not title:
                        continue
                    articles.append(
                        RawArticle(
                            url=url,
                            title=title,
                            source_name=feed_config["name"],
                            author=getattr(entry, "author", None),
                            published_at=self._parse_date(entry),
                            summary=getattr(entry, "summary", None),
                        )
                    )
            except Exception:
                logger.warning(
                    "Failed to fetch feed %s", feed_config["url"], exc_info=True
                )
        return articles

    def _parse_date(self, entry) -> datetime | None:
        parsed = getattr(entry, "published_parsed", None)
        if not parsed:
            return None
        try:
            return datetime(*parsed[:6], tzinfo=timezone.utc)
        except (TypeError, ValueError):
            return None
```

- [ ] **Step 6: Run tests to verify they pass**

```bash
python -m pytest tests/ingestion/test_rss_plugin.py -v
```

Expected: All 6 tests pass.

- [ ] **Step 7: Commit**

```bash
git add src/ml-service/app/ingestion/plugin_base.py src/ml-service/app/ingestion/plugins/ src/ml-service/tests/ingestion/test_rss_plugin.py
git commit -m "feat: add source plugin interface and RSS feed plugin"
```

---

## Task 4: Full-Text Extraction

**Files:**
- Create: `src/ml-service/app/ingestion/extractor.py`
- Create: `src/ml-service/tests/ingestion/test_extractor.py`

- [ ] **Step 1: Write extractor tests**

```python
from unittest.mock import patch

from app.ingestion.extractor import FullTextExtractor


@patch("app.ingestion.extractor.trafilatura")
def test_extract_returns_text(mock_traf):
    mock_traf.fetch_url.return_value = "<html><body>Content</body></html>"
    mock_traf.extract.return_value = (
        "This is a properly extracted article with enough content to pass the "
        "minimum length check that filters out stubs and error pages."
    )
    extractor = FullTextExtractor()
    result = extractor.extract("http://example.com/article")
    assert result is not None
    assert "extracted article" in result
    mock_traf.fetch_url.assert_called_once_with("http://example.com/article")


@patch("app.ingestion.extractor.trafilatura")
def test_extract_returns_none_on_download_failure(mock_traf):
    mock_traf.fetch_url.return_value = None
    extractor = FullTextExtractor()
    result = extractor.extract("http://example.com/bad-url")
    assert result is None


@patch("app.ingestion.extractor.trafilatura")
def test_extract_returns_none_when_extraction_empty(mock_traf):
    mock_traf.fetch_url.return_value = "<html></html>"
    mock_traf.extract.return_value = None
    extractor = FullTextExtractor()
    result = extractor.extract("http://example.com/empty")
    assert result is None


@patch("app.ingestion.extractor.trafilatura")
def test_extract_returns_none_for_short_content(mock_traf):
    mock_traf.fetch_url.return_value = "<html>content</html>"
    mock_traf.extract.return_value = "Too short."
    extractor = FullTextExtractor()
    result = extractor.extract("http://example.com/stub")
    assert result is None


@patch("app.ingestion.extractor.trafilatura")
def test_extract_handles_exception(mock_traf):
    mock_traf.fetch_url.side_effect = Exception("Connection timeout")
    extractor = FullTextExtractor()
    result = extractor.extract("http://example.com/timeout")
    assert result is None
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/ingestion/test_extractor.py -v
```

Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement extractor.py**

```python
import logging

import trafilatura

logger = logging.getLogger(__name__)

MIN_CONTENT_LENGTH = 100


class FullTextExtractor:
    """Extracts full article text from URLs using trafilatura."""

    def extract(self, url: str) -> str | None:
        try:
            downloaded = trafilatura.fetch_url(url)
            if not downloaded:
                logger.warning("Failed to download: %s", url)
                return None

            text = trafilatura.extract(downloaded)
            if not text or len(text.strip()) < MIN_CONTENT_LENGTH:
                logger.warning("Extraction too short or empty: %s", url)
                return None

            return text
        except Exception:
            logger.warning("Extraction failed for %s", url, exc_info=True)
            return None
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python -m pytest tests/ingestion/test_extractor.py -v
```

Expected: All 5 tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/ml-service/app/ingestion/extractor.py src/ml-service/tests/ingestion/test_extractor.py
git commit -m "feat: add trafilatura full-text extraction"
```

---

## Task 5: Database Connection & Article Repository

**Files:**
- Create: `src/ml-service/app/database.py`
- Create: `src/ml-service/app/ingestion/repository.py`
- Create: `src/ml-service/tests/ingestion/test_repository.py`

- [ ] **Step 1: Create database.py**

```python
import logging

import psycopg
from psycopg.rows import dict_row

from app.config import settings

logger = logging.getLogger(__name__)


def get_connection() -> psycopg.Connection:
    """Create a new database connection with dict row factory."""
    return psycopg.connect(settings.database_url, row_factory=dict_row)


def init_schema():
    """Create the articles table if it doesn't exist."""
    with get_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS articles (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                url TEXT NOT NULL UNIQUE,
                content_hash TEXT,
                title TEXT NOT NULL,
                title_normalized TEXT,
                author TEXT,
                author_normalized TEXT,
                raw_content TEXT,
                source_name TEXT NOT NULL,
                published_at TIMESTAMPTZ,
                fetched_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                qdrant_point_id UUID,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_articles_content_hash "
            "ON articles (content_hash)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_articles_url ON articles (url)"
        )
        conn.commit()
    logger.info("Database schema initialized")
```

- [ ] **Step 2: Write repository tests**

Create `tests/ingestion/test_repository.py`:

```python
from unittest.mock import MagicMock

from conftest import make_normalized_article

from app.ingestion.repository import ArticleRepository


def test_insert_executes_insert_sql():
    conn = MagicMock()
    repo = ArticleRepository(conn)
    article = make_normalized_article()
    repo.insert(article)
    conn.execute.assert_called_once()
    sql = conn.execute.call_args[0][0]
    assert "INSERT INTO articles" in sql
    assert "ON CONFLICT (url) DO NOTHING" in sql


def test_exists_by_url_returns_true_when_found():
    conn = MagicMock()
    conn.execute.return_value.fetchone.return_value = (1,)
    repo = ArticleRepository(conn)
    assert repo.exists_by_url("http://example.com") is True


def test_exists_by_url_returns_false_when_not_found():
    conn = MagicMock()
    conn.execute.return_value.fetchone.return_value = None
    repo = ArticleRepository(conn)
    assert repo.exists_by_url("http://example.com") is False


def test_exists_by_content_hash_returns_true_when_found():
    conn = MagicMock()
    conn.execute.return_value.fetchone.return_value = (1,)
    repo = ArticleRepository(conn)
    assert repo.exists_by_content_hash("abc123") is True


def test_find_recent_for_dedup_returns_rows():
    conn = MagicMock()
    conn.execute.return_value.fetchall.return_value = [
        {"title_normalized": "test title", "author_normalized": "test author"}
    ]
    repo = ArticleRepository(conn)
    rows = repo.find_recent_for_dedup(days=7)
    assert len(rows) == 1
    assert rows[0]["title_normalized"] == "test title"


def test_insert_batch_inserts_all_articles():
    conn = MagicMock()
    repo = ArticleRepository(conn)
    articles = [make_normalized_article(), make_normalized_article()]
    repo.insert_batch(articles)
    assert conn.execute.call_count == 2
```

- [ ] **Step 3: Run tests to verify they fail**

```bash
python -m pytest tests/ingestion/test_repository.py -v
```

Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 4: Implement repository.py**

```python
from datetime import datetime, timedelta, timezone
from uuid import UUID

import psycopg

from app.ingestion.models import NormalizedArticle


class ArticleRepository:
    """PostgreSQL CRUD operations for articles."""

    def __init__(self, conn: psycopg.Connection):
        self.conn = conn

    def insert(self, article: NormalizedArticle) -> None:
        self.conn.execute(
            """
            INSERT INTO articles
                (id, url, content_hash, title, title_normalized,
                 author, author_normalized, raw_content, source_name,
                 published_at, fetched_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (url) DO NOTHING
            """,
            (
                str(article.id),
                article.url,
                article.content_hash,
                article.title,
                article.title_normalized,
                article.author,
                article.author_normalized,
                article.raw_content,
                article.source_name,
                article.published_at,
                article.fetched_at,
            ),
        )

    def insert_batch(self, articles: list[NormalizedArticle]) -> None:
        for article in articles:
            self.insert(article)

    def exists_by_url(self, url: str) -> bool:
        row = self.conn.execute(
            "SELECT 1 FROM articles WHERE url = %s", (url,)
        ).fetchone()
        return row is not None

    def exists_by_content_hash(self, content_hash: str) -> bool:
        row = self.conn.execute(
            "SELECT 1 FROM articles WHERE content_hash = %s", (content_hash,)
        ).fetchone()
        return row is not None

    def find_recent_for_dedup(self, days: int = 7) -> list[dict]:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        rows = self.conn.execute(
            """
            SELECT title_normalized, author_normalized
            FROM articles
            WHERE created_at > %s
            """,
            (cutoff,),
        ).fetchall()
        return rows

    def update_qdrant_point_ids(self, article_ids: list[UUID]) -> None:
        for article_id in article_ids:
            self.conn.execute(
                "UPDATE articles SET qdrant_point_id = %s WHERE id = %s",
                (str(article_id), str(article_id)),
            )

    def commit(self) -> None:
        self.conn.commit()
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
python -m pytest tests/ingestion/test_repository.py -v
```

Expected: All 6 tests pass.

- [ ] **Step 6: Commit**

```bash
git add src/ml-service/app/database.py src/ml-service/app/ingestion/repository.py src/ml-service/tests/ingestion/test_repository.py
git commit -m "feat: add database connection and article repository"
```

---

## Task 6: Deduplication

**Files:**
- Create: `src/ml-service/app/ingestion/dedup.py`
- Create: `src/ml-service/tests/ingestion/test_dedup.py`

- [ ] **Step 1: Write dedup tests**

```python
from unittest.mock import MagicMock

from conftest import make_normalized_article

from app.ingestion.dedup import Deduplicator

FEEDS_URL_BASE = "http://example.com"


def test_exact_url_duplicate():
    repo = MagicMock()
    repo.exists_by_url.return_value = True
    dedup = Deduplicator(repo)
    article = make_normalized_article()
    assert dedup.is_duplicate(article) is True
    repo.exists_by_content_hash.assert_not_called()


def test_content_hash_duplicate():
    repo = MagicMock()
    repo.exists_by_url.return_value = False
    repo.exists_by_content_hash.return_value = True
    dedup = Deduplicator(repo)
    article = make_normalized_article()
    assert dedup.is_duplicate(article) is True


def test_fuzzy_title_match_same_author_is_duplicate():
    repo = MagicMock()
    repo.exists_by_url.return_value = False
    repo.exists_by_content_hash.return_value = False
    repo.find_recent_for_dedup.return_value = [
        {"title_normalized": "breaking news major event", "author_normalized": "john doe"}
    ]
    dedup = Deduplicator(repo)
    article = make_normalized_article(
        title_normalized="breaking news major event",
        author_normalized="john doe",
    )
    assert dedup.is_duplicate(article) is True


def test_same_title_different_author_not_duplicate():
    """Per spec: same title + different author = different article (different perspectives)."""
    repo = MagicMock()
    repo.exists_by_url.return_value = False
    repo.exists_by_content_hash.return_value = False
    repo.find_recent_for_dedup.return_value = [
        {"title_normalized": "breaking news event", "author_normalized": "john doe"}
    ]
    dedup = Deduplicator(repo)
    article = make_normalized_article(
        title_normalized="breaking news event",
        author_normalized="jane smith",
    )
    assert dedup.is_duplicate(article) is False


def test_new_article_not_duplicate():
    repo = MagicMock()
    repo.exists_by_url.return_value = False
    repo.exists_by_content_hash.return_value = False
    repo.find_recent_for_dedup.return_value = []
    dedup = Deduplicator(repo)
    article = make_normalized_article()
    assert dedup.is_duplicate(article) is False


def test_filter_removes_duplicates():
    repo = MagicMock()
    repo.exists_by_url.side_effect = [True, False]
    repo.exists_by_content_hash.return_value = False
    repo.find_recent_for_dedup.return_value = []
    dedup = Deduplicator(repo)
    articles = [make_normalized_article(), make_normalized_article()]
    result = dedup.filter_duplicates(articles)
    assert len(result) == 1


def test_filter_deduplicates_within_batch():
    """Two articles with the same URL in one batch — only the first should pass."""
    repo = MagicMock()
    repo.exists_by_url.return_value = False
    repo.exists_by_content_hash.return_value = False
    repo.find_recent_for_dedup.return_value = []
    dedup = Deduplicator(repo)
    shared_url = "http://example.com/same-article"
    articles = [
        make_normalized_article(url=shared_url),
        make_normalized_article(url=shared_url),
    ]
    result = dedup.filter_duplicates(articles)
    assert len(result) == 1
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/ingestion/test_dedup.py -v
```

Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement dedup.py**

```python
import logging

from rapidfuzz import fuzz

from app.ingestion.models import NormalizedArticle
from app.ingestion.repository import ArticleRepository

logger = logging.getLogger(__name__)

TITLE_SIMILARITY_THRESHOLD = 90


class Deduplicator:
    """Three-layer deduplication: exact URL, content hash, fuzzy title+author."""

    def __init__(self, repository: ArticleRepository):
        self.repository = repository

    def is_duplicate(self, article: NormalizedArticle) -> bool:
        if self.repository.exists_by_url(article.url):
            return True

        if article.content_hash and self.repository.exists_by_content_hash(
            article.content_hash
        ):
            return True

        recent = self.repository.find_recent_for_dedup(days=7)
        for existing in recent:
            title_sim = fuzz.ratio(
                article.title_normalized, existing["title_normalized"] or ""
            )
            if title_sim >= TITLE_SIMILARITY_THRESHOLD:
                # Per spec: same title + different author = different article
                if (
                    article.author_normalized
                    and existing["author_normalized"]
                    and article.author_normalized != existing["author_normalized"]
                ):
                    continue
                return True

        return False

    def filter_duplicates(
        self, articles: list[NormalizedArticle]
    ) -> list[NormalizedArticle]:
        seen_urls: set[str] = set()
        result = []
        for article in articles:
            if article.url in seen_urls:
                continue
            if self.is_duplicate(article):
                continue
            seen_urls.add(article.url)
            result.append(article)
        return result
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python -m pytest tests/ingestion/test_dedup.py -v
```

Expected: All 7 tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/ml-service/app/ingestion/dedup.py src/ml-service/tests/ingestion/test_dedup.py
git commit -m "feat: add three-layer article deduplication"
```

---

## Task 7: Embedding & Qdrant Storage

**Files:**
- Create: `src/ml-service/app/ingestion/embedder.py`
- Create: `src/ml-service/tests/ingestion/test_embedder.py`

- [ ] **Step 1: Write embedder tests**

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/ingestion/test_embedder.py -v
```

Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement embedder.py**

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python -m pytest tests/ingestion/test_embedder.py -v
```

Expected: All 4 tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/ml-service/app/ingestion/embedder.py src/ml-service/tests/ingestion/test_embedder.py
git commit -m "feat: add sentence-transformers embedding and Qdrant storage"
```

---

## Task 8: Ingestion Pipeline Orchestrator

**Files:**
- Create: `src/ml-service/app/ingestion/pipeline.py`
- Create: `src/ml-service/tests/ingestion/test_pipeline.py`

- [ ] **Step 1: Write pipeline tests**

```python
from unittest.mock import MagicMock

from conftest import make_normalized_article, make_raw_article

from app.ingestion.pipeline import IngestionPipeline


def _build_pipeline(**overrides):
    """Build a pipeline with mocked components. Override any component via kwargs."""
    defaults = {
        "plugins": [MagicMock()],
        "extractor": MagicMock(),
        "normalizer_fn": MagicMock(),
        "dedup": MagicMock(),
        "repository": MagicMock(),
        "embedder": MagicMock(),
    }
    defaults.update(overrides)

    # Wire up sensible default behaviors
    if "plugins" not in overrides:
        defaults["plugins"][0].fetch.return_value = [make_raw_article()]
        defaults["plugins"][0].name = "MockPlugin"
    if "extractor" not in overrides:
        defaults["extractor"].extract.return_value = "Full article text " * 10
    if "normalizer_fn" not in overrides:
        defaults["normalizer_fn"].return_value = make_normalized_article()
    if "dedup" not in overrides:
        defaults["dedup"].filter_duplicates.side_effect = lambda x: x
    if "embedder" not in overrides:
        defaults["embedder"].embed_and_store.return_value = [
            make_normalized_article().id
        ]

    return IngestionPipeline(**defaults)


def test_pipeline_end_to_end():
    pipeline = _build_pipeline()
    result = pipeline.run()
    assert result.fetched == 1
    assert result.extracted == 1
    assert result.new == 1
    assert result.embedded == 1


def test_pipeline_skips_extraction_failures():
    extractor = MagicMock()
    extractor.extract.return_value = None

    pipeline = _build_pipeline(extractor=extractor)
    result = pipeline.run()

    assert result.fetched == 1
    assert result.extracted == 0
    assert result.new == 0


def test_pipeline_dedup_filters_duplicates():
    dedup = MagicMock()
    dedup.filter_duplicates.return_value = []  # All filtered out

    pipeline = _build_pipeline(dedup=dedup)
    result = pipeline.run()

    assert result.new == 0
    assert result.embedded == 0


def test_pipeline_handles_plugin_error():
    failing_plugin = MagicMock()
    failing_plugin.fetch.side_effect = Exception("Feed unavailable")
    failing_plugin.name = "FailPlugin"

    working_plugin = MagicMock()
    working_plugin.fetch.return_value = [make_raw_article()]
    working_plugin.name = "WorkPlugin"

    pipeline = _build_pipeline(plugins=[failing_plugin, working_plugin])
    result = pipeline.run()

    assert result.fetched == 1  # Only working plugin's articles


def test_pipeline_commits_after_success():
    repo = MagicMock()
    pipeline = _build_pipeline(repository=repo)
    pipeline.run()
    repo.commit.assert_called_once()


def test_pipeline_multiple_articles():
    plugin = MagicMock()
    plugin.fetch.return_value = [make_raw_article(), make_raw_article(), make_raw_article()]
    plugin.name = "MultiPlugin"

    normalized = [make_normalized_article() for _ in range(3)]
    normalizer = MagicMock(side_effect=normalized)

    dedup = MagicMock()
    dedup.filter_duplicates.side_effect = lambda x: x

    embedder = MagicMock()
    embedder.embed_and_store.return_value = [a.id for a in normalized]

    pipeline = _build_pipeline(
        plugins=[plugin],
        normalizer_fn=normalizer,
        dedup=dedup,
        embedder=embedder,
    )
    result = pipeline.run()

    assert result.fetched == 3
    assert result.extracted == 3
    assert result.new == 3
    assert result.embedded == 3
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/ingestion/test_pipeline.py -v
```

Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement pipeline.py**

```python
import logging
from typing import Callable
from uuid import UUID

from app.ingestion.dedup import Deduplicator
from app.ingestion.embedder import ArticleEmbedder
from app.ingestion.extractor import FullTextExtractor
from app.ingestion.models import IngestionResult, NormalizedArticle, RawArticle
from app.ingestion.plugin_base import SourcePlugin
from app.ingestion.repository import ArticleRepository

logger = logging.getLogger(__name__)

_pipeline_instance: "IngestionPipeline | None" = None


class IngestionPipeline:
    def __init__(
        self,
        plugins: list[SourcePlugin],
        extractor: FullTextExtractor,
        normalizer_fn: Callable[[RawArticle, str], NormalizedArticle],
        dedup: Deduplicator,
        repository: ArticleRepository,
        embedder: ArticleEmbedder,
    ):
        self.plugins = plugins
        self.extractor = extractor
        self.normalizer_fn = normalizer_fn
        self.dedup = dedup
        self.repository = repository
        self.embedder = embedder

    def run(self) -> IngestionResult:
        # 1. Fetch from all plugins
        raw_articles: list[RawArticle] = []
        for plugin in self.plugins:
            try:
                raw_articles.extend(plugin.fetch())
            except Exception:
                logger.exception("Plugin %s failed", plugin.name)

        logger.info("Fetched %d raw articles", len(raw_articles))

        # 2. Extract full text + normalize
        normalized: list[NormalizedArticle] = []
        for raw in raw_articles:
            full_text = self.extractor.extract(raw.url)
            if full_text:
                article = self.normalizer_fn(raw, full_text)
                normalized.append(article)

        logger.info("Extracted %d / %d articles", len(normalized), len(raw_articles))

        if not normalized:
            return IngestionResult(fetched=len(raw_articles))

        # 3. Deduplicate
        new_articles = self.dedup.filter_duplicates(normalized)
        logger.info("After dedup: %d new articles", len(new_articles))

        if not new_articles:
            return IngestionResult(
                fetched=len(raw_articles), extracted=len(normalized)
            )

        # 4. Store in PostgreSQL
        self.repository.insert_batch(new_articles)

        # 5. Embed and store in Qdrant
        embedded_ids = self.embedder.embed_and_store(new_articles)

        # 6. Update qdrant_point_ids and commit
        self.repository.update_qdrant_point_ids(embedded_ids)
        self.repository.commit()

        return IngestionResult(
            fetched=len(raw_articles),
            extracted=len(normalized),
            new=len(new_articles),
            embedded=len(embedded_ids),
        )


def get_pipeline() -> "IngestionPipeline":
    if _pipeline_instance is None:
        raise RuntimeError("Pipeline not initialized. Call init_pipeline() first.")
    return _pipeline_instance


def init_pipeline(
    plugins: list[SourcePlugin],
    extractor: FullTextExtractor,
    normalizer_fn: Callable,
    dedup: Deduplicator,
    repository: ArticleRepository,
    embedder: ArticleEmbedder,
) -> None:
    global _pipeline_instance
    _pipeline_instance = IngestionPipeline(
        plugins=plugins,
        extractor=extractor,
        normalizer_fn=normalizer_fn,
        dedup=dedup,
        repository=repository,
        embedder=embedder,
    )
    logger.info("Ingestion pipeline initialized")
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python -m pytest tests/ingestion/test_pipeline.py -v
```

Expected: All 6 tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/ml-service/app/ingestion/pipeline.py src/ml-service/tests/ingestion/test_pipeline.py
git commit -m "feat: add ingestion pipeline orchestrator"
```

---

## Task 9: Ingestion API Endpoints

**Files:**
- Create: `src/ml-service/app/routers/ingestion.py`
- Create: `src/ml-service/tests/test_ingestion_api.py`

- [ ] **Step 1: Write API tests**

```python
import json
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from app.ingestion.models import IngestionResult


@patch("app.routers.ingestion.get_pipeline")
def test_trigger_ingestion_starts_run(mock_get_pipeline):
    mock_pipeline = MagicMock()
    mock_pipeline.run.return_value = IngestionResult(
        fetched=10, extracted=8, new=5, embedded=5
    )
    mock_get_pipeline.return_value = mock_pipeline

    from app.main import app

    client = TestClient(app)
    response = client.post(
        "/api/ingestion/trigger", headers={"X-Api-Key": "test-api-key"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["result"]["fetched"] == 10
    assert data["result"]["new"] == 5


@patch("app.routers.ingestion.get_pipeline")
def test_trigger_ingestion_handles_pipeline_error(mock_get_pipeline):
    mock_pipeline = MagicMock()
    mock_pipeline.run.side_effect = Exception("DB connection failed")
    mock_get_pipeline.return_value = mock_pipeline

    from app.main import app

    client = TestClient(app)
    response = client.post(
        "/api/ingestion/trigger", headers={"X-Api-Key": "test-api-key"}
    )
    assert response.status_code == 500
    assert "error" in response.json()


@patch("app.routers.ingestion.load_feeds")
def test_list_feeds(mock_load):
    mock_load.return_value = [
        {"url": "http://feed1.rss", "name": "Feed 1"},
        {"url": "http://feed2.rss", "name": "Feed 2"},
    ]

    from app.main import app

    client = TestClient(app)
    response = client.get(
        "/api/ingestion/feeds", headers={"X-Api-Key": "test-api-key"}
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data["feeds"]) == 2


def test_get_status():
    from app.main import app

    client = TestClient(app)
    response = client.get(
        "/api/ingestion/status", headers={"X-Api-Key": "test-api-key"}
    )
    assert response.status_code == 200
    data = response.json()
    assert "running" in data
    assert "last_result" in data


def test_ingestion_endpoints_require_api_key():
    from app.main import app

    client = TestClient(app)
    response = client.post("/api/ingestion/trigger")
    assert response.status_code == 401
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/test_ingestion_api.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'app.routers.ingestion'`

- [ ] **Step 3: Implement ingestion router**

```python
import json
import logging
from dataclasses import asdict
from datetime import datetime, timezone

from fastapi import APIRouter

from app.ingestion.models import IngestionResult
from app.ingestion.pipeline import get_pipeline

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/ingestion", tags=["ingestion"])

_last_result: IngestionResult | None = None
_last_run_at: datetime | None = None
_running = False


def load_feeds(path: str = "feeds.json") -> list[dict]:
    with open(path) as f:
        return json.load(f)["feeds"]


@router.post("/trigger")
async def trigger_ingestion():
    global _last_result, _last_run_at, _running

    if _running:
        return {"status": "already_running"}

    _running = True
    try:
        pipeline = get_pipeline()
        result = pipeline.run()
        _last_result = result
        _last_run_at = datetime.now(timezone.utc)
        return {"status": "completed", "result": asdict(result)}
    except Exception as e:
        logger.exception("Ingestion run failed")
        return {"status": "error", "error": str(e)}
    finally:
        _running = False


@router.get("/status")
async def get_status():
    return {
        "running": _running,
        "last_result": asdict(_last_result) if _last_result else None,
        "last_run_at": _last_run_at.isoformat() if _last_run_at else None,
    }


@router.get("/feeds")
async def list_feeds():
    try:
        feeds = load_feeds()
        return {"feeds": feeds}
    except FileNotFoundError:
        return {"feeds": [], "error": "feeds.json not found"}
```

- [ ] **Step 4: Register ingestion router in main.py**

Update `src/ml-service/app/main.py`:

```python
from fastapi import FastAPI

from app.middleware import ApiKeyMiddleware
from app.routers import health, ingestion

app = FastAPI(title="News Searcher ML Service")

app.add_middleware(ApiKeyMiddleware)
app.include_router(health.router)
app.include_router(ingestion.router)
```

- [ ] **Step 5: Fix trigger error handling**

The test expects a 500 status code on pipeline error, but the current endpoint returns 200 with an error body. Update the trigger endpoint to raise an HTTPException:

Replace the exception handler in the trigger endpoint:

```python
    except Exception as e:
        logger.exception("Ingestion run failed")
        from fastapi import HTTPException
        raise HTTPException(status_code=500, detail=str(e))
```

Full updated function:

```python
@router.post("/trigger")
async def trigger_ingestion():
    global _last_result, _last_run_at, _running

    if _running:
        return {"status": "already_running"}

    _running = True
    try:
        pipeline = get_pipeline()
        result = pipeline.run()
        _last_result = result
        _last_run_at = datetime.now(timezone.utc)
        return {"status": "completed", "result": asdict(result)}
    except Exception as e:
        logger.exception("Ingestion run failed")
        from fastapi import HTTPException

        raise HTTPException(status_code=500, detail=str(e))
    finally:
        _running = False
```

- [ ] **Step 6: Run tests to verify they pass**

```bash
python -m pytest tests/test_ingestion_api.py -v
```

Expected: All 5 tests pass.

- [ ] **Step 7: Run all tests**

```bash
python -m pytest tests/ -v
```

Expected: All tests pass (health + normalizer + rss + extractor + repository + dedup + embedder + pipeline + ingestion API).

- [ ] **Step 8: Commit**

```bash
git add src/ml-service/app/routers/ingestion.py src/ml-service/app/main.py src/ml-service/tests/test_ingestion_api.py
git commit -m "feat: add ingestion API endpoints for trigger, status, and feeds"
```

---

## Task 10: Scheduler, Health Checks & Startup Wiring

**Files:**
- Create: `src/ml-service/app/ingestion/scheduler.py`
- Modify: `src/ml-service/app/main.py`
- Modify: `src/ml-service/app/routers/health.py`
- Modify: `src/ml-service/app/middleware.py`

This task wires everything together. The lifespan event initializes the database schema, builds the pipeline, and starts the background scheduler. The health endpoint gets real connectivity checks. No new unit tests — this is integration wiring validated by running the full service.

- [ ] **Step 1: Create scheduler.py**

```python
import logging
import threading

logger = logging.getLogger(__name__)

_timer: threading.Timer | None = None
_interval_seconds: int = 0


def _run_scheduled():
    from app.ingestion.pipeline import get_pipeline

    try:
        pipeline = get_pipeline()
        result = pipeline.run()
        logger.info(
            "Scheduled ingestion complete: fetched=%d, new=%d, embedded=%d",
            result.fetched,
            result.new,
            result.embedded,
        )
    except Exception:
        logger.exception("Scheduled ingestion failed")
    finally:
        _schedule_next()


def _schedule_next():
    global _timer
    if _interval_seconds > 0:
        _timer = threading.Timer(_interval_seconds, _run_scheduled)
        _timer.daemon = True
        _timer.start()


def start_scheduler(interval_minutes: int):
    global _interval_seconds
    _interval_seconds = interval_minutes * 60
    logger.info("Ingestion scheduler started (every %d minutes)", interval_minutes)
    _schedule_next()


def stop_scheduler():
    global _timer
    if _timer:
        _timer.cancel()
        logger.info("Ingestion scheduler stopped")
```

- [ ] **Step 2: Update main.py with lifespan and full wiring**

```python
import json
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.middleware import ApiKeyMiddleware
from app.routers import health, ingestion

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    if os.environ.get("TESTING") == "1":
        yield
        return

    from app.config import settings
    from app.database import get_connection, init_schema
    from app.ingestion.dedup import Deduplicator
    from app.ingestion.embedder import ArticleEmbedder
    from app.ingestion.extractor import FullTextExtractor
    from app.ingestion.normalizer import normalize_article
    from app.ingestion.pipeline import init_pipeline
    from app.ingestion.plugins.rss_plugin import RssPlugin
    from app.ingestion.repository import ArticleRepository
    from app.ingestion.scheduler import start_scheduler, stop_scheduler

    # Initialize database schema
    init_schema()

    # Load feed configuration
    with open(settings.feeds_path) as f:
        feeds = json.load(f)["feeds"]

    # Build pipeline components
    conn = get_connection()
    repository = ArticleRepository(conn)
    plugins = [RssPlugin(feeds)]
    extractor = FullTextExtractor()
    dedup = Deduplicator(repository)
    embedder = ArticleEmbedder(
        model_name=settings.embedding_model,
        qdrant_url=settings.qdrant_url,
        collection=settings.qdrant_collection,
        embedding_dim=settings.embedding_dim,
    )

    init_pipeline(
        plugins=plugins,
        extractor=extractor,
        normalizer_fn=normalize_article,
        dedup=dedup,
        repository=repository,
        embedder=embedder,
    )

    # Start background scheduler
    start_scheduler(settings.ingestion_interval_minutes)

    logger.info("ML Service started successfully")
    yield

    stop_scheduler()
    conn.close()


app = FastAPI(title="News Searcher ML Service", lifespan=lifespan)

app.add_middleware(ApiKeyMiddleware)
app.include_router(health.router)
app.include_router(ingestion.router)
```

- [ ] **Step 3: Update health.py with real connectivity checks**

```python
import logging
import os

from fastapi import APIRouter

router = APIRouter()

logger = logging.getLogger(__name__)


@router.get("/health")
async def health_check():
    db_status = "not_connected"
    qdrant_status = "not_connected"

    if os.environ.get("TESTING") == "1":
        return {
            "status": "healthy",
            "database": "testing",
            "qdrant": "testing",
        }

    try:
        from app.database import get_connection

        conn = get_connection()
        conn.execute("SELECT 1")
        conn.close()
        db_status = "connected"
    except Exception:
        logger.debug("Health check: database not reachable", exc_info=True)

    try:
        from qdrant_client import QdrantClient

        from app.config import settings

        client = QdrantClient(url=settings.qdrant_url, timeout=2)
        client.get_collections()
        qdrant_status = "connected"
    except Exception:
        logger.debug("Health check: Qdrant not reachable", exc_info=True)

    return {
        "status": "healthy",
        "database": db_status,
        "qdrant": qdrant_status,
    }
```

- [ ] **Step 4: Update middleware to allow ingestion API paths**

The middleware already allows any path with a valid API key. No changes needed — the `X-Api-Key` header protects all non-health endpoints including `/api/ingestion/*`.

- [ ] **Step 5: Update .env.example with new variables**

Append to `src/ml-service/` section in the root `.env.example`:

```env
# PostgreSQL
POSTGRES_USER=newssearcher
POSTGRES_PASSWORD=changeme_dev
POSTGRES_DB=newssearcher

# Qdrant
QDRANT_HOST=qdrant
QDRANT_PORT=6333

# JWT
JWT_SECRET=changeme_dev_secret_at_least_32_chars_long
JWT_ISSUER=NewsSearcher
JWT_AUDIENCE=NewsSearcher

# ML Service
ML_SERVICE_URL=http://ml-service:8000
ML_SERVICE_API_KEY=changeme_dev_ml_api_key

# Embeddings (defaults shown — override to change model)
# EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
# EMBEDDING_DIM=384
# INGESTION_INTERVAL_MINUTES=360
```

- [ ] **Step 6: Run all tests**

```bash
python -m pytest tests/ -v
```

Expected: All tests pass. The lifespan is skipped during testing due to `TESTING=1`.

- [ ] **Step 7: Verify existing .NET tests still pass**

Run from `src/web-api/`:

```bash
dotnet test --verbosity normal
```

Expected: All 14 integration tests pass (no .NET changes were made).

- [ ] **Step 8: Commit**

```bash
git add src/ml-service/app/ingestion/scheduler.py src/ml-service/app/main.py src/ml-service/app/routers/health.py .env.example
git commit -m "feat: wire up ingestion pipeline with scheduler and health checks"
```

---

## Post-Completion: Manual Smoke Test

After all tasks are complete, verify end-to-end with real services:

1. Start infrastructure:
   ```bash
   docker compose up postgres qdrant -d
   ```

2. Run the ML service locally:
   ```bash
   cd src/ml-service
   DATABASE_URL=postgresql://newssearcher:changeme_dev@localhost:5432/newssearcher \
   QDRANT_URL=http://localhost:6333 \
   ML_SERVICE_API_KEY=test \
   python -m uvicorn app.main:app --reload
   ```

3. Trigger an ingestion run:
   ```bash
   curl -X POST http://localhost:8000/api/ingestion/trigger -H "X-Api-Key: test"
   ```

4. Check status:
   ```bash
   curl http://localhost:8000/api/ingestion/status -H "X-Api-Key: test"
   ```

5. Check health:
   ```bash
   curl http://localhost:8000/health
   ```

Expected: Articles fetched from RSS feeds, extracted, deduplicated, embedded, and stored in PostgreSQL + Qdrant.

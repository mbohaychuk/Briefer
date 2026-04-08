import hashlib
import os
from datetime import datetime, timezone
from uuid import uuid4

from app.ingestion.models import NormalizedArticle, RawArticle

os.environ["TESTING"] = "1"
os.environ["ML_SERVICE_API_KEY"] = "test-api-key"


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

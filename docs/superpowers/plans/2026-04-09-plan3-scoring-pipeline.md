# Plan 3: Scoring Pipeline — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the four-tier scoring cascade that takes ingested articles and determines which ones are relevant to each user — vector retrieval → cross-encoder reranking → LLM scoring → LLM summarization — with score normalization, persistence in `user_articles`, and API endpoints.

**Architecture:** Each tier is its own class with dependency injection via constructor params (same pattern as the ingestion pipeline). A `CascadeRouter` handles the split between Tier 2 and Tier 3. A thin `ScoringPipeline` orchestrator wires everything. User profiles are loaded from `profiles.json` and embedded at startup. LLM calls go through a model-agnostic `LlmProvider` interface, with an Ollama/Gemma 4 implementation. All tests mock external dependencies (no real Qdrant, PostgreSQL, Ollama, or model loading).

**Tech Stack:** Python 3.14, FastAPI, sentence-transformers (CrossEncoder), qdrant-client, httpx (for Ollama REST API), psycopg3, pytest

**Important notes:**
- The cross-encoder model (`BAAI/bge-reranker-v2-m3`, ~1.1GB) downloads on first use via `sentence-transformers`. First run will be slow.
- Ollama must be installed and running locally with Gemma 4 pulled (`ollama pull gemma4`) for the LLM tiers to work. Tests mock all Ollama calls.
- The `user_articles` table references the `articles` table created by Plan 2. Database schema init runs both tables.
- The existing `all-MiniLM-L6-v2` model (from Plan 2's embedder) is reused to embed user interest profiles. No new embedding model needed.

---

## File Structure

```
src/ml-service/
├── app/
│   ├── config.py                         # (modify) Add scoring/Ollama settings
│   ├── database.py                       # (modify) Add user_articles table to init_schema
│   ├── main.py                           # (modify) Wire scoring pipeline into lifespan
│   ├── reasoning/
│   │   ├── __init__.py
│   │   ├── models.py                     # InterestBlock, UserProfile, ScoredArticle, ScoringResult
│   │   ├── profile_loader.py            # Load profiles.json, embed interest blocks
│   │   ├── retriever.py                 # Tier 1: Qdrant multi-vector search
│   │   ├── reranker.py                  # Tier 2: Cross-encoder reranking
│   │   ├── cascade_router.py            # Route Tier 2 output → clear-pass / borderline / safety-net
│   │   ├── llm_scorer.py               # Tier 3: LLM relevance scoring
│   │   ├── llm_summarizer.py           # Tier 4: Per-article personalized summaries
│   │   ├── normalizer.py               # Percentile normalization + confidence discounting
│   │   ├── repository.py               # user_articles table CRUD
│   │   ├── pipeline.py                 # Orchestrator: wires all tiers together
│   │   └── providers/
│   │       ├── __init__.py
│   │       ├── base.py                  # Abstract LlmProvider interface
│   │       └── ollama.py               # Ollama + Gemma 4 implementation
│   └── routers/
│       └── scoring.py                   # /api/scoring/trigger, /status
├── profiles.json                        # Test user profile (Alberta policy analyst)
└── tests/
    └── reasoning/
        ├── __init__.py
        ├── test_profile_loader.py
        ├── test_retriever.py
        ├── test_reranker.py
        ├── test_cascade_router.py
        ├── test_llm_scorer.py
        ├── test_llm_summarizer.py
        ├── test_normalizer.py
        ├── test_repository.py
        └── test_pipeline.py
```

---

## Task 1: Configuration and Data Models

**Files:**
- Modify: `src/ml-service/app/config.py`
- Create: `src/ml-service/profiles.json`
- Create: `src/ml-service/app/reasoning/__init__.py`
- Create: `src/ml-service/app/reasoning/models.py`
- Test: `src/ml-service/tests/reasoning/__init__.py`
- Test: `src/ml-service/tests/reasoning/test_profile_loader.py` (partial — model tests only)

- [ ] **Step 1: Add scoring settings to config.py**

Add the new scoring/Ollama settings below the existing fields in `Settings.__init__`:

```python
        # Scoring pipeline settings
        self.ollama_base_url = os.environ.get(
            "OLLAMA_BASE_URL", "http://localhost:11434"
        )
        self.ollama_model = os.environ.get("OLLAMA_MODEL", "gemma4")
        self.ollama_timeout = int(os.environ.get("OLLAMA_TIMEOUT", "120"))
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
```

- [ ] **Step 2: Create profiles.json**

Create `src/ml-service/profiles.json` with the Alberta policy analyst test profile from the design spec:

```json
{
  "profiles": [
    {
      "user_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
      "name": "Alberta Policy Analyst (Test)",
      "interests": [
        {
          "label": "Primary Role",
          "text": "I'm an environmental analyst for the Government of Alberta, working in the oil and gas branch. I need to stay informed about environmental policy, regulations, and incidents that could affect Alberta's energy sector."
        },
        {
          "label": "Wildlife Mandate",
          "text": "My department is responsible for managing deer populations in the Peace River region of northern Alberta. This is due to a historical mandate. I need to know about anything affecting deer in this region: disease, habitat disruption, predator changes, climate impact, and similar issues in neighboring provinces that could spread."
        },
        {
          "label": "Regional Scope",
          "text": "I primarily focus on Alberta but need awareness of British Columbia, Saskatchewan, and federal Canadian developments that could have cross-border policy implications."
        }
      ]
    }
  ]
}
```

- [ ] **Step 3: Create reasoning module and data models**

Create `src/ml-service/app/reasoning/__init__.py` (empty file).

Create `src/ml-service/app/reasoning/models.py`:

```python
from dataclasses import dataclass, field
from uuid import UUID

from app.ingestion.models import NormalizedArticle


@dataclass
class InterestBlock:
    """A single interest description with its embedding."""

    label: str
    text: str
    embedding: list[float] = field(default_factory=list)


@dataclass
class UserProfile:
    """A user's profile with embedded interest blocks."""

    user_id: UUID
    name: str
    interest_blocks: list[InterestBlock] = field(default_factory=list)


@dataclass
class ScoredArticle:
    """An article accumulating scores through the cascade."""

    article: NormalizedArticle
    vector_score: float | None = None
    rerank_score: float | None = None
    llm_score: float | None = None
    llm_explanation: str | None = None
    priority: str | None = None
    summary: str | None = None
    display_score: float | None = None
    route: str | None = None


@dataclass
class ScoringResult:
    """Summary of a single scoring run."""

    user_id: UUID | None = None
    candidates_retrieved: int = 0
    reranked: int = 0
    llm_scored: int = 0
    summarized: int = 0
    stored: int = 0
```

- [ ] **Step 4: Write tests for data models**

Create `src/ml-service/tests/reasoning/__init__.py` (empty file).

Create `src/ml-service/tests/reasoning/test_profile_loader.py` with model-only tests (profile loading tests come in the next steps):

```python
from uuid import UUID

from conftest import make_normalized_article

from app.reasoning.models import (
    InterestBlock,
    ScoredArticle,
    ScoringResult,
    UserProfile,
)


def test_interest_block_defaults():
    block = InterestBlock(label="Test", text="Some interest")
    assert block.label == "Test"
    assert block.text == "Some interest"
    assert block.embedding == []


def test_user_profile_creation():
    profile = UserProfile(
        user_id=UUID("a1b2c3d4-e5f6-7890-abcd-ef1234567890"),
        name="Test User",
        interest_blocks=[
            InterestBlock(label="Role", text="I work in policy"),
        ],
    )
    assert profile.name == "Test User"
    assert len(profile.interest_blocks) == 1


def test_scored_article_defaults():
    article = make_normalized_article()
    scored = ScoredArticle(article=article)
    assert scored.vector_score is None
    assert scored.rerank_score is None
    assert scored.llm_score is None
    assert scored.route is None


def test_scoring_result_defaults():
    result = ScoringResult()
    assert result.candidates_retrieved == 0
    assert result.stored == 0
```

- [ ] **Step 5: Run tests**

Run: `cd src/ml-service && python -m pytest tests/reasoning/test_profile_loader.py -v`
Expected: 4 tests PASS

- [ ] **Step 6: Commit**

```bash
git add src/ml-service/app/config.py src/ml-service/profiles.json \
  src/ml-service/app/reasoning/__init__.py src/ml-service/app/reasoning/models.py \
  src/ml-service/tests/reasoning/__init__.py src/ml-service/tests/reasoning/test_profile_loader.py
git commit -m "feat: add scoring config, data models, and test profile"
```

---

## Task 2: Profile Loader

**Files:**
- Create: `src/ml-service/app/reasoning/profile_loader.py`
- Modify: `src/ml-service/tests/reasoning/test_profile_loader.py`

- [ ] **Step 1: Write failing tests**

Add to `src/ml-service/tests/reasoning/test_profile_loader.py`:

```python
import json
from unittest.mock import MagicMock, patch


@patch("app.reasoning.profile_loader.SentenceTransformer")
def test_load_profiles_parses_json(mock_st_cls):
    mock_model = MagicMock()
    mock_model.encode.return_value = [[0.1] * 384]
    mock_st_cls.return_value = mock_model

    from app.reasoning.profile_loader import ProfileLoader

    profiles_data = {
        "profiles": [
            {
                "user_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
                "name": "Test User",
                "interests": [
                    {"label": "Role", "text": "I work in policy"},
                ],
            }
        ]
    }

    loader = ProfileLoader(model_name="test-model")
    profiles = loader.load_from_dict(profiles_data)
    assert len(profiles) == 1
    assert profiles[0].name == "Test User"
    assert len(profiles[0].interest_blocks) == 1
    assert profiles[0].interest_blocks[0].label == "Role"


@patch("app.reasoning.profile_loader.SentenceTransformer")
def test_load_profiles_embeds_interests(mock_st_cls):
    mock_model = MagicMock()
    mock_model.encode.return_value = [[0.1] * 384, [0.2] * 384]
    mock_st_cls.return_value = mock_model

    from app.reasoning.profile_loader import ProfileLoader

    profiles_data = {
        "profiles": [
            {
                "user_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
                "name": "Test User",
                "interests": [
                    {"label": "A", "text": "Interest A"},
                    {"label": "B", "text": "Interest B"},
                ],
            }
        ]
    }

    loader = ProfileLoader(model_name="test-model")
    profiles = loader.load_from_dict(profiles_data)
    assert len(profiles[0].interest_blocks[0].embedding) == 384
    assert len(profiles[0].interest_blocks[1].embedding) == 384
    mock_model.encode.assert_called_once()


@patch("app.reasoning.profile_loader.SentenceTransformer")
def test_load_profiles_from_file(mock_st_cls, tmp_path):
    mock_model = MagicMock()
    mock_model.encode.return_value = [[0.5] * 384]
    mock_st_cls.return_value = mock_model

    from app.reasoning.profile_loader import ProfileLoader

    profiles_data = {
        "profiles": [
            {
                "user_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
                "name": "File User",
                "interests": [
                    {"label": "Role", "text": "I analyze data"},
                ],
            }
        ]
    }
    path = tmp_path / "profiles.json"
    path.write_text(json.dumps(profiles_data))

    loader = ProfileLoader(model_name="test-model")
    profiles = loader.load_from_file(str(path))
    assert profiles[0].name == "File User"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd src/ml-service && python -m pytest tests/reasoning/test_profile_loader.py::test_load_profiles_parses_json -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.reasoning.profile_loader'`

- [ ] **Step 3: Implement ProfileLoader**

Create `src/ml-service/app/reasoning/profile_loader.py`:

```python
import json
import logging
from uuid import UUID

from sentence_transformers import SentenceTransformer

from app.reasoning.models import InterestBlock, UserProfile

logger = logging.getLogger(__name__)


class ProfileLoader:
    """Loads user profiles from config and embeds interest blocks."""

    def __init__(self, model_name: str):
        self.model = SentenceTransformer(model_name)

    def load_from_file(self, path: str) -> list[UserProfile]:
        with open(path) as f:
            data = json.load(f)
        return self.load_from_dict(data)

    def load_from_dict(self, data: dict) -> list[UserProfile]:
        profiles = []
        for entry in data["profiles"]:
            blocks = [
                InterestBlock(label=i["label"], text=i["text"])
                for i in entry["interests"]
            ]

            # Batch-embed all interest texts for this profile
            texts = [b.text for b in blocks]
            embeddings = self.model.encode(texts)
            for block, embedding in zip(blocks, embeddings):
                block.embedding = embedding.tolist()

            profile = UserProfile(
                user_id=UUID(entry["user_id"]),
                name=entry["name"],
                interest_blocks=blocks,
            )
            profiles.append(profile)
            logger.info(
                "Loaded profile '%s' with %d interest blocks",
                profile.name,
                len(blocks),
            )

        return profiles
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd src/ml-service && python -m pytest tests/reasoning/test_profile_loader.py -v`
Expected: 7 tests PASS (4 model tests + 3 loader tests)

- [ ] **Step 5: Commit**

```bash
git add src/ml-service/app/reasoning/profile_loader.py \
  src/ml-service/tests/reasoning/test_profile_loader.py
git commit -m "feat: add profile loader with interest embedding"
```

---

## Task 3: LLM Provider Interface and Ollama Implementation

**Files:**
- Create: `src/ml-service/app/reasoning/providers/__init__.py`
- Create: `src/ml-service/app/reasoning/providers/base.py`
- Create: `src/ml-service/app/reasoning/providers/ollama.py`
- Test: `src/ml-service/tests/reasoning/test_ollama_provider.py`

- [ ] **Step 1: Write failing tests**

Create `src/ml-service/tests/reasoning/test_ollama_provider.py`:

```python
from unittest.mock import MagicMock, patch


@patch("app.reasoning.providers.ollama.httpx")
def test_generate_returns_text(mock_httpx):
    mock_response = MagicMock()
    mock_response.json.return_value = {"response": "Hello world"}
    mock_response.raise_for_status = MagicMock()
    mock_httpx.post.return_value = mock_response

    from app.reasoning.providers.ollama import OllamaProvider

    provider = OllamaProvider(
        base_url="http://localhost:11434", model="gemma4", timeout=30
    )
    result = provider.generate("Say hello")
    assert result == "Hello world"
    mock_httpx.post.assert_called_once()


@patch("app.reasoning.providers.ollama.httpx")
def test_generate_with_system_prompt(mock_httpx):
    mock_response = MagicMock()
    mock_response.json.return_value = {"response": "System aware"}
    mock_response.raise_for_status = MagicMock()
    mock_httpx.post.return_value = mock_response

    from app.reasoning.providers.ollama import OllamaProvider

    provider = OllamaProvider(
        base_url="http://localhost:11434", model="gemma4", timeout=30
    )
    provider.generate("Prompt", system="You are helpful")

    call_args = mock_httpx.post.call_args
    body = call_args[1]["json"]
    assert body["system"] == "You are helpful"


@patch("app.reasoning.providers.ollama.httpx")
def test_generate_json_parses_response(mock_httpx):
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "response": '{"score": 7, "explanation": "Relevant"}'
    }
    mock_response.raise_for_status = MagicMock()
    mock_httpx.post.return_value = mock_response

    from app.reasoning.providers.ollama import OllamaProvider

    provider = OllamaProvider(
        base_url="http://localhost:11434", model="gemma4", timeout=30
    )
    result = provider.generate_json("Score this")
    assert result["score"] == 7
    assert result["explanation"] == "Relevant"

    call_args = mock_httpx.post.call_args
    body = call_args[1]["json"]
    assert body["format"] == "json"


@patch("app.reasoning.providers.ollama.httpx")
def test_chat_returns_content_and_tool_calls(mock_httpx):
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "message": {
            "content": "I'll help with that",
            "tool_calls": [
                {
                    "function": {
                        "name": "search",
                        "arguments": {"query": "deer disease"},
                    }
                }
            ],
        }
    }
    mock_response.raise_for_status = MagicMock()
    mock_httpx.post.return_value = mock_response

    from app.reasoning.providers.ollama import OllamaProvider

    provider = OllamaProvider(
        base_url="http://localhost:11434", model="gemma4", timeout=30
    )
    result = provider.chat(
        messages=[{"role": "user", "content": "Find deer diseases"}],
        tools=[{"type": "function", "function": {"name": "search"}}],
    )
    assert result["content"] == "I'll help with that"
    assert len(result["tool_calls"]) == 1


@patch("app.reasoning.providers.ollama.httpx")
def test_chat_without_tool_calls(mock_httpx):
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "message": {"content": "Just a response"}
    }
    mock_response.raise_for_status = MagicMock()
    mock_httpx.post.return_value = mock_response

    from app.reasoning.providers.ollama import OllamaProvider

    provider = OllamaProvider(
        base_url="http://localhost:11434", model="gemma4", timeout=30
    )
    result = provider.chat(
        messages=[{"role": "user", "content": "Hello"}],
    )
    assert result["content"] == "Just a response"
    assert result["tool_calls"] is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd src/ml-service && python -m pytest tests/reasoning/test_ollama_provider.py::test_generate_returns_text -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Create the abstract LlmProvider**

Create `src/ml-service/app/reasoning/providers/__init__.py` (empty file).

Create `src/ml-service/app/reasoning/providers/base.py`:

```python
from abc import ABC, abstractmethod


class LlmProvider(ABC):
    """Abstract interface for LLM providers."""

    @abstractmethod
    def generate(self, prompt: str, system: str | None = None) -> str:
        """Send a prompt, get text back."""

    @abstractmethod
    def generate_json(self, prompt: str, system: str | None = None) -> dict:
        """Send a prompt, get parsed JSON back."""

    @abstractmethod
    def chat(
        self,
        messages: list[dict],
        system: str | None = None,
        tools: list[dict] | None = None,
    ) -> dict:
        """Multi-turn conversation with optional tool use.

        Returns: {"content": str, "tool_calls": list[dict] | None}
        """
```

- [ ] **Step 4: Implement OllamaProvider**

Create `src/ml-service/app/reasoning/providers/ollama.py`:

```python
import json
import logging

import httpx

from app.reasoning.providers.base import LlmProvider

logger = logging.getLogger(__name__)


class OllamaProvider(LlmProvider):
    """LLM provider using Ollama's REST API."""

    def __init__(self, base_url: str, model: str, timeout: int = 120):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout

    def generate(self, prompt: str, system: str | None = None) -> str:
        body = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
        }
        if system:
            body["system"] = system

        response = httpx.post(
            f"{self.base_url}/api/generate",
            json=body,
            timeout=self.timeout,
        )
        response.raise_for_status()
        return response.json()["response"]

    def generate_json(self, prompt: str, system: str | None = None) -> dict:
        body = {
            "model": self.model,
            "prompt": prompt,
            "format": "json",
            "stream": False,
        }
        if system:
            body["system"] = system

        response = httpx.post(
            f"{self.base_url}/api/generate",
            json=body,
            timeout=self.timeout,
        )
        response.raise_for_status()
        return json.loads(response.json()["response"])

    def chat(
        self,
        messages: list[dict],
        system: str | None = None,
        tools: list[dict] | None = None,
    ) -> dict:
        body = {
            "model": self.model,
            "messages": messages,
            "stream": False,
        }
        if system:
            body["messages"] = [
                {"role": "system", "content": system}
            ] + body["messages"]
        if tools:
            body["tools"] = tools

        response = httpx.post(
            f"{self.base_url}/api/chat",
            json=body,
            timeout=self.timeout,
        )
        response.raise_for_status()
        message = response.json()["message"]
        return {
            "content": message.get("content", ""),
            "tool_calls": message.get("tool_calls") or None,
        }
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd src/ml-service && python -m pytest tests/reasoning/test_ollama_provider.py -v`
Expected: 5 tests PASS

- [ ] **Step 6: Commit**

```bash
git add src/ml-service/app/reasoning/providers/__init__.py \
  src/ml-service/app/reasoning/providers/base.py \
  src/ml-service/app/reasoning/providers/ollama.py \
  src/ml-service/tests/reasoning/test_ollama_provider.py
git commit -m "feat: add LLM provider interface and Ollama implementation"
```

---

## Task 4: Tier 1 — Vector Retriever

**Files:**
- Create: `src/ml-service/app/reasoning/retriever.py`
- Test: `src/ml-service/tests/reasoning/test_retriever.py`

The retriever queries Qdrant with each interest vector, merges results, deduplicates, and loads full article data from PostgreSQL. Qdrant stores embeddings + metadata payloads (see `app/ingestion/embedder.py:54-63`), but not full article content — that's in PostgreSQL.

- [ ] **Step 1: Write failing tests**

Create `src/ml-service/tests/reasoning/test_retriever.py`:

```python
from unittest.mock import MagicMock
from uuid import UUID, uuid4

from conftest import make_normalized_article

from app.reasoning.models import InterestBlock, ScoredArticle, UserProfile


def _make_profile(num_interests=2):
    blocks = [
        InterestBlock(
            label=f"Interest {i}",
            text=f"I care about topic {i}",
            embedding=[float(i * 0.1)] * 384,
        )
        for i in range(num_interests)
    ]
    return UserProfile(
        user_id=UUID("a1b2c3d4-e5f6-7890-abcd-ef1234567890"),
        name="Test User",
        interest_blocks=blocks,
    )


def _make_qdrant_hit(article_id, score):
    hit = MagicMock()
    hit.id = str(article_id)
    hit.score = score
    hit.payload = {
        "title": "Test Article",
        "source_name": "Test Source",
        "url": f"http://example.com/{article_id}",
        "published_at": "2026-04-08T12:00:00+00:00",
    }
    return hit


def test_retriever_queries_per_interest_vector():
    from app.reasoning.retriever import ArticleRetriever

    mock_qdrant = MagicMock()
    mock_qdrant.search.return_value = []
    mock_conn = MagicMock()

    retriever = ArticleRetriever(
        qdrant_client=mock_qdrant,
        collection="articles",
        conn=mock_conn,
        top_k=50,
        date_days=7,
    )
    profile = _make_profile(num_interests=3)
    retriever.retrieve(profile)

    assert mock_qdrant.search.call_count == 3


def test_retriever_deduplicates_across_interests():
    from app.reasoning.retriever import ArticleRetriever

    article_id = uuid4()
    mock_qdrant = MagicMock()
    # Same article returned by both interest queries, different scores
    mock_qdrant.search.side_effect = [
        [_make_qdrant_hit(article_id, 0.7)],
        [_make_qdrant_hit(article_id, 0.9)],
    ]

    article = make_normalized_article(id=article_id)
    mock_conn = MagicMock()
    mock_conn.execute.return_value.fetchall.return_value = [
        {
            "id": str(article_id),
            "url": article.url,
            "title": article.title,
            "title_normalized": article.title_normalized,
            "raw_content": article.raw_content,
            "content_hash": article.content_hash,
            "source_name": article.source_name,
            "author": article.author,
            "author_normalized": article.author_normalized,
            "published_at": article.published_at,
            "fetched_at": article.fetched_at,
        }
    ]

    retriever = ArticleRetriever(
        qdrant_client=mock_qdrant,
        collection="articles",
        conn=mock_conn,
        top_k=50,
        date_days=7,
    )
    profile = _make_profile(num_interests=2)
    results = retriever.retrieve(profile)

    # Should be deduplicated to 1 article with the highest score
    assert len(results) == 1
    assert results[0].vector_score == 0.9


def test_retriever_returns_scored_articles():
    from app.reasoning.retriever import ArticleRetriever

    id1 = uuid4()
    id2 = uuid4()
    mock_qdrant = MagicMock()
    mock_qdrant.search.return_value = [
        _make_qdrant_hit(id1, 0.8),
        _make_qdrant_hit(id2, 0.6),
    ]

    a1 = make_normalized_article(id=id1)
    a2 = make_normalized_article(id=id2)
    mock_conn = MagicMock()
    mock_conn.execute.return_value.fetchall.return_value = [
        {
            "id": str(id1), "url": a1.url, "title": a1.title,
            "title_normalized": a1.title_normalized, "raw_content": a1.raw_content,
            "content_hash": a1.content_hash, "source_name": a1.source_name,
            "author": a1.author, "author_normalized": a1.author_normalized,
            "published_at": a1.published_at, "fetched_at": a1.fetched_at,
        },
        {
            "id": str(id2), "url": a2.url, "title": a2.title,
            "title_normalized": a2.title_normalized, "raw_content": a2.raw_content,
            "content_hash": a2.content_hash, "source_name": a2.source_name,
            "author": a2.author, "author_normalized": a2.author_normalized,
            "published_at": a2.published_at, "fetched_at": a2.fetched_at,
        },
    ]

    retriever = ArticleRetriever(
        qdrant_client=mock_qdrant,
        collection="articles",
        conn=mock_conn,
        top_k=50,
        date_days=7,
    )
    profile = _make_profile(num_interests=1)
    results = retriever.retrieve(profile)

    assert len(results) == 2
    assert all(isinstance(r, ScoredArticle) for r in results)
    assert results[0].vector_score == 0.8


def test_retriever_handles_empty_results():
    from app.reasoning.retriever import ArticleRetriever

    mock_qdrant = MagicMock()
    mock_qdrant.search.return_value = []
    mock_conn = MagicMock()

    retriever = ArticleRetriever(
        qdrant_client=mock_qdrant,
        collection="articles",
        conn=mock_conn,
        top_k=50,
        date_days=7,
    )
    profile = _make_profile(num_interests=1)
    results = retriever.retrieve(profile)

    assert results == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd src/ml-service && python -m pytest tests/reasoning/test_retriever.py::test_retriever_queries_per_interest_vector -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement ArticleRetriever**

Create `src/ml-service/app/reasoning/retriever.py`:

```python
import logging
from datetime import datetime, timedelta, timezone
from uuid import UUID

import psycopg
from qdrant_client import QdrantClient
from qdrant_client.models import FieldCondition, Filter, MatchValue, Range

from app.ingestion.models import NormalizedArticle
from app.reasoning.models import ScoredArticle, UserProfile

logger = logging.getLogger(__name__)


class ArticleRetriever:
    """Tier 1: Retrieves candidate articles from Qdrant via multi-vector search."""

    def __init__(
        self,
        qdrant_client: QdrantClient,
        collection: str,
        conn: psycopg.Connection,
        top_k: int = 50,
        date_days: int = 7,
    ):
        self.qdrant = qdrant_client
        self.collection = collection
        self.conn = conn
        self.top_k = top_k
        self.date_days = date_days

    def retrieve(self, profile: UserProfile) -> list[ScoredArticle]:
        # Query Qdrant once per interest vector
        candidates: dict[str, float] = {}  # article_id -> best score

        for block in profile.interest_blocks:
            hits = self.qdrant.search(
                collection_name=self.collection,
                query_vector=block.embedding,
                limit=self.top_k,
            )
            for hit in hits:
                article_id = hit.id
                score = hit.score
                if article_id not in candidates or score > candidates[article_id]:
                    candidates[article_id] = score

        if not candidates:
            logger.info("No candidates found in Qdrant")
            return []

        logger.info(
            "Retrieved %d unique candidates from Qdrant", len(candidates)
        )

        # Load full article data from PostgreSQL
        article_ids = list(candidates.keys())
        articles = self._load_articles(article_ids)

        # Build ScoredArticle list
        results = []
        for article in articles:
            article_id_str = str(article.id)
            if article_id_str in candidates:
                results.append(
                    ScoredArticle(
                        article=article,
                        vector_score=candidates[article_id_str],
                    )
                )

        results.sort(key=lambda s: s.vector_score or 0, reverse=True)
        return results

    def _load_articles(self, article_ids: list[str]) -> list[NormalizedArticle]:
        if not article_ids:
            return []

        placeholders = ", ".join(["%s"] * len(article_ids))
        rows = self.conn.execute(
            f"""
            SELECT id, url, title, title_normalized, raw_content,
                   content_hash, source_name, author, author_normalized,
                   published_at, fetched_at
            FROM articles
            WHERE id IN ({placeholders})
            """,
            article_ids,
        ).fetchall()

        return [
            NormalizedArticle(
                id=UUID(row["id"]) if isinstance(row["id"], str) else row["id"],
                url=row["url"],
                title=row["title"],
                title_normalized=row["title_normalized"] or "",
                raw_content=row["raw_content"] or "",
                content_hash=row["content_hash"] or "",
                source_name=row["source_name"],
                author=row["author"],
                author_normalized=row["author_normalized"],
                published_at=row["published_at"],
                fetched_at=row["fetched_at"],
            )
            for row in rows
        ]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd src/ml-service && python -m pytest tests/reasoning/test_retriever.py -v`
Expected: 4 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/ml-service/app/reasoning/retriever.py \
  src/ml-service/tests/reasoning/test_retriever.py
git commit -m "feat: add Tier 1 vector retriever with Qdrant multi-vector search"
```

---

## Task 5: Tier 2 — Cross-Encoder Reranker

**Files:**
- Create: `src/ml-service/app/reasoning/reranker.py`
- Test: `src/ml-service/tests/reasoning/test_reranker.py`

The reranker loads a cross-encoder model and scores each article against the best-matching interest block. The `sentence_transformers.CrossEncoder` class handles this — it's the same `sentence-transformers` package from Plan 2, just a different model class.

- [ ] **Step 1: Write failing tests**

Create `src/ml-service/tests/reasoning/test_reranker.py`:

```python
from unittest.mock import MagicMock, patch
from uuid import UUID

from conftest import make_normalized_article

from app.reasoning.models import InterestBlock, ScoredArticle, UserProfile
import numpy as np


def _make_profile():
    return UserProfile(
        user_id=UUID("a1b2c3d4-e5f6-7890-abcd-ef1234567890"),
        name="Test User",
        interest_blocks=[
            InterestBlock(label="Role", text="Environmental policy analyst", embedding=[0.1] * 384),
            InterestBlock(label="Wildlife", text="Deer population management", embedding=[0.2] * 384),
        ],
    )


def _make_scored(vector_score=0.8):
    return ScoredArticle(
        article=make_normalized_article(),
        vector_score=vector_score,
    )


@patch("app.reasoning.reranker.CrossEncoder")
def test_reranker_scores_all_articles(mock_ce_cls):
    mock_model = MagicMock()
    # predict returns scores for each (query, doc) pair
    # 2 interests x 3 articles = 6 pairs
    mock_model.predict.return_value = np.array([0.5, 0.3, 0.7, 0.8, 0.2, 0.9])
    mock_ce_cls.return_value = mock_model

    from app.reasoning.reranker import ArticleReranker

    reranker = ArticleReranker(model_name="test-model")
    profile = _make_profile()
    articles = [_make_scored() for _ in range(3)]

    results = reranker.rerank(articles, profile)

    assert len(results) == 3
    assert all(r.rerank_score is not None for r in results)


@patch("app.reasoning.reranker.CrossEncoder")
def test_reranker_keeps_best_interest_score(mock_ce_cls):
    mock_model = MagicMock()
    # 2 interests x 1 article = 2 pairs
    # Interest 0 gives 0.3, Interest 1 gives 0.9 — should keep 0.9
    mock_model.predict.return_value = np.array([0.3, 0.9])
    mock_ce_cls.return_value = mock_model

    from app.reasoning.reranker import ArticleReranker

    reranker = ArticleReranker(model_name="test-model")
    profile = _make_profile()
    articles = [_make_scored()]

    results = reranker.rerank(articles, profile)

    assert results[0].rerank_score == 0.9


@patch("app.reasoning.reranker.CrossEncoder")
def test_reranker_builds_correct_pairs(mock_ce_cls):
    mock_model = MagicMock()
    mock_model.predict.return_value = np.array([0.5, 0.5])
    mock_ce_cls.return_value = mock_model

    from app.reasoning.reranker import ArticleReranker

    reranker = ArticleReranker(model_name="test-model")
    profile = _make_profile()
    article = make_normalized_article(title="Deer Disease Found", raw_content="Full text about deer " * 30)
    articles = [ScoredArticle(article=article, vector_score=0.8)]

    reranker.rerank(articles, profile)

    pairs = mock_model.predict.call_args[0][0]
    # 2 interests x 1 article = 2 pairs
    assert len(pairs) == 2
    # Each pair is (interest_text, article_title + content[:512])
    assert pairs[0][0] == "Environmental policy analyst"
    assert pairs[1][0] == "Deer population management"
    assert pairs[0][1].startswith("Deer Disease Found\n")


@patch("app.reasoning.reranker.CrossEncoder")
def test_reranker_preserves_vector_score(mock_ce_cls):
    mock_model = MagicMock()
    mock_model.predict.return_value = np.array([0.6, 0.4])
    mock_ce_cls.return_value = mock_model

    from app.reasoning.reranker import ArticleReranker

    reranker = ArticleReranker(model_name="test-model")
    profile = _make_profile()
    articles = [_make_scored(vector_score=0.75)]

    results = reranker.rerank(articles, profile)

    assert results[0].vector_score == 0.75
    assert results[0].rerank_score is not None


@patch("app.reasoning.reranker.CrossEncoder")
def test_reranker_handles_empty_list(mock_ce_cls):
    mock_ce_cls.return_value = MagicMock()

    from app.reasoning.reranker import ArticleReranker

    reranker = ArticleReranker(model_name="test-model")
    profile = _make_profile()

    results = reranker.rerank([], profile)
    assert results == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd src/ml-service && python -m pytest tests/reasoning/test_reranker.py::test_reranker_scores_all_articles -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement ArticleReranker**

Create `src/ml-service/app/reasoning/reranker.py`:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd src/ml-service && python -m pytest tests/reasoning/test_reranker.py -v`
Expected: 5 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/ml-service/app/reasoning/reranker.py \
  src/ml-service/tests/reasoning/test_reranker.py
git commit -m "feat: add Tier 2 cross-encoder reranker"
```

---

## Task 6: Cascade Router

**Files:**
- Create: `src/ml-service/app/reasoning/cascade_router.py`
- Test: `src/ml-service/tests/reasoning/test_cascade_router.py`

The router splits Tier 2 output into three buckets based on rerank score percentiles: clear-pass (top N), borderline (30th–70th percentile), and rejected (below 30th). It also randomly samples from rejected for the safety net.

- [ ] **Step 1: Write failing tests**

Create `src/ml-service/tests/reasoning/test_cascade_router.py`:

```python
import random
from uuid import uuid4

from conftest import make_normalized_article

from app.reasoning.models import ScoredArticle


def _make_scored(rerank_score):
    return ScoredArticle(
        article=make_normalized_article(id=uuid4()),
        vector_score=0.5,
        rerank_score=rerank_score,
    )


def test_router_clear_pass_takes_top_n():
    from app.reasoning.cascade_router import CascadeRouter

    router = CascadeRouter(clear_pass_count=3, safety_net_count=2)
    articles = [_make_scored(score) for score in [0.9, 0.8, 0.7, 0.6, 0.5, 0.4, 0.3, 0.2, 0.1]]

    result = router.route(articles)

    assert len(result.clear_pass) == 3
    # Top 3 by rerank_score
    scores = [a.rerank_score for a in result.clear_pass]
    assert scores == [0.9, 0.8, 0.7]


def test_router_borderline_between_thresholds():
    from app.reasoning.cascade_router import CascadeRouter

    router = CascadeRouter(clear_pass_count=2, safety_net_count=1)
    # 10 articles with evenly spaced scores
    articles = [_make_scored(i / 10) for i in range(10, 0, -1)]

    result = router.route(articles)

    # Clear pass = top 2 (1.0, 0.9)
    assert len(result.clear_pass) == 2
    # Borderline = between 30th and 70th percentile (excluding clear-pass)
    # All borderline articles should have scores in the middle range
    for a in result.borderline:
        assert a not in result.clear_pass


def test_router_safety_net_samples_from_rejected():
    from app.reasoning.cascade_router import CascadeRouter

    random.seed(42)  # Deterministic for testing
    router = CascadeRouter(clear_pass_count=2, safety_net_count=3)
    articles = [_make_scored(i / 20) for i in range(20, 0, -1)]

    result = router.route(articles)

    assert len(result.safety_net) <= 3
    # Safety net articles should NOT overlap with clear_pass or borderline
    safety_ids = {id(a) for a in result.safety_net}
    clear_ids = {id(a) for a in result.clear_pass}
    border_ids = {id(a) for a in result.borderline}
    assert safety_ids.isdisjoint(clear_ids)
    assert safety_ids.isdisjoint(border_ids)


def test_router_sets_route_on_articles():
    from app.reasoning.cascade_router import CascadeRouter

    router = CascadeRouter(clear_pass_count=2, safety_net_count=1)
    articles = [_make_scored(score) for score in [0.9, 0.8, 0.5, 0.2, 0.1]]

    result = router.route(articles)

    for a in result.clear_pass:
        assert a.route == "clear_pass"
    for a in result.borderline:
        assert a.route == "borderline"
    for a in result.safety_net:
        assert a.route == "safety_net"


def test_router_handles_fewer_articles_than_clear_pass():
    from app.reasoning.cascade_router import CascadeRouter

    router = CascadeRouter(clear_pass_count=5, safety_net_count=3)
    articles = [_make_scored(0.9), _make_scored(0.8)]

    result = router.route(articles)

    # All articles become clear_pass when fewer than count
    assert len(result.clear_pass) == 2
    assert len(result.borderline) == 0
    assert len(result.safety_net) == 0


def test_router_handles_empty_list():
    from app.reasoning.cascade_router import CascadeRouter

    router = CascadeRouter(clear_pass_count=5, safety_net_count=3)
    result = router.route([])

    assert result.clear_pass == []
    assert result.borderline == []
    assert result.safety_net == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd src/ml-service && python -m pytest tests/reasoning/test_cascade_router.py::test_router_clear_pass_takes_top_n -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement CascadeRouter**

Create `src/ml-service/app/reasoning/cascade_router.py`:

```python
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
        high_threshold = _percentile(scores, BORDERLINE_HIGH_PERCENTILE)

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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd src/ml-service && python -m pytest tests/reasoning/test_cascade_router.py -v`
Expected: 6 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/ml-service/app/reasoning/cascade_router.py \
  src/ml-service/tests/reasoning/test_cascade_router.py
git commit -m "feat: add cascade router for Tier 2 to Tier 3 routing"
```

---

## Task 7: Tier 3 — LLM Scorer

**Files:**
- Create: `src/ml-service/app/reasoning/llm_scorer.py`
- Test: `src/ml-service/tests/reasoning/test_llm_scorer.py`

The LLM scorer sends each article + the user's full profile to Ollama/Gemma 4 via `generate_json()`. It parses the structured response (score 1-10, explanation, priority) and logs cascade misses from safety-net articles.

- [ ] **Step 1: Write failing tests**

Create `src/ml-service/tests/reasoning/test_llm_scorer.py`:

```python
from unittest.mock import MagicMock, call
from uuid import UUID, uuid4

from conftest import make_normalized_article

from app.reasoning.models import InterestBlock, ScoredArticle, UserProfile


def _make_profile():
    return UserProfile(
        user_id=UUID("a1b2c3d4-e5f6-7890-abcd-ef1234567890"),
        name="Test User",
        interest_blocks=[
            InterestBlock(label="Role", text="Environmental policy", embedding=[]),
        ],
    )


def _make_scored(route="borderline", rerank_score=0.5):
    return ScoredArticle(
        article=make_normalized_article(id=uuid4()),
        vector_score=0.7,
        rerank_score=rerank_score,
        route=route,
    )


def test_scorer_assigns_llm_score():
    from app.reasoning.llm_scorer import LlmScorer

    mock_provider = MagicMock()
    mock_provider.generate_json.return_value = {
        "score": 8,
        "explanation": "Highly relevant to environmental policy",
        "priority": "important",
    }

    scorer = LlmScorer(provider=mock_provider, threshold=5)
    profile = _make_profile()
    articles = [_make_scored()]

    results = scorer.score(articles, profile)

    assert len(results) == 1
    assert results[0].llm_score == 8
    assert results[0].llm_explanation == "Highly relevant to environmental policy"
    assert results[0].priority == "important"


def test_scorer_filters_below_threshold():
    from app.reasoning.llm_scorer import LlmScorer

    mock_provider = MagicMock()
    mock_provider.generate_json.side_effect = [
        {"score": 8, "explanation": "Relevant", "priority": "important"},
        {"score": 3, "explanation": "Not relevant", "priority": "routine"},
    ]

    scorer = LlmScorer(provider=mock_provider, threshold=5)
    profile = _make_profile()
    articles = [_make_scored(), _make_scored()]

    results = scorer.score(articles, profile)

    assert len(results) == 1
    assert results[0].llm_score == 8


def test_scorer_logs_cascade_misses(caplog):
    from app.reasoning.llm_scorer import LlmScorer

    mock_provider = MagicMock()
    mock_provider.generate_json.return_value = {
        "score": 9,
        "explanation": "Very relevant but missed by reranker",
        "priority": "critical",
    }

    scorer = LlmScorer(provider=mock_provider, threshold=5)
    profile = _make_profile()
    safety_net_article = _make_scored(route="safety_net")

    import logging
    with caplog.at_level(logging.WARNING):
        results = scorer.score([safety_net_article], profile)

    assert len(results) == 1
    assert "CASCADE MISS" in caplog.text


def test_scorer_handles_malformed_json():
    from app.reasoning.llm_scorer import LlmScorer

    mock_provider = MagicMock()
    mock_provider.generate_json.side_effect = Exception("Invalid JSON")

    scorer = LlmScorer(provider=mock_provider, threshold=5)
    profile = _make_profile()
    articles = [_make_scored()]

    results = scorer.score(articles, profile)

    # Article should be skipped on error, not crash
    assert len(results) == 0


def test_scorer_includes_profile_in_prompt():
    from app.reasoning.llm_scorer import LlmScorer

    mock_provider = MagicMock()
    mock_provider.generate_json.return_value = {
        "score": 7, "explanation": "Relevant", "priority": "routine"
    }

    scorer = LlmScorer(provider=mock_provider, threshold=5)
    profile = _make_profile()
    articles = [_make_scored()]

    scorer.score(articles, profile)

    prompt = mock_provider.generate_json.call_args[0][0]
    assert "Environmental policy" in prompt
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd src/ml-service && python -m pytest tests/reasoning/test_llm_scorer.py::test_scorer_assigns_llm_score -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement LlmScorer**

Create `src/ml-service/app/reasoning/llm_scorer.py`:

```python
import logging

from app.reasoning.models import ScoredArticle, UserProfile
from app.reasoning.providers.base import LlmProvider

logger = logging.getLogger(__name__)

SCORING_SYSTEM_PROMPT = """You are a news relevance scorer. Given a user's interest profile and an article, assess how relevant the article is to the user.

Respond with JSON only:
{
  "score": <integer 1-10>,
  "explanation": "<1-2 sentences explaining why this is or isn't relevant>",
  "priority": "<routine|important|critical>"
}

Score guide:
- 1-3: Not relevant to the user's interests
- 4-5: Tangentially related, background awareness only
- 6-7: Relevant, the user should know about this
- 8-9: Highly relevant, directly impacts their work
- 10: Critical, requires immediate attention"""

CASCADE_MISS_THRESHOLD = 7


class LlmScorer:
    """Tier 3: LLM-based relevance scoring."""

    def __init__(self, provider: LlmProvider, threshold: int = 5):
        self.provider = provider
        self.threshold = threshold

    def score(
        self, articles: list[ScoredArticle], profile: UserProfile
    ) -> list[ScoredArticle]:
        profile_text = self._format_profile(profile)
        passed = []

        for scored in articles:
            try:
                result = self._score_one(scored, profile_text)
                if result is None:
                    continue

                scored.llm_score = result["score"]
                scored.llm_explanation = result["explanation"]
                scored.priority = result["priority"]

                # Log cascade misses from safety net
                if (
                    scored.route == "safety_net"
                    and scored.llm_score >= CASCADE_MISS_THRESHOLD
                ):
                    logger.warning(
                        "CASCADE MISS: Article '%s' scored %d by LLM but was "
                        "rejected by reranker (rerank_score=%.3f)",
                        scored.article.title,
                        scored.llm_score,
                        scored.rerank_score or 0,
                    )

                if scored.llm_score >= self.threshold:
                    passed.append(scored)

            except Exception:
                logger.warning(
                    "LLM scoring failed for '%s'",
                    scored.article.title,
                    exc_info=True,
                )

        logger.info(
            "LLM scored %d articles, %d passed threshold",
            len(articles),
            len(passed),
        )
        return passed

    def _score_one(self, scored: ScoredArticle, profile_text: str) -> dict | None:
        prompt = (
            f"## User Profile\n\n{profile_text}\n\n"
            f"## Article\n\n"
            f"**Title:** {scored.article.title}\n"
            f"**Source:** {scored.article.source_name}\n"
            f"**Author:** {scored.article.author or 'Unknown'}\n\n"
            f"{scored.article.raw_content[:2000]}"
        )

        result = self.provider.generate_json(prompt, system=SCORING_SYSTEM_PROMPT)

        if "score" not in result or "explanation" not in result:
            logger.warning("LLM returned incomplete JSON: %s", result)
            return None

        return result

    def _format_profile(self, profile: UserProfile) -> str:
        lines = [f"**Name:** {profile.name}\n"]
        for block in profile.interest_blocks:
            lines.append(f"**{block.label}:** {block.text}")
        return "\n\n".join(lines)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd src/ml-service && python -m pytest tests/reasoning/test_llm_scorer.py -v`
Expected: 5 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/ml-service/app/reasoning/llm_scorer.py \
  src/ml-service/tests/reasoning/test_llm_scorer.py
git commit -m "feat: add Tier 3 LLM scorer with cascade miss detection"
```

---

## Task 8: Tier 4 — LLM Summarizer

**Files:**
- Create: `src/ml-service/app/reasoning/llm_summarizer.py`
- Test: `src/ml-service/tests/reasoning/test_llm_summarizer.py`

- [ ] **Step 1: Write failing tests**

Create `src/ml-service/tests/reasoning/test_llm_summarizer.py`:

```python
from unittest.mock import MagicMock
from uuid import UUID, uuid4

from conftest import make_normalized_article

from app.reasoning.models import InterestBlock, ScoredArticle, UserProfile


def _make_profile():
    return UserProfile(
        user_id=UUID("a1b2c3d4-e5f6-7890-abcd-ef1234567890"),
        name="Test User",
        interest_blocks=[
            InterestBlock(label="Role", text="Environmental policy", embedding=[]),
        ],
    )


def _make_scored():
    return ScoredArticle(
        article=make_normalized_article(id=uuid4()),
        vector_score=0.7,
        rerank_score=0.8,
        llm_score=8,
        llm_explanation="Relevant",
        priority="important",
        route="borderline",
    )


def test_summarizer_generates_summary():
    from app.reasoning.llm_summarizer import LlmSummarizer

    mock_provider = MagicMock()
    mock_provider.generate.return_value = (
        "This article discusses new environmental regulations that directly "
        "affect Alberta's oil and gas sector."
    )

    summarizer = LlmSummarizer(provider=mock_provider)
    profile = _make_profile()
    articles = [_make_scored()]

    results = summarizer.summarize(articles, profile)

    assert len(results) == 1
    assert "environmental regulations" in results[0].summary


def test_summarizer_includes_profile_context():
    from app.reasoning.llm_summarizer import LlmSummarizer

    mock_provider = MagicMock()
    mock_provider.generate.return_value = "Summary text"

    summarizer = LlmSummarizer(provider=mock_provider)
    profile = _make_profile()
    articles = [_make_scored()]

    summarizer.summarize(articles, profile)

    prompt = mock_provider.generate.call_args[0][0]
    assert "Environmental policy" in prompt


def test_summarizer_handles_failure_gracefully():
    from app.reasoning.llm_summarizer import LlmSummarizer

    mock_provider = MagicMock()
    mock_provider.generate.side_effect = Exception("Ollama timeout")

    summarizer = LlmSummarizer(provider=mock_provider)
    profile = _make_profile()
    articles = [_make_scored()]

    results = summarizer.summarize(articles, profile)

    # Article passes through even if summary fails
    assert len(results) == 1
    assert results[0].summary is None


def test_summarizer_handles_multiple_articles():
    from app.reasoning.llm_summarizer import LlmSummarizer

    mock_provider = MagicMock()
    mock_provider.generate.side_effect = [
        "Summary for article 1",
        "Summary for article 2",
        "Summary for article 3",
    ]

    summarizer = LlmSummarizer(provider=mock_provider)
    profile = _make_profile()
    articles = [_make_scored() for _ in range(3)]

    results = summarizer.summarize(articles, profile)

    assert len(results) == 3
    assert mock_provider.generate.call_count == 3
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd src/ml-service && python -m pytest tests/reasoning/test_llm_summarizer.py::test_summarizer_generates_summary -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement LlmSummarizer**

Create `src/ml-service/app/reasoning/llm_summarizer.py`:

```python
import logging

from app.reasoning.models import ScoredArticle, UserProfile
from app.reasoning.providers.base import LlmProvider

logger = logging.getLogger(__name__)

SUMMARY_SYSTEM_PROMPT = """You are a news briefing assistant. Given a user's interest profile and an article, write a concise 2-3 sentence summary focused on why this article matters to this specific user. Do not include generic summaries — explain the relevance to their work."""


class LlmSummarizer:
    """Tier 4: Generates personalized per-article summaries."""

    def __init__(self, provider: LlmProvider):
        self.provider = provider

    def summarize(
        self, articles: list[ScoredArticle], profile: UserProfile
    ) -> list[ScoredArticle]:
        profile_text = self._format_profile(profile)

        for scored in articles:
            try:
                prompt = (
                    f"## User Profile\n\n{profile_text}\n\n"
                    f"## Article\n\n"
                    f"**Title:** {scored.article.title}\n"
                    f"**Source:** {scored.article.source_name}\n\n"
                    f"{scored.article.raw_content[:2000]}\n\n"
                    f"Write a 2-3 sentence summary explaining why this article "
                    f"matters to this user."
                )
                scored.summary = self.provider.generate(
                    prompt, system=SUMMARY_SYSTEM_PROMPT
                )
            except Exception:
                logger.warning(
                    "Summarization failed for '%s'",
                    scored.article.title,
                    exc_info=True,
                )

        logger.info(
            "Summarized %d / %d articles",
            sum(1 for a in articles if a.summary),
            len(articles),
        )
        return articles

    def _format_profile(self, profile: UserProfile) -> str:
        lines = [f"**Name:** {profile.name}\n"]
        for block in profile.interest_blocks:
            lines.append(f"**{block.label}:** {block.text}")
        return "\n\n".join(lines)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd src/ml-service && python -m pytest tests/reasoning/test_llm_summarizer.py -v`
Expected: 4 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/ml-service/app/reasoning/llm_summarizer.py \
  src/ml-service/tests/reasoning/test_llm_summarizer.py
git commit -m "feat: add Tier 4 LLM summarizer for personalized article summaries"
```

---

## Task 9: Score Normalizer

**Files:**
- Create: `src/ml-service/app/reasoning/normalizer.py`
- Test: `src/ml-service/tests/reasoning/test_normalizer.py`

The normalizer converts raw scores from different tiers into comparable percentiles, applies confidence discounting, and handles clear-pass imputation.

- [ ] **Step 1: Write failing tests**

Create `src/ml-service/tests/reasoning/test_normalizer.py`:

```python
from uuid import uuid4

from conftest import make_normalized_article

from app.reasoning.models import ScoredArticle


def _make_scored(vector_score=None, rerank_score=None, llm_score=None, route=None):
    return ScoredArticle(
        article=make_normalized_article(id=uuid4()),
        vector_score=vector_score,
        rerank_score=rerank_score,
        llm_score=llm_score,
        route=route,
    )


def test_normalizer_uses_llm_score_when_available():
    from app.reasoning.normalizer import ScoreNormalizer

    normalizer = ScoreNormalizer()
    articles = [
        _make_scored(vector_score=0.5, rerank_score=0.6, llm_score=8),
        _make_scored(vector_score=0.7, rerank_score=0.8, llm_score=6),
        _make_scored(vector_score=0.9, rerank_score=0.9, llm_score=4),
    ]

    results = normalizer.normalize(articles)

    # Article with highest LLM score should rank first
    assert results[0].llm_score == 8
    assert results[0].display_score is not None


def test_normalizer_discounts_rerank_only():
    from app.reasoning.normalizer import ScoreNormalizer

    normalizer = ScoreNormalizer()
    articles = [
        _make_scored(vector_score=0.5, rerank_score=0.9, llm_score=None),
        _make_scored(vector_score=0.5, rerank_score=0.5, llm_score=8),
    ]

    results = normalizer.normalize(articles)

    # LLM-scored article should rank higher despite lower rerank score
    llm_article = next(a for a in results if a.llm_score == 8)
    rerank_article = next(a for a in results if a.llm_score is None)
    assert llm_article.display_score > rerank_article.display_score


def test_normalizer_discounts_vector_only():
    from app.reasoning.normalizer import ScoreNormalizer

    normalizer = ScoreNormalizer()
    articles = [
        _make_scored(vector_score=0.9, rerank_score=None, llm_score=None),
        _make_scored(vector_score=0.5, rerank_score=0.5, llm_score=None),
    ]

    results = normalizer.normalize(articles)

    # Both have display scores
    assert all(a.display_score is not None for a in results)


def test_normalizer_imputes_clear_pass_on_missing_llm():
    from app.reasoning.normalizer import ScoreNormalizer

    normalizer = ScoreNormalizer()
    articles = [
        _make_scored(rerank_score=0.9, llm_score=None, route="clear_pass"),
        _make_scored(rerank_score=0.5, llm_score=9, route="borderline"),
        _make_scored(rerank_score=0.4, llm_score=7, route="borderline"),
        _make_scored(rerank_score=0.3, llm_score=5, route="borderline"),
    ]

    results = normalizer.normalize(articles)

    # Clear-pass article should get imputed score at 75th percentile of LLM scores
    clear_pass = next(a for a in results if a.route == "clear_pass")
    assert clear_pass.display_score is not None
    # It should not rank below all borderline articles
    assert clear_pass.display_score > results[-1].display_score


def test_normalizer_sorts_by_display_score_descending():
    from app.reasoning.normalizer import ScoreNormalizer

    normalizer = ScoreNormalizer()
    articles = [
        _make_scored(llm_score=3),
        _make_scored(llm_score=9),
        _make_scored(llm_score=6),
    ]

    results = normalizer.normalize(articles)

    scores = [a.display_score for a in results]
    assert scores == sorted(scores, reverse=True)


def test_normalizer_handles_single_article():
    from app.reasoning.normalizer import ScoreNormalizer

    normalizer = ScoreNormalizer()
    articles = [_make_scored(llm_score=7)]

    results = normalizer.normalize(articles)

    assert len(results) == 1
    assert results[0].display_score is not None


def test_normalizer_handles_empty_list():
    from app.reasoning.normalizer import ScoreNormalizer

    normalizer = ScoreNormalizer()
    results = normalizer.normalize([])
    assert results == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd src/ml-service && python -m pytest tests/reasoning/test_normalizer.py::test_normalizer_uses_llm_score_when_available -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement ScoreNormalizer**

Create `src/ml-service/app/reasoning/normalizer.py`:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd src/ml-service && python -m pytest tests/reasoning/test_normalizer.py -v`
Expected: 7 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/ml-service/app/reasoning/normalizer.py \
  src/ml-service/tests/reasoning/test_normalizer.py
git commit -m "feat: add score normalizer with percentile ranking and confidence discounting"
```

---

## Task 10: Scoring Repository and Database Schema

**Files:**
- Modify: `src/ml-service/app/database.py`
- Create: `src/ml-service/app/reasoning/repository.py`
- Test: `src/ml-service/tests/reasoning/test_repository.py`

- [ ] **Step 1: Add user_articles table to init_schema**

Add the `user_articles` table creation to `src/ml-service/app/database.py`, after the existing `articles` table creation:

```python
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS user_articles (
                user_id UUID NOT NULL,
                article_id UUID NOT NULL,
                status TEXT NOT NULL DEFAULT 'ready',
                vector_score REAL,
                rerank_score REAL,
                llm_score REAL,
                display_score REAL,
                summary TEXT,
                explanation TEXT,
                priority TEXT,
                route TEXT,
                profile_version INTEGER NOT NULL DEFAULT 1,
                scored_at TIMESTAMPTZ,
                briefed_at TIMESTAMPTZ,
                seen_at TIMESTAMPTZ,
                feedback TEXT,
                feedback_note TEXT,
                feedback_at TIMESTAMPTZ,
                PRIMARY KEY (user_id, article_id),
                FOREIGN KEY (article_id) REFERENCES articles(id)
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_user_articles_user_status "
            "ON user_articles(user_id, status)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_user_articles_display_score "
            "ON user_articles(user_id, display_score DESC)"
        )
```

- [ ] **Step 2: Write failing tests**

Create `src/ml-service/tests/reasoning/test_repository.py`:

```python
from datetime import datetime, timezone
from unittest.mock import MagicMock
from uuid import UUID, uuid4

from conftest import make_normalized_article

from app.reasoning.models import ScoredArticle


def _make_scored_for_storage():
    return ScoredArticle(
        article=make_normalized_article(id=uuid4()),
        vector_score=0.7,
        rerank_score=0.8,
        llm_score=8.0,
        llm_explanation="Relevant to environmental policy",
        priority="important",
        summary="This article matters because...",
        display_score=0.85,
        route="borderline",
    )


def test_repository_inserts_scored_article():
    from app.reasoning.repository import ScoringRepository

    mock_conn = MagicMock()
    repo = ScoringRepository(conn=mock_conn)

    user_id = UUID("a1b2c3d4-e5f6-7890-abcd-ef1234567890")
    scored = _make_scored_for_storage()

    repo.insert(user_id, scored, status="ready")

    mock_conn.execute.assert_called_once()
    call_args = mock_conn.execute.call_args
    sql = call_args[0][0]
    assert "INSERT INTO user_articles" in sql
    params = call_args[0][1]
    assert str(user_id) in [str(p) for p in params]


def test_repository_insert_batch():
    from app.reasoning.repository import ScoringRepository

    mock_conn = MagicMock()
    repo = ScoringRepository(conn=mock_conn)

    user_id = UUID("a1b2c3d4-e5f6-7890-abcd-ef1234567890")
    articles = [_make_scored_for_storage() for _ in range(3)]

    repo.insert_batch(user_id, articles, status="ready")

    assert mock_conn.execute.call_count == 3


def test_repository_find_ready_for_user():
    from app.reasoning.repository import ScoringRepository

    mock_conn = MagicMock()
    mock_conn.execute.return_value.fetchall.return_value = [
        {
            "article_id": str(uuid4()),
            "display_score": 0.9,
            "summary": "Summary",
            "priority": "important",
        }
    ]

    repo = ScoringRepository(conn=mock_conn)
    user_id = UUID("a1b2c3d4-e5f6-7890-abcd-ef1234567890")

    results = repo.find_by_user_and_status(user_id, "ready")

    assert len(results) == 1
    assert results[0]["display_score"] == 0.9


def test_repository_checks_already_scored():
    from app.reasoning.repository import ScoringRepository

    mock_conn = MagicMock()
    mock_conn.execute.return_value.fetchone.return_value = {"count": 1}

    repo = ScoringRepository(conn=mock_conn)
    user_id = UUID("a1b2c3d4-e5f6-7890-abcd-ef1234567890")
    article_id = uuid4()

    assert repo.is_already_scored(user_id, article_id) is True


def test_repository_commit():
    from app.reasoning.repository import ScoringRepository

    mock_conn = MagicMock()
    repo = ScoringRepository(conn=mock_conn)
    repo.commit()
    mock_conn.commit.assert_called_once()
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `cd src/ml-service && python -m pytest tests/reasoning/test_repository.py::test_repository_inserts_scored_article -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 4: Implement ScoringRepository**

Create `src/ml-service/app/reasoning/repository.py`:

```python
import logging
from datetime import datetime, timezone
from uuid import UUID

import psycopg

from app.reasoning.models import ScoredArticle

logger = logging.getLogger(__name__)


class ScoringRepository:
    """PostgreSQL CRUD for user_articles scoring results."""

    def __init__(self, conn: psycopg.Connection):
        self.conn = conn

    def insert(self, user_id: UUID, scored: ScoredArticle, status: str = "ready") -> None:
        self.conn.execute(
            """
            INSERT INTO user_articles
                (user_id, article_id, status, vector_score, rerank_score,
                 llm_score, display_score, summary, explanation, priority,
                 route, scored_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (user_id, article_id) DO NOTHING
            """,
            (
                str(user_id),
                str(scored.article.id),
                status,
                scored.vector_score,
                scored.rerank_score,
                scored.llm_score,
                scored.display_score,
                scored.summary,
                scored.llm_explanation,
                scored.priority,
                scored.route,
                datetime.now(timezone.utc),
            ),
        )

    def insert_batch(
        self, user_id: UUID, articles: list[ScoredArticle], status: str = "ready"
    ) -> None:
        for scored in articles:
            self.insert(user_id, scored, status)

    def find_by_user_and_status(self, user_id: UUID, status: str) -> list[dict]:
        rows = self.conn.execute(
            """
            SELECT article_id, display_score, summary, priority, explanation,
                   route, scored_at
            FROM user_articles
            WHERE user_id = %s AND status = %s
            ORDER BY display_score DESC
            """,
            (str(user_id), status),
        ).fetchall()
        return rows

    def is_already_scored(self, user_id: UUID, article_id: UUID) -> bool:
        row = self.conn.execute(
            "SELECT count(*) as count FROM user_articles WHERE user_id = %s AND article_id = %s",
            (str(user_id), str(article_id)),
        ).fetchone()
        return row["count"] > 0

    def commit(self) -> None:
        self.conn.commit()
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd src/ml-service && python -m pytest tests/reasoning/test_repository.py -v`
Expected: 5 tests PASS

- [ ] **Step 6: Commit**

```bash
git add src/ml-service/app/database.py \
  src/ml-service/app/reasoning/repository.py \
  src/ml-service/tests/reasoning/test_repository.py
git commit -m "feat: add user_articles table and scoring repository"
```

---

## Task 11: Scoring Pipeline Orchestrator

**Files:**
- Create: `src/ml-service/app/reasoning/pipeline.py`
- Test: `src/ml-service/tests/reasoning/test_pipeline.py`

The orchestrator wires all tiers together: retrieve → rerank → route → LLM score → summarize → normalize → store. Same singleton pattern as `app/ingestion/pipeline.py`.

- [ ] **Step 1: Write failing tests**

Create `src/ml-service/tests/reasoning/test_pipeline.py`:

```python
from unittest.mock import MagicMock
from uuid import UUID, uuid4

from conftest import make_normalized_article

from app.reasoning.cascade_router import RouteResult
from app.reasoning.models import InterestBlock, ScoredArticle, UserProfile


def _make_profile():
    return UserProfile(
        user_id=UUID("a1b2c3d4-e5f6-7890-abcd-ef1234567890"),
        name="Test User",
        interest_blocks=[
            InterestBlock(label="Role", text="Policy", embedding=[0.1] * 384),
        ],
    )


def _make_scored(route="borderline"):
    return ScoredArticle(
        article=make_normalized_article(id=uuid4()),
        vector_score=0.7,
        rerank_score=0.6,
        route=route,
    )


def _build_pipeline(**overrides):
    from app.reasoning.pipeline import ScoringPipeline

    defaults = {
        "retriever": MagicMock(),
        "reranker": MagicMock(),
        "router": MagicMock(),
        "scorer": MagicMock(),
        "summarizer": MagicMock(),
        "normalizer": MagicMock(),
        "repository": MagicMock(),
    }
    defaults.update(overrides)

    # Wire up sensible defaults
    if "retriever" not in overrides:
        defaults["retriever"].retrieve.return_value = [_make_scored()]
    if "reranker" not in overrides:
        defaults["reranker"].rerank.side_effect = lambda articles, profile: articles
    if "router" not in overrides:
        defaults["router"].route.return_value = RouteResult(
            clear_pass=[],
            borderline=[_make_scored()],
            safety_net=[],
        )
    if "scorer" not in overrides:
        scored = _make_scored()
        scored.llm_score = 8
        defaults["scorer"].score.return_value = [scored]
    if "summarizer" not in overrides:
        defaults["summarizer"].summarize.side_effect = lambda articles, profile: articles
    if "normalizer" not in overrides:
        defaults["normalizer"].normalize.side_effect = lambda articles: articles

    return ScoringPipeline(**defaults)


def test_pipeline_end_to_end():
    pipeline = _build_pipeline()
    profile = _make_profile()
    result = pipeline.run(profile)

    assert result.candidates_retrieved == 1
    assert result.reranked == 1
    assert result.llm_scored == 1
    assert result.user_id == profile.user_id


def test_pipeline_combines_router_outputs_for_scorer():
    router = MagicMock()
    clear = [_make_scored("clear_pass")]
    border = [_make_scored("borderline"), _make_scored("borderline")]
    safety = [_make_scored("safety_net")]
    router.route.return_value = RouteResult(
        clear_pass=clear, borderline=border, safety_net=safety
    )

    scorer = MagicMock()
    scorer.score.return_value = clear + border + safety

    pipeline = _build_pipeline(router=router, scorer=scorer)
    profile = _make_profile()
    pipeline.run(profile)

    # Scorer should receive all three lists combined
    scored_articles = scorer.score.call_args[0][0]
    assert len(scored_articles) == 4


def test_pipeline_stores_results():
    repository = MagicMock()

    pipeline = _build_pipeline(repository=repository)
    profile = _make_profile()
    pipeline.run(profile)

    repository.insert_batch.assert_called_once()
    repository.commit.assert_called_once()


def test_pipeline_handles_no_candidates():
    retriever = MagicMock()
    retriever.retrieve.return_value = []

    pipeline = _build_pipeline(retriever=retriever)
    profile = _make_profile()
    result = pipeline.run(profile)

    assert result.candidates_retrieved == 0
    assert result.stored == 0


def test_pipeline_handles_no_llm_passes():
    scorer = MagicMock()
    scorer.score.return_value = []

    pipeline = _build_pipeline(scorer=scorer)
    profile = _make_profile()
    result = pipeline.run(profile)

    assert result.llm_scored == 0
    assert result.summarized == 0


def test_pipeline_singleton():
    from app.reasoning.pipeline import get_scoring_pipeline, init_scoring_pipeline

    mock_pipeline = MagicMock()
    init_scoring_pipeline(mock_pipeline)

    assert get_scoring_pipeline() is mock_pipeline
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd src/ml-service && python -m pytest tests/reasoning/test_pipeline.py::test_pipeline_end_to_end -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement ScoringPipeline**

Create `src/ml-service/app/reasoning/pipeline.py`:

```python
import logging

from app.reasoning.cascade_router import CascadeRouter
from app.reasoning.llm_scorer import LlmScorer
from app.reasoning.llm_summarizer import LlmSummarizer
from app.reasoning.models import ScoringResult, UserProfile
from app.reasoning.normalizer import ScoreNormalizer
from app.reasoning.repository import ScoringRepository
from app.reasoning.retriever import ArticleRetriever
from app.reasoning.reranker import ArticleReranker

logger = logging.getLogger(__name__)

_pipeline_instance: "ScoringPipeline | None" = None


class ScoringPipeline:
    """Orchestrates the four-tier scoring cascade."""

    def __init__(
        self,
        retriever: ArticleRetriever,
        reranker: ArticleReranker,
        router: CascadeRouter,
        scorer: LlmScorer,
        summarizer: LlmSummarizer,
        normalizer: ScoreNormalizer,
        repository: ScoringRepository,
    ):
        self.retriever = retriever
        self.reranker = reranker
        self.router = router
        self.scorer = scorer
        self.summarizer = summarizer
        self.normalizer = normalizer
        self.repository = repository

    def run(self, profile: UserProfile) -> ScoringResult:
        result = ScoringResult(user_id=profile.user_id)

        # Tier 1: Vector retrieval
        candidates = self.retriever.retrieve(profile)
        result.candidates_retrieved = len(candidates)
        logger.info("Tier 1: Retrieved %d candidates", len(candidates))

        if not candidates:
            return result

        # Tier 2: Cross-encoder reranking
        reranked = self.reranker.rerank(candidates, profile)
        result.reranked = len(reranked)
        logger.info("Tier 2: Reranked %d articles", len(reranked))

        # Route to Tier 3 buckets
        route_result = self.router.route(reranked)
        to_score = route_result.clear_pass + route_result.borderline + route_result.safety_net
        logger.info(
            "Router: %d clear-pass, %d borderline, %d safety-net",
            len(route_result.clear_pass),
            len(route_result.borderline),
            len(route_result.safety_net),
        )

        if not to_score:
            return result

        # Tier 3: LLM scoring
        passed = self.scorer.score(to_score, profile)
        result.llm_scored = len(passed)
        logger.info("Tier 3: %d articles passed LLM scoring", len(passed))

        if not passed:
            return result

        # Tier 4: LLM summarization
        summarized = self.summarizer.summarize(passed, profile)
        result.summarized = sum(1 for a in summarized if a.summary)
        logger.info("Tier 4: Summarized %d articles", result.summarized)

        # Normalize scores and rank
        ranked = self.normalizer.normalize(summarized)

        # Store results
        self.repository.insert_batch(profile.user_id, ranked, status="ready")
        self.repository.commit()
        result.stored = len(ranked)

        logger.info(
            "Scoring complete for '%s': %d stored", profile.name, result.stored
        )
        return result


def get_scoring_pipeline() -> "ScoringPipeline":
    if _pipeline_instance is None:
        raise RuntimeError(
            "Scoring pipeline not initialized. Call init_scoring_pipeline() first."
        )
    return _pipeline_instance


def init_scoring_pipeline(pipeline: "ScoringPipeline") -> None:
    global _pipeline_instance
    _pipeline_instance = pipeline
    logger.info("Scoring pipeline initialized")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd src/ml-service && python -m pytest tests/reasoning/test_pipeline.py -v`
Expected: 6 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/ml-service/app/reasoning/pipeline.py \
  src/ml-service/tests/reasoning/test_pipeline.py
git commit -m "feat: add scoring pipeline orchestrator"
```

---

## Task 12: API Endpoints and Lifespan Wiring

**Files:**
- Create: `src/ml-service/app/routers/scoring.py`
- Modify: `src/ml-service/app/main.py`
- Test: `src/ml-service/tests/test_scoring_api.py`

This task adds the scoring API endpoints (same pattern as ingestion router) and wires the scoring pipeline into the FastAPI lifespan startup.

- [ ] **Step 1: Write failing tests**

Create `src/ml-service/tests/test_scoring_api.py`:

```python
from dataclasses import asdict
from unittest.mock import MagicMock, patch
from uuid import UUID

from fastapi.testclient import TestClient

from app.reasoning.models import ScoringResult


@patch("app.routers.scoring.get_scoring_pipeline")
@patch("app.routers.scoring.get_profiles")
def test_trigger_scoring_returns_result(mock_profiles, mock_get_pipeline):
    mock_profile = MagicMock()
    mock_profile.user_id = UUID("a1b2c3d4-e5f6-7890-abcd-ef1234567890")
    mock_profiles.return_value = [mock_profile]

    mock_pipeline = MagicMock()
    mock_pipeline.run.return_value = ScoringResult(
        user_id=UUID("a1b2c3d4-e5f6-7890-abcd-ef1234567890"),
        candidates_retrieved=100,
        reranked=100,
        llm_scored=15,
        summarized=12,
        stored=12,
    )
    mock_get_pipeline.return_value = mock_pipeline

    from app.main import app

    client = TestClient(app)
    response = client.post(
        "/api/scoring/trigger", headers={"X-Api-Key": "test-api-key"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["results"][0]["stored"] == 12


@patch("app.routers.scoring.get_scoring_pipeline")
@patch("app.routers.scoring.get_profiles")
def test_trigger_scoring_handles_error(mock_profiles, mock_get_pipeline):
    mock_profile = MagicMock()
    mock_profile.user_id = UUID("a1b2c3d4-e5f6-7890-abcd-ef1234567890")
    mock_profiles.return_value = [mock_profile]

    mock_pipeline = MagicMock()
    mock_pipeline.run.side_effect = Exception("Qdrant unreachable")
    mock_get_pipeline.return_value = mock_pipeline

    from app.main import app

    client = TestClient(app)
    response = client.post(
        "/api/scoring/trigger", headers={"X-Api-Key": "test-api-key"}
    )
    assert response.status_code == 500


def test_get_scoring_status():
    from app.main import app

    client = TestClient(app)
    response = client.get(
        "/api/scoring/status", headers={"X-Api-Key": "test-api-key"}
    )
    assert response.status_code == 200
    data = response.json()
    assert "running" in data
    assert "last_run_at" in data


def test_scoring_endpoints_require_api_key():
    from app.main import app

    client = TestClient(app)
    response = client.post("/api/scoring/trigger")
    assert response.status_code == 401
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd src/ml-service && python -m pytest tests/test_scoring_api.py::test_trigger_scoring_returns_result -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Create scoring router**

Create `src/ml-service/app/routers/scoring.py`:

```python
import logging
from dataclasses import asdict
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException

from app.reasoning.models import ScoringResult
from app.reasoning.pipeline import get_scoring_pipeline

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/scoring", tags=["scoring"])

_last_results: list[dict] | None = None
_last_run_at: datetime | None = None
_running = False

# Module-level profile list, set during lifespan
_profiles = []


def set_profiles(profiles):
    global _profiles
    _profiles = profiles


def get_profiles():
    return _profiles


@router.post("/trigger")
async def trigger_scoring():
    global _last_results, _last_run_at, _running

    if _running:
        return {"status": "already_running"}

    _running = True
    try:
        pipeline = get_scoring_pipeline()
        profiles = get_profiles()

        results = []
        for profile in profiles:
            result = pipeline.run(profile)
            results.append(asdict(result))

        _last_results = results
        _last_run_at = datetime.now(timezone.utc)
        return {"status": "completed", "results": results}
    except Exception as e:
        logger.exception("Scoring run failed")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        _running = False


@router.get("/status")
async def get_status():
    return {
        "running": _running,
        "last_results": _last_results,
        "last_run_at": _last_run_at.isoformat() if _last_run_at else None,
    }
```

- [ ] **Step 4: Wire scoring into main.py**

Update `src/ml-service/app/main.py` to import and register the scoring router, and wire the scoring pipeline into the lifespan. Add these imports and initialization to the lifespan function (after the ingestion pipeline init):

Add to imports at top of file:
```python
from app.routers import health, ingestion, scoring
```

Add to the lifespan function, after the ingestion pipeline initialization (before `start_scheduler`):

```python
    # Build scoring pipeline components
    from app.reasoning.cascade_router import CascadeRouter
    from app.reasoning.llm_scorer import LlmScorer
    from app.reasoning.llm_summarizer import LlmSummarizer
    from app.reasoning.normalizer import ScoreNormalizer
    from app.reasoning.pipeline import init_scoring_pipeline, ScoringPipeline
    from app.reasoning.profile_loader import ProfileLoader
    from app.reasoning.providers.ollama import OllamaProvider
    from app.reasoning.reranker import ArticleReranker
    from app.reasoning.repository import ScoringRepository
    from app.reasoning.retriever import ArticleRetriever

    profile_loader = ProfileLoader(model_name=settings.embedding_model)
    profiles = profile_loader.load_from_file(settings.profiles_path)
    scoring.set_profiles(profiles)

    llm_provider = OllamaProvider(
        base_url=settings.ollama_base_url,
        model=settings.ollama_model,
        timeout=settings.ollama_timeout,
    )

    scoring_repo = ScoringRepository(conn=conn)
    retriever = ArticleRetriever(
        qdrant_client=embedder.client,
        collection=settings.qdrant_collection,
        conn=conn,
        top_k=settings.retriever_top_k,
        date_days=settings.retriever_date_days,
    )
    reranker = ArticleReranker(model_name=settings.reranker_model)
    cascade_router = CascadeRouter(
        clear_pass_count=settings.scoring_clear_pass_count,
        safety_net_count=settings.scoring_safety_net_count,
    )
    llm_scorer = LlmScorer(
        provider=llm_provider,
        threshold=settings.scoring_llm_threshold,
    )
    llm_summarizer = LlmSummarizer(provider=llm_provider)
    score_normalizer = ScoreNormalizer()

    scoring_pipeline = ScoringPipeline(
        retriever=retriever,
        reranker=reranker,
        router=cascade_router,
        scorer=llm_scorer,
        summarizer=llm_summarizer,
        normalizer=score_normalizer,
        repository=scoring_repo,
    )
    init_scoring_pipeline(scoring_pipeline)
```

Add the router registration at the bottom of main.py:
```python
app.include_router(scoring.router)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd src/ml-service && python -m pytest tests/test_scoring_api.py -v`
Expected: 4 tests PASS

- [ ] **Step 6: Run the full test suite**

Run: `cd src/ml-service && python -m pytest -v`
Expected: All tests PASS (49 existing + ~51 new = ~100 total)

- [ ] **Step 7: Commit**

```bash
git add src/ml-service/app/routers/scoring.py \
  src/ml-service/app/main.py \
  src/ml-service/tests/test_scoring_api.py
git commit -m "feat: add scoring API endpoints and lifespan wiring"
```

---

## Spec Compliance Checklist

| Spec Requirement | Task |
|---|---|
| Four-tier cascade (vector → reranker → LLM → summary) | Tasks 4, 5, 7, 8 orchestrated in Task 11 |
| Config-seeded user profiles with embedded interests | Tasks 1, 2 |
| Multi-vector Qdrant search (one query per interest) | Task 4 |
| Cross-encoder reranking (bge-reranker-v2-m3) | Task 5 |
| Cascade routing (clear-pass / borderline / safety-net) | Task 6 |
| LLM scoring with JSON output (score, explanation, priority) | Task 7 |
| Cascade miss detection for safety-net articles | Task 7 |
| Per-article personalized summarization | Task 8 |
| Percentile normalization + confidence discounting | Task 9 |
| Clear-pass imputation | Task 9 |
| `user_articles` table with composite PK | Task 10 |
| Model-agnostic LLM provider interface | Task 3 |
| Ollama/Gemma 4 implementation | Task 3 |
| `chat()` method for future ReAct profile builder | Task 3 |
| API endpoints (trigger, status) | Task 12 |
| Lifespan wiring | Task 12 |
| Score normalization formula: `llm ?? (rerank * 0.85) ?? (vector * 0.70)` | Task 9 |

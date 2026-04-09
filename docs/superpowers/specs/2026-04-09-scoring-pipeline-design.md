# Scoring Pipeline — Design Specification

**Date:** 2026-04-09
**Status:** Approved
**Parent Spec:** `docs/superpowers/specs/2026-04-07-news-searcher-design.md` (Section 7)

---

## 1. Overview

The scoring pipeline is the core intelligence of News Searcher. It takes articles stored by the ingestion pipeline (Plan 2) and determines which ones are relevant to each user via a four-tier cascade. Each tier is dramatically cheaper than the next, filtering down the candidate set so expensive LLM calls only run on articles that truly need them.

### What This Plan Covers

- Four-tier scoring cascade (vector retrieval → cross-encoder reranking → LLM scoring → LLM summarization)
- Config-seeded user profiles with embedded interest vectors
- Score normalization and ranking
- `user_articles` table for persisting scoring results
- Model-agnostic LLM provider interface with Ollama/Gemma 4 implementation
- API endpoints for triggering and monitoring scoring runs

### What This Plan Does NOT Cover

- Executive summary / briefing generation (Plan 4)
- User management / authentication (ASP.NET side)
- ReAct-based guided profile builder (future plan)
- Feedback loop / threshold tuning
- HyDE (Hypothetical Document Embeddings) — deferred to profile builder plan

---

## 2. Architecture Decisions

### No Haystack — Direct Library Usage

The design spec suggests Haystack for the reasoning module. After analysis, we're building the cascade manually for three reasons:

1. **Complex conditional routing:** Tier 2 output fans into three buckets (clear-pass, borderline, rejected) with a safety-net sample from rejected. Haystack's DAG pipeline model doesn't naturally support this conditional fan-out.
2. **Cross-document aggregation:** Percentile-based score normalization requires seeing all articles' scores at once. Haystack's per-document processing doesn't support this.
3. **Consistency:** The ingestion pipeline (Plan 2) uses direct library usage with dependency injection. The same pattern works here.

We still use the underlying libraries Haystack would wrap: `sentence-transformers` for cross-encoder models, `qdrant-client` for vector search, and `httpx` for Ollama's REST API.

### Composable Tier Components

Each tier is its own class with dependency injection via constructor parameters. A `CascadeRouter` handles the split logic between Tier 2 and Tier 3. A thin `ScoringPipeline` orchestrator wires everything together.

**Why not a monolithic pipeline class:** The routing logic between Tier 2 → Tier 3 is the trickiest part of the cascade. Isolating it into a testable component means we can verify routing decisions without loading ML models or making LLM calls.

**Why not an abstract `ScoringTier` strategy pattern:** The four tiers have fundamentally different inputs/outputs. Tier 1 takes embeddings, Tier 2 takes text pairs, Tier 3 takes articles + profile text. Forcing a common interface would hide these real differences behind a leaky abstraction.

### Config-Seeded Profiles (No Profiles Table)

User identity and profile management belong to ASP.NET Identity (a future plan). For the scoring pipeline, we load test profiles from `profiles.json` — a config file with the Alberta policy analyst example from the spec. The pipeline accepts a `UserProfile` dataclass; it doesn't care whether it came from a config file or a database.

The `user_articles` table uses the `user_id` from the config file (a UUID). When ASP.NET user management is built, it will provide real user IDs. No `user_profiles` table is created in Python — that avoids FK conflicts with ASP.NET Identity's `users` table later.

### Ollama + Gemma 4 (Local LLM)

All LLM calls use Ollama running locally with Gemma 4. Zero cost, no API keys, no network dependency during development. A model-agnostic provider interface means swapping to Claude or OpenAI for production is a config change + one new adapter class.

---

## 3. Component Design

### File Structure

```
src/ml-service/
├── app/
│   ├── config.py                         # (modify) Add scoring settings
│   ├── database.py                       # (modify) Add user_articles schema
│   ├── main.py                           # (modify) Wire scoring pipeline into lifespan
│   ├── reasoning/
│   │   ├── __init__.py
│   │   ├── models.py                     # UserProfile, InterestBlock, ScoredArticle, ScoringResult
│   │   ├── profile_loader.py            # Load profiles.json, embed interest blocks
│   │   ├── retriever.py                 # Tier 1: Qdrant multi-vector search
│   │   ├── reranker.py                  # Tier 2: Cross-encoder reranking
│   │   ├── cascade_router.py            # Route Tier 2 output → Tier 3 buckets
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
├── profiles.json                        # Test user profile configuration
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

### Data Models

```python
@dataclass
class InterestBlock:
    label: str              # "Primary Role", "Wildlife Mandate", etc.
    text: str               # The narrative description
    embedding: list[float]  # 384-dim vector (all-MiniLM-L6-v2)

@dataclass
class UserProfile:
    user_id: UUID
    name: str
    interest_blocks: list[InterestBlock]

@dataclass
class ScoredArticle:
    article: NormalizedArticle   # From ingestion models
    vector_score: float | None
    rerank_score: float | None
    llm_score: float | None
    llm_explanation: str | None
    priority: str | None         # routine / important / critical
    summary: str | None
    display_score: float | None  # Final normalized + discounted score
    route: str | None            # clear_pass / borderline / safety_net / rejected

@dataclass
class ScoringResult:
    user_id: UUID
    candidates_retrieved: int    # After Tier 1
    reranked: int                # After Tier 2
    llm_scored: int              # After Tier 3
    summarized: int              # After Tier 4
    stored: int                  # Written to user_articles
```

---

## 4. Tier Specifications

### Tier 1: Vector Retrieval (Retriever)

**Input:** `UserProfile` with pre-embedded interest blocks
**Output:** ~200 `ScoredArticle` with `vector_score` set

- Query Qdrant once per interest vector (multi-vector search per spec Section 7)
- Each query retrieves `top_k` candidates (configurable, default: 50)
- Merge results across all interest vectors, deduplicate by article ID
- When an article matches multiple interest vectors, keep the highest score
- Filter by metadata: date range (default: last 7 days), exclude blocklisted sources
- Load full article data from PostgreSQL for candidates (Qdrant stores embeddings + metadata, not full content)
- `vector_score` = best cosine similarity across interest vectors

### Tier 2: Cross-Encoder Reranking (Reranker)

**Input:** ~200 `ScoredArticle` from Tier 1
**Output:** All articles with `rerank_score` set

- Load `BAAI/bge-reranker-v2-m3` cross-encoder model via `sentence_transformers.CrossEncoder`
- For each article, score against the best-matching interest block text
- Input pair: `(interest_text, article_title + "\n" + article_content[:512])`
- Content truncated to 512 chars to stay within model context while keeping scoring fast
- Model outputs a logit score (not a probability) — raw scores are model-dependent, which is why we normalize later

**Why `bge-reranker-v2-m3` over `ms-marco-MiniLM-L-6-v2`:** Supports longer inputs (8192 tokens vs 512), better cross-domain relevance for narrative interest descriptions. Recommended in the parent design spec.

### Cascade Router

**Input:** All articles with `rerank_score` from Tier 2
**Output:** Three lists: `clear_pass`, `borderline`, `safety_net`

Routing rules:
- **Clear-pass:** Top 5 articles by `rerank_score` (always go to Tier 3 for full LLM scoring — prevents them from being disadvantaged in ranking)
- **Borderline:** Articles with `rerank_score` between the inclusion threshold and exclusion threshold (configurable, tuned over time)
- **Rejected:** Articles below the exclusion threshold
- **Safety-net sample:** 10-15 random articles from the rejected set (measures false negative rate)

Starting thresholds will use percentile-based cutoffs rather than absolute values, since cross-encoder logit scales vary by model and data distribution. Initial values: borderline = articles between the 30th and 70th percentile of rerank scores; clear-pass = top 5 regardless of percentile; rejected = below the 30th percentile. These will be tuned with user feedback.

### Tier 3: LLM Scoring (LlmScorer)

**Input:** Three article lists from the router + `UserProfile`
**Output:** Articles with `llm_score`, `llm_explanation`, `priority` set

- Sends each article to Ollama/Gemma 4 with the full user profile as context
- Prompt asks for JSON response:
  ```json
  {
    "score": 7,
    "explanation": "This article about chronic wasting disease in Saskatchewan deer is directly relevant to your wildlife management mandate in Peace River, Alberta. CWD can spread across provincial boundaries.",
    "priority": "important"
  }
  ```
- Score: 1-10 scale (1 = completely irrelevant, 10 = critical must-read)
- Priority: `routine` (background awareness), `important` (should read today), `critical` (needs immediate attention)
- Safety-net articles that score ≥ 7 are logged as "cascade misses" — they passed LLM scoring but were rejected by the cross-encoder, indicating the Tier 2 threshold may be too aggressive
- Articles scoring below threshold (configurable, default: 5) after LLM scoring are marked rejected

### Tier 4: LLM Summarization (LlmSummarizer)

**Input:** Articles that passed Tier 3 + `UserProfile`
**Output:** Articles with `summary` set

- Runs on all articles that will be included in the briefing
- Prompt includes user profile context so the summary focuses on *why this matters to this specific user*
- Target: 2-3 sentence summary per article
- If summarization fails for an article, it still passes through with `summary = None` — the article's value is in the scoring, not the summary

---

## 5. LLM Provider Interface

### Abstract Interface

```python
class LlmProvider(ABC):
    @abstractmethod
    def generate(self, prompt: str, system: str | None = None) -> str:
        """Send a prompt, get text back."""

    @abstractmethod
    def generate_json(self, prompt: str, system: str | None = None) -> dict:
        """Send a prompt, get parsed JSON back."""

    @abstractmethod
    def chat(self, messages: list[dict], system: str | None = None,
             tools: list[dict] | None = None) -> dict:
        """Multi-turn conversation with optional tool use.
        Returns: {"content": str, "tool_calls": list[dict] | None}
        """
```

### Why Three Methods

- `generate()` — Tier 4 summaries (free-form text output)
- `generate_json()` — Tier 3 scoring (structured JSON: score, explanation, priority). Uses Ollama's `format: "json"` parameter.
- `chat()` — Not used by the scoring pipeline. Exists for the future ReAct-based guided profile builder, which needs multi-turn conversation with tool use. Defined now so adding a new provider later doesn't require retrofitting the interface.

### Ollama Implementation

- Uses Ollama's REST API via `httpx` (already a dependency)
- `POST /api/generate` for `generate()` and `generate_json()`
- `POST /api/chat` for `chat()`
- Model configurable via settings (default: `gemma4`)
- Base URL configurable (default: `http://localhost:11434`)
- Timeout configurable (default: 120s — local models can be slow on first load)

---

## 6. Score Normalization & Ranking

Raw scores from different tiers are on incomparable scales:
- Vector similarity: cosine distance, typically 0.3–0.8
- Cross-encoder: logits, model-dependent scale
- LLM scores: prompted 1–10

### Normalization Strategy

1. **Per-tier percentile normalization:** Convert each tier's raw scores to percentiles within the current scoring cycle. The 80th percentile vector score and 80th percentile LLM score both mean "better than 80% of articles scored by this method."

2. **Confidence discounting:** Apply tier-specific discount factors:
   ```
   display_score = normalized_llm_score ?? (normalized_rerank_score * 0.85) ?? (normalized_vector_score * 0.70)
   ```
   Articles that reached Tier 3 use their LLM score (most reliable). Articles that only reached Tier 2 get a 15% discount. Vector-only scores get a 30% discount.

3. **Clear-pass imputation:** If a clear-pass article skips Tier 3 for any reason (e.g., LLM timeout), it receives an imputed score at the 75th percentile of actual LLM scores. This prevents clear-pass articles from being ranked below borderline articles.

The discount factors (0.85, 0.70) are starting values from the design spec. They'll be calibrated with user feedback data over time.

---

## 7. Storage: `user_articles` Table

```sql
CREATE TABLE IF NOT EXISTS user_articles (
    user_id        UUID NOT NULL,
    article_id     UUID NOT NULL,
    status         TEXT NOT NULL DEFAULT 'ready',
    vector_score   REAL,
    rerank_score   REAL,
    llm_score      REAL,
    display_score  REAL,
    summary        TEXT,
    explanation    TEXT,
    priority       TEXT,
    route          TEXT,
    profile_version INTEGER NOT NULL DEFAULT 1,
    scored_at      TIMESTAMP,
    briefed_at     TIMESTAMP,
    seen_at        TIMESTAMP,
    feedback       TEXT,
    feedback_note  TEXT,
    feedback_at    TIMESTAMP,
    PRIMARY KEY (user_id, article_id),
    FOREIGN KEY (article_id) REFERENCES articles(id)
);

CREATE INDEX IF NOT EXISTS idx_user_articles_user_status ON user_articles(user_id, status);
CREATE INDEX IF NOT EXISTS idx_user_articles_display_score ON user_articles(user_id, display_score DESC);
```

### Design Decisions

- **Composite PK** `(user_id, article_id)` — one row per user-article pair
- **No FK to `users` table** — ASP.NET Identity creates that later. `user_id` is a UUID from `profiles.json` for now.
- **`status` as TEXT, not ENUM** — PostgreSQL enums require `ALTER TYPE` migrations to add values. Text with application-level validation is more flexible for a project still evolving.
- **All score columns nullable** — an article reaching only Tier 1 has `vector_score` but null `rerank_score` and `llm_score`
- **`route` column** — tracks which path the article took (clear_pass / borderline / safety_net) for cascade tuning and debugging

### Status Values

Per the parent design spec (Section 9):

| Status | Meaning |
|---|---|
| `ready` | Scored above threshold, waiting for briefing |
| `below_threshold` | Scored but not relevant enough |
| `briefed` | Included in a briefing (set by future briefing plan) |
| `seen` | User viewed in briefing (set by future briefing plan) |
| `dismissed` | User marked not relevant (set by future feedback) |

Plan 3 only sets `ready` and `below_threshold`. Other statuses are set by future plans.

---

## 8. API Endpoints

### `POST /api/scoring/trigger`

Triggers a scoring run for all configured profiles (or a specific user_id).

```json
// Request (optional body)
{ "user_id": "uuid" }

// Response
{
  "user_id": "...",
  "candidates_retrieved": 187,
  "reranked": 187,
  "llm_scored": 28,
  "summarized": 22,
  "stored": 22
}
```

### `GET /api/scoring/status`

Returns current scoring state.

```json
{
  "running": false,
  "last_result": { ... },
  "last_run_at": "2026-04-09T14:30:00Z"
}
```

Same pattern as the ingestion API endpoints from Plan 2.

---

## 9. Configuration

New settings added to `app/config.py`:

| Setting | Default | Description |
|---|---|---|
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama API endpoint |
| `OLLAMA_MODEL` | `gemma4` | Model name for LLM calls |
| `OLLAMA_TIMEOUT` | `120` | Request timeout in seconds |
| `RERANKER_MODEL` | `BAAI/bge-reranker-v2-m3` | Cross-encoder model name |
| `RETRIEVER_TOP_K` | `50` | Candidates per interest vector |
| `RETRIEVER_DATE_DAYS` | `7` | How far back to search |
| `SCORING_LLM_THRESHOLD` | `5` | Minimum LLM score to include |
| `SCORING_CLEAR_PASS_COUNT` | `5` | Top N from Tier 2 sent to Tier 3 |
| `SCORING_SAFETY_NET_COUNT` | `12` | Random rejected articles sampled |
| `PROFILES_PATH` | `profiles.json` | Path to user profiles config |

---

## 10. Testing Strategy

All tests mock external dependencies (no real Qdrant, PostgreSQL, Ollama, or model loading needed for unit tests).

| Test File | What It Tests |
|---|---|
| `test_profile_loader.py` | Loading profiles.json, embedding interest blocks |
| `test_retriever.py` | Qdrant query construction, result merging, dedup |
| `test_reranker.py` | Cross-encoder pair construction, score assignment |
| `test_cascade_router.py` | Routing logic: clear-pass/borderline/safety-net splits |
| `test_llm_scorer.py` | Prompt construction, JSON parsing, safety-net miss logging |
| `test_llm_summarizer.py` | Summary prompt construction, graceful failure |
| `test_normalizer.py` | Percentile calculation, confidence discounting, imputation |
| `test_repository.py` | user_articles CRUD, status filtering |
| `test_pipeline.py` | Full cascade orchestration with mocked components |

### Mocking Patterns

Consistent with Plan 2:
- Module-level mocking for models (`@patch("app.reasoning.reranker.CrossEncoder")`)
- Dependency injection via constructor params for pipeline components
- `TESTING=1` env var skips lifespan initialization

---

## 11. Dependencies

New packages to add to `requirements.txt`:

| Package | Version | Purpose |
|---|---|---|
| `httpx` | `0.27.0` | Already present — used for Ollama REST API |
| `sentence-transformers` | `3.4.1` | Already present — `CrossEncoder` class for reranking |

No new dependencies needed. The cross-encoder model (`bge-reranker-v2-m3`, ~1.1GB) downloads on first use via `sentence-transformers`. Ollama + Gemma 4 must be installed and running locally.

---

## 12. Data Flow Summary

```
profiles.json
    │
    ▼
ProfileLoader (embed interest blocks)
    │
    ▼
UserProfile { interest_blocks: [InterestBlock { text, embedding }] }
    │
    ▼
Retriever (Tier 1) ──── Qdrant multi-vector search ──── ~200 candidates
    │
    ▼
Reranker (Tier 2) ──── CrossEncoder bge-reranker-v2-m3 ──── all scored
    │
    ▼
CascadeRouter ──── split by rerank_score
    │         │           │
    │    clear-pass(5)  borderline(~20-45)  safety-net(12 random from rejected)
    │         │           │                    │
    ▼         ▼           ▼                    ▼
LlmScorer (Tier 3) ──── Ollama/Gemma 4 ──── score 1-10 + explanation + priority
    │
    │  (articles scoring ≥ threshold)
    ▼
LlmSummarizer (Tier 4) ──── Ollama/Gemma 4 ──── personalized 2-3 sentence summary
    │
    ▼
ScoreNormalizer ──── percentile normalization + confidence discounting
    │
    ▼
ScoringRepository ──── INSERT into user_articles (status: ready / below_threshold)
    │
    ▼
ScoringResult { candidates_retrieved, reranked, llm_scored, summarized, stored }
```

# Briefer

A personalized news intelligence platform that uses multi-stage AI reasoning to surface relevant articles for analysts -- including non-obvious connections that keyword-based tools would miss.

An analyst responsible for managing deer populations in northern Alberta needs to know about brain-eating parasites affecting deer in neighboring Saskatchewan. That connection exists, but no keyword search will find it. Briefer uses a four-tier scoring cascade that reasons about *why* an article matters to a specific user, not just whether it contains matching terms.

## Architecture

```
                                 +------------------+
                                 |   PostgreSQL 16  |
                                 +--------+---------+
                                          |
                    +---------------------+---------------------+
                    |                                           |
          +---------+---------+                     +-----------+-----------+
          |  ASP.NET Web API  |--- internal HTTP -->|  Python ML Service   |
          |  (.NET 10, C#)    |                     |  (FastAPI, Python)   |
          +---------+---------+                     +-----------+-----------+
                    |                                           |
                    |                                  +--------+---------+
                    |                                  |   Qdrant v1.13   |
                    |                                  |  (vector store)  |
               JWT auth                                +------------------+
              user profiles
            source preferences
           briefing retrieval
```

**Two services, split along a real domain boundary.** C# handles web concerns (auth, request routing, user management). Python handles ML concerns (embeddings, scoring, LLM orchestration). They share PostgreSQL for persistent state and communicate over internal HTTP with API key authentication and retry/circuit-breaker resilience.

This isn't a microservices-for-the-sake-of-microservices split. The languages genuinely play to different strengths here, and the ingestion module is designed with a clean interface so it can be extracted into a standalone service later if independent scaling is needed.

## Scoring Pipeline

The core intelligence. A four-tier cascade where each tier is dramatically cheaper than the next, filtering the candidate set so expensive LLM calls only run on articles that genuinely need them.

```
profiles.json / ASP.NET profile sync
    |
    v
ProfileLoader (embed interest blocks with sentence-transformers)
    |
    v
Tier 1: Vector Retrieval (Qdrant) ........... ~200 candidates, milliseconds, near-zero cost
    |
    v
Tier 2: Cross-Encoder Reranking ............. all scored, seconds, CPU only
    |       (BAAI/bge-reranker-v2-m3)
    v
CascadeRouter
    |--- clear-pass (top 5) ---------->|
    |--- borderline (~20-45) --------->|
    |--- safety-net (12 random) ------>|
                                       v
Tier 3: LLM Scoring ..................... ~35 calls, score 1-10 + explanation + priority
    |       (Ollama/Gemma 4 or OpenAI)
    v
Tier 4: LLM Summarization .............. ~15 calls, personalized 2-3 sentence summaries
    |
    v
Score Normalization (percentile + confidence discounting)
    |
    v
user_articles table (status: ready / below_threshold)
```

### Why a cascade instead of just sending everything to an LLM

Running 5,000 articles through an LLM costs ~$50/user and takes 30+ minutes. The cascade achieves roughly 95% of the quality at 5% of the cost by using cheap methods to eliminate obvious non-matches before the expensive reasoning kicks in.

### Why a cross-encoder tier exists at all

Skipping it means sending ~200 candidates to the LLM instead of ~35. That's a 6x cost increase per briefing cycle with marginal quality improvement, since most of those 200 articles are clearly irrelevant and the cross-encoder catches them.

### Safety net: measuring what the cascade misses

Each scoring cycle, 12 random articles that *failed* Tier 2 are still sent to the LLM. If the LLM scores them highly, they're logged as "cascade misses" -- evidence that the cross-encoder threshold is too aggressive. This is the feedback mechanism for tuning the cascade over time, and it's what prevents the system from silently dropping the non-obvious connections that justify its existence.

### Score normalization

Cosine similarity (0.3-0.8), cross-encoder logits (model-dependent), and LLM scores (1-10) are on completely different scales. Raw scores are converted to percentiles within each scoring cycle, then confidence-discounted based on which tier produced them:

```
display_score = normalized_llm_score ?? (normalized_rerank_score * 0.85) ?? (normalized_vector_score * 0.70)
```

Articles that only reached Tier 2 get a 15% discount. Vector-only scores get 30%. This prevents articles that happened to skip LLM scoring from outranking articles that were properly evaluated.

## Interest Profiles

Users describe their interests in narrative English, not keywords or tags. Each interest block captures a facet of what they care about and *why*.

```json
{
  "interests": [
    {
      "label": "Primary Role",
      "text": "I'm an environmental analyst for the Government of Alberta, working in the oil and gas branch..."
    },
    {
      "label": "Wildlife Mandate",
      "text": "My department is responsible for managing deer populations in the Peace River region..."
    }
  ]
}
```

Each block is embedded independently rather than as a single averaged vector. This prevents niche interests from being diluted when they share a profile with broader ones. Qdrant is queried with each interest vector separately, and results are merged.

Profile versioning tracks every edit. Each `user_articles` row records which profile version produced its scores, so re-scoring after profile changes only touches articles that need it.

## Ingestion Pipeline

RSS-first architecture. Most major outlets publish full-text RSS feeds with no API key, no rate limits, and no truncation. A shared full-text extraction layer (trafilatura) converts any article URL into clean text.

21 feeds configured out of the box covering Canadian national news, Alberta regional sources, environmental/wildlife outlets, and international wire services.

Three-layer deduplication at ingestion time:

| Layer | What it catches |
|---|---|
| Exact URL match | Same article, same source |
| Content hash (SHA-256) | Same article syndicated verbatim to a different URL |
| Fuzzy title+author match (90%+ via rapidfuzz) | Same article republished with minor headline edits |

Same title + different author = different article (different perspectives). Intentionally allowed through.

## Briefing Generation

Once articles are scored, users can generate executive briefings. The LLM reads the top-ranked articles alongside the user's profile and produces a summary focused on what matters to *this specific user*. Briefings are stored with article snapshots for 30-day history.

Graceful degradation: if the LLM is unavailable, the briefing still contains the scored article list. The executive summary is additive, not load-bearing.

## Design Decisions and Tradeoffs

### No Haystack / No LangChain

The original design spec suggested Haystack for the ML pipeline. After analysis, the cascade was built with direct library usage for three reasons:

1. **Conditional routing.** Tier 2 output fans into three buckets (clear-pass, borderline, rejected) with a safety-net sample from rejected. Haystack's DAG pipeline model doesn't naturally support this conditional fan-out.
2. **Cross-document aggregation.** Percentile-based score normalization requires seeing all articles' scores at once. Haystack processes documents individually.
3. **Debuggability.** When a scoring decision looks wrong, stepping through direct library calls is simpler than unwinding framework abstractions.

The underlying libraries are the same ones Haystack would wrap: `sentence-transformers`, `qdrant-client`, `httpx`.

### Qdrant over pgvector

pgvector would be simpler (one fewer service), but Qdrant's metadata filtering during search is important for scoping queries by date range, source, and region without post-filtering a larger result set. Qdrant is also self-hostable with a single Docker container, which matters for a project that might handle government-adjacent data.

Pinecone was ruled out for being proprietary and cloud-only.

### RSS over NewsAPI

NewsAPI's free tier returns 200-character truncated snippets with a 24-hour delay, 100 requests/day, and prohibits commercial use. The $449/month paid tier is prohibitive. RSS + trafilatura gives full article text at zero cost.

### TEXT over ENUM for status columns

PostgreSQL enums require `ALTER TYPE` migrations to add values. For a project still evolving, text columns with application-level validation are more flexible. The tradeoff is slightly less database-level safety, which is acceptable given the single-writer architecture.

### No abstract `ScoringTier` strategy pattern

The four tiers have fundamentally different inputs and outputs. Tier 1 takes embeddings, Tier 2 takes text pairs, Tier 3 takes articles + profile text. A common interface would hide these real differences behind a leaky abstraction. Each tier is its own class with dependency injection; a thin `ScoringPipeline` orchestrator wires them together.

### Profile sync: fire-and-forget with logging

When a user edits their interests in the ASP.NET API, the updated profile is pushed to the ML service for re-embedding. This call is fire-and-forget: if the ML service is down, the profile change still saves locally and the sync failure is logged. The ML service will pick up the profile from the database on its next restart. The tradeoff is eventual consistency over blocking the user's HTTP response on an internal service call.

### Model-agnostic LLM provider

All LLM calls go through an abstract `LlmProvider` interface with `generate()`, `generate_json()`, and `chat()` methods. Two implementations ship: Ollama (local, free, no API key) and OpenAI. Swapping models is a config change, not a code change.

The `chat()` method isn't used by the current pipeline. It exists for a planned guided profile builder that needs multi-turn conversation. Defined now so adding a provider later doesn't require retrofitting the interface.

## Tech Stack

| Component | Technology | Why |
|---|---|---|
| Web API | ASP.NET 10 (C#) | Strong auth story (Identity + JWT), EF Core, resilience patterns |
| ML Service | FastAPI (Python 3.12) | ML ecosystem, sentence-transformers, LLM libraries |
| Vector Store | Qdrant v1.13 | Metadata filtering, self-hostable, single container |
| Database | PostgreSQL 16 | Shared state between services, mature, reliable |
| Embeddings | sentence-transformers/all-MiniLM-L6-v2 | 384-dim, fast, good general-purpose quality |
| Reranker | BAAI/bge-reranker-v2-m3 | 8192 token context, cross-domain relevance |
| LLM (local) | Ollama + Gemma 4 | Zero cost, no API keys, works offline |
| LLM (cloud) | OpenAI GPT-4.1-nano | Low latency, good structured output |
| Deduplication | rapidfuzz | Fast fuzzy matching for title/author comparison |
| Extraction | trafilatura | Robust full-text extraction from article URLs |

## Project Structure

```
Briefer/
|-- docker-compose.yml              # 4 services: postgres, qdrant, web-api, ml-service
|-- docker-compose.dev.yml          # Dev overrides (exposed ports, hot reload)
|-- .env.example
|-- docs/
|   `-- superpowers/
|       |-- specs/                   # Design specifications
|       `-- plans/                   # Implementation plans (4 phases)
`-- src/
    |-- web-api/
    |   |-- NewsSearcher.Api/        # Controllers, Services, Models, Data
    |   |-- NewsSearcher.Api.Tests/  # 29 tests (xUnit)
    |   `-- Dockerfile
    `-- ml-service/
        |-- app/
        |   |-- ingestion/           # RSS plugins, extraction, dedup, embedding
        |   |-- reasoning/           # 4-tier cascade, LLM providers, scoring
        |   |-- briefing/            # Generation, repository, models
        |   `-- routers/             # FastAPI endpoints
        |-- tests/                   # 223 tests (pytest)
        |-- feeds.json               # 21 RSS feed sources
        |-- profiles.json            # Test user profile
        `-- Dockerfile
```

## Running Locally

```bash
# Clone and configure
git clone https://github.com/mbohaychuk/Briefer.git
cd Briefer
cp .env.example .env
# Edit .env with your values (the defaults work for local dev)

# Start infrastructure
docker compose up -d postgres qdrant

# Start the ML service
cd src/ml-service
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
TESTING=0 uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# Start the web API (separate terminal)
cd src/web-api/NewsSearcher.Api
dotnet run

# Or run everything via Docker Compose
docker compose up --build
```

For LLM scoring, install [Ollama](https://ollama.com/) and pull a model:

```bash
ollama pull gemma4
```

Or set `LLM_PROVIDER=openai` and `OPENAI_API_KEY=sk-...` to use OpenAI instead.

## Running Tests

```bash
# ASP.NET tests (29 tests)
cd src/web-api/NewsSearcher.Api.Tests
dotnet test

# Python tests (223 tests)
cd src/ml-service
TESTING=1 python -m pytest tests/ -v
```

## API Endpoints

### Web API (public, JWT auth required)

| Method | Path | Description |
|---|---|---|
| POST | `/api/auth/register` | Create account |
| POST | `/api/auth/login` | Get JWT token |
| GET | `/api/profile` | Current interest profile |
| POST | `/api/profile/interests` | Add interest block |
| PUT | `/api/profile/interests/{id}` | Update interest block |
| DELETE | `/api/profile/interests/{id}` | Remove interest block |
| GET | `/api/sourcepreferences` | Blocklist + priority sources |
| POST | `/api/sourcepreferences` | Add source preference |
| DELETE | `/api/sourcepreferences/{id}` | Remove source preference |
| POST | `/api/briefing/generate` | Generate briefing for current user |
| GET | `/api/briefing/latest` | Most recent briefing |
| GET | `/api/briefing/history` | Briefing metadata (30 days) |
| GET | `/api/briefing/{id}` | Specific briefing with articles |
| POST | `/api/ingestion/trigger` | Trigger article ingestion |
| GET | `/api/ingestion/status` | Ingestion pipeline status |
| POST | `/api/scoring/trigger` | Trigger scoring pipeline |
| GET | `/api/scoring/status` | Scoring pipeline status |

### ML Service (internal, API key auth)

| Method | Path | Description |
|---|---|---|
| GET | `/health` | Health check (no auth) |
| POST | `/api/ingestion/trigger` | Run ingestion pipeline |
| GET | `/api/ingestion/status` | Pipeline status |
| GET | `/api/ingestion/feeds` | Configured RSS feeds |
| POST | `/api/scoring/trigger` | Run scoring cascade |
| GET | `/api/scoring/status` | Scoring status |
| POST | `/api/briefing/generate` | Generate briefing |
| GET | `/api/briefing/latest/{user_id}` | Latest briefing |
| GET | `/api/briefing/history/{user_id}` | Briefing history |
| GET | `/api/briefing/{id}` | Briefing by ID |
| POST | `/api/profiles/sync` | Sync profiles from web API |

## What's Next

The backend is complete. Planned next steps, roughly in order:

- **Vue/Nuxt frontend** -- briefing dashboard, profile management, feedback controls
- **Guided profile builder** -- AI-assisted interest expansion through causal reasoning (seed, expand, confirm workflow)
- **HyDE embeddings** -- generate hypothetical ideal articles from user profiles for better retrieval
- **Feedback loop** -- relevant/not-relevant signals to tune cascade thresholds over time
- **Cross-encoder fine-tuning** -- train on accumulated feedback pairs
- **Continuous monitoring mode** -- move from scheduled runs to near-real-time ingestion

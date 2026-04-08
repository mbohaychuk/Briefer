# News Searcher — Design Specification

**Date:** 2026-04-07
**Status:** Approved
**Working Name:** Policy Lens (TBD)

---

## 1. Overview

An AI-powered news intelligence platform that helps analysts discover relevant articles — including non-obvious connections — across diverse sources. Users describe their interests in plain English, the system retrieves and scores articles using a multi-stage cascade pipeline, and delivers an executive briefing via a web app.

### Core Problem

Analysts (policy, research, intelligence, market) spend significant time manually scanning news sources for articles relevant to their work. Relevance is often non-obvious: a government environmental analyst responsible for deer populations in northern Alberta needs to know about brain-eating parasites affecting deer in neighboring Saskatchewan — a connection that keyword matching would never find.

### Core Value Proposition

The user describes what they care about in narrative form, including context about why and non-obvious responsibilities. The system uses AI to reason about relevance, catching connections that keyword-based tools miss.

---

## 2. Target Audience

Analysts of any domain who need to monitor news and published research relevant to their work. The initial use case is a Government of Alberta policy analyst, but the system is domain-agnostic — it works for anyone who can describe their interests in plain English.

---

## 3. Tech Stack

| Component | Technology | Role |
|---|---|---|
| Frontend | Vue / Nuxt | Briefing dashboard, profile management |
| Web API | ASP.NET (C#) | User-facing gateway, auth, serves frontend |
| ML Service | Python (Haystack) | Ingestion, scoring, summarization pipeline |
| Vector Store | Qdrant | Article embeddings, filtered vector search |
| Database | PostgreSQL | Users, articles, scores, briefings, feedback |
| Auth | ASP.NET Identity | Email/password, JWT tokens |

### Why This Stack

- **ASP.NET + Python split:** Each language plays to its strengths. C# handles web API concerns (auth, request/response, user management). Python handles ML concerns (embeddings, Haystack pipeline, LLM orchestration). The split falls along a real domain boundary.
- **Haystack:** Purpose-built for RAG pipelines. The two-stage retrieval-then-reasoning pattern is its core use case. Supports swappable document stores, embedders, and generators — aligns with our model-agnostic and modular source requirements.
- **Qdrant:** Strong metadata filtering during vector search (scoping by date, source, region). Fully open source, self-hostable, single Docker container. First-class Haystack integration.
- **Vue/Nuxt:** Modern reactive frontend. Nuxt provides SSR and file-based routing.

### Alternatives Considered

- **LangChain** (instead of Haystack): Too general-purpose, frequent API changes, debugging through abstraction layers is painful. Haystack is focused specifically on retrieval-augmented pipelines.
- **LlamaIndex** (instead of Haystack): Strong data ingestion but more opinionated about retrieval patterns. Haystack's composable pipeline model gives more control.
- **pgvector** (instead of Qdrant): Simpler (one fewer service) but lacks Qdrant's metadata filtering during search — important for scoping queries by date, region, and source.
- **Pinecone** (instead of Qdrant): Proprietary, cloud-only, no self-hosting. Not suitable for a portfolio piece or potentially government-adjacent data.

---

## 4. Architecture

### Service Layout

```
User <-> Nuxt Frontend <-> ASP.NET API <-> Python ML Service <-> Qdrant
                              |                    |
                              +--- PostgreSQL <-----+
```

### ASP.NET Web API

User-facing gateway handling:
- Authentication (ASP.NET Identity, JWT)
- User profile and interest description management
- Source preference management (blocklist / priority list)
- Briefing endpoints (triggers executive summary generation)
- Feedback collection
Communicates with the Python ML service via internal HTTP API. The Nuxt frontend is served independently (its own Node.js process / Docker container), not through ASP.NET. In production, a reverse proxy (nginx or Caddy) routes `/api/*` to ASP.NET and everything else to Nuxt.

### Python ML Service

Three distinct modules:

**Ingestion Module** (future microservice seam):
- Source plugins fetch articles via APIs, RSS, or scraping
- Normalize into standard document format
- Deduplicate (URL + content hash + title/author fuzzy match)
- Blocklist filter (system defaults + user-configured)
- Chunk and embed articles
- Store in Qdrant + PostgreSQL

**Reasoning Module:**
- Cascade scoring pipeline (see Section 7)
- Per-article summarization
- Executive summary generation (on-demand)

**Scheduler Module:**
- Orchestrates ingestion and scoring jobs on configurable schedules
- Thin wrapper — triggers ingestion and reasoning, doesn't contain business logic
- Designed so swapping to more frequent monitoring is a config change

### Communication Flow

1. User manages interest profile and views briefings through Nuxt → ASP.NET
2. ASP.NET handles all user-facing concerns, calls Python ML service for intelligence operations
3. Python ingestion module runs on schedule — fetches, embeds, stores articles
4. Python reasoning module runs on schedule — scores articles for each user
5. When user opens the briefing page, ASP.NET calls reasoning module to generate the executive summary on-demand from already-scored articles

### Project Structure

```
news-searcher/
├── src/
│   ├── web-api/                  # ASP.NET Web API (C#)
│   │   ├── Controllers/
│   │   ├── Models/
│   │   ├── Services/
│   │   └── Data/
│   │
│   ├── ml-service/               # Python ML Service
│   │   ├── ingestion/            # Distinct module (future microservice seam)
│   │   │   ├── plugins/          # Source plugins
│   │   │   └── pipeline.py
│   │   ├── reasoning/            # Retrieval + scoring + summarization
│   │   │   ├── retrieval.py
│   │   │   ├── scoring.py
│   │   │   └── briefing.py
│   │   ├── scheduler/            # Orchestrates ingestion + reasoning jobs
│   │   │   └── scheduler.py
│   │   ├── providers/            # LLM provider adapters (model-agnostic)
│   │   └── api.py
│   │
│   └── frontend/                 # Vue / Nuxt
│       ├── pages/
│       ├── components/
│       └── composables/
│
├── docker-compose.yml
└── docs/
```

### Future Extensibility

The ingestion module is designed with a clean interface so it can be extracted into a standalone microservice later. This would enable independent scaling and potentially connecting internal government report sources without modifying the core ML service. This is a documented architectural decision for portfolio purposes — we implement as a module now, but the seam is deliberate.

---

## 5. User Interest Profile System

### Narrative Descriptions

Users describe their interests in plain English blocks — not keywords, not tags. Each block captures a facet of what they care about and why.

Example profile:

> **Primary Role:** "I'm an environmental analyst for the Government of Alberta, working in the oil and gas branch. I need to stay informed about environmental policy, regulations, and incidents that could affect Alberta's energy sector."
>
> **Wildlife Mandate:** "My department is responsible for managing deer populations in the Peace River region of northern Alberta. This is due to a historical mandate. I need to know about anything affecting deer in this region: disease, habitat disruption, predator changes, climate impact, and similar issues in neighboring provinces that could spread."
>
> **Regional Scope:** "I primarily focus on Alberta but need awareness of British Columbia, Saskatchewan, and federal Canadian developments that could have cross-border policy implications."

### Why Narrative Over Structured Fields

Structured fields (dropdowns for region, topic, industry) force the user to anticipate every possible connection upfront. The deer parasite article wouldn't match any predefined category. Free-text narrative lets the LLM reason about *why* something matters, not just *what* keywords match.

### Multi-Vector Embedding

Each interest description block is embedded separately rather than as a single averaged embedding. This prevents niche interests from being diluted. When searching for relevant articles, Qdrant is queried with each interest vector independently and results are merged.

### HyDE (Hypothetical Document Embeddings)

When a user creates or updates their profile, the LLM generates 2-3 "hypothetical ideal articles" matching their interests (1 LLM call). These hypothetical articles are embedded and used as additional search vectors. This often retrieves better results than embedding the raw profile text, because the embedding model was trained on articles, not profile descriptions.

### LLM-Generated Search Terms

The user's narrative profile is translated into concrete search queries for each source plugin. An LLM reads the interest descriptions and generates search terms optimized for each source type. "Manages deer populations in Peace River region" becomes queries like "deer population Alberta", "wildlife disease western Canada", "chronic wasting disease", etc. Search terms are regenerated when the profile changes significantly.

### Feedback Loop

- **Relevant** — confirms the system's judgment. Article moves to briefing history. Reinforces connection patterns for future scoring.
- **Not relevant** — tells the system it overreached. Article disappears. Negative signal for future scoring.
- **Relevant but missed** — the most valuable signal. User found an article the system should have caught. They can annotate *why* it's relevant, and that reasoning enriches the profile context over time.

### Guided Conversation Profile Builder (Future Enhancement)

**Status: Planned for after the core scoring pipeline is working.**

When creating or editing an interest block, the user enters a guided AI conversation (3-5 turns) that expands their stated interest through causal reasoning:

1. **Seed:** User describes their interest in plain English.
2. **Expand:** AI analyzes the description and generates expansion contexts organized by causal distance:
   - **Direct** — topics that obviously relate to the stated interest
   - **One-hop** — events one causal step removed (adjacent domains, neighboring regions) with explicit causal links
   - **Two-hop** — broader systemic forces two causal steps removed with explicit causal chains
3. **Refine:** AI presents expansions as structured cards. User accepts/rejects/edits via toggles and targeted feedback. AI asks focused questions about blind spots. Max 3 expansion turns.
4. **Confirm:** User reviews the full expansion map and activates their profile.

Each accepted expansion context generates additional search terms and HyDE embedding vectors, widening the retrieval net to catch non-obvious connections. The expansion map is the persistent artifact — re-editing happens on the map directly, not by replaying the conversation.

**Why this matters:** The scoring pipeline can only score articles that were retrieved. If search terms are too narrow, non-obvious articles never enter the pipeline. Causal expansion widens retrieval proactively rather than hoping the LLM catches misses reactively.

**Why deferred:** The core pipeline must work end-to-end first. Measuring what the basic pipeline misses (via the Tier 3 safety net) provides concrete evidence for whether and how much expansion helps.

### Profile Versioning

Every profile edit increments a `profile_version` integer. Each scored `user_articles` row records which profile version produced its scores. This drives the re-scoring logic (see Section 9).

---

## 6. Source Plugin System

### Plugin Interface

Every source implements the same interface:
- **Fetch** — retrieve new/updated content since last run
- **Normalize** — convert to standard article document (title, content, author, source, date, URL, metadata)
- **Rate limiting / backoff** — each plugin manages its own source's constraints

### RSS-First Architecture

RSS is the primary article source, not a supplement. Most major outlets (CBC, BBC, Reuters, AP, Government of Canada) publish full-text RSS feeds with no API key, no rate limits, and no truncation. A shared **full-text extraction layer** (using `trafilatura`) converts any article URL into clean text, decoupling content acquisition from source APIs.

**Why RSS-first:** NewsAPI's free tier is unusable for this project — it returns 200-character truncated snippets, has a 24-hour delay, limits to 100 requests/day, and prohibits commercial use. The $449/month paid tier is prohibitive. RSS + trafilatura gives us full article text at zero cost.

### Initial Plugins

| Plugin | Type | Coverage | Notes |
|---|---|---|---|
| RSS Feed Reader | RSS | Government publications, regional papers, industry outlets, major wire services | **Primary source.** Curated list of 30-50 feeds. |
| The Guardian API | API | UK/international news, full article text | Free, 5,000 req/day, full body text included. |
| Semantic Scholar | API | Academic papers, research | Free API key, abstracts + OA PDF links. |
| PubMed | API | Biomedical and environmental science research | Free API key, abstracts + PMC full text for OA. |
| NewsAPI | API | Broad news URL discovery | **Demoted to URL discovery only.** Free tier finds URLs; trafilatura extracts full text. |
| Web Scraper | Scraping | Targeted scraping for specific high-value sites | Fallback for sites without RSS/API. |

### Full-Text Extraction Layer

Every source plugin produces URLs + metadata. A shared extraction step uses `trafilatura` (Python) to pull actual article content from the URL. This means:
- Source plugins don't need to provide full text — just URLs
- If any source API changes, only URL-fetching breaks, not the content pipeline
- Articles where extraction fails are flagged; the user can click through to the source

### Adding a New Source

Write a new plugin class implementing the interface. No changes to the pipeline, storage, or reasoning layer. This is the extensibility point for future internal report sources.

### Source Preferences

**Blocklist:**
- System defaults — satirical sources (The Onion, Babylon Bee, etc.), known low-quality content farms. Applied to all users unless explicitly overridden.
- User blocklist — sources or authors the user adds. Blocked content is dropped before embedding, never enters Qdrant, never costs compute.

**Priority list:**
- Sources the user considers authoritative or high-value.
- Articles from priority sources get a relevance boost during scoring.
- Doesn't guarantee inclusion — the article still needs to be relevant.

Users manage both lists through the UI. System defaults are visible so users know what's being filtered and can override if needed.

### Search Term Filtering

Source plugins don't fetch blindly. They query their APIs using search terms derived from all users' interest profiles. This is the primary volume control — we fetch hundreds of articles, not millions.

Search terms across all users are aggregated so plugins make efficient batched queries. An article fetched because of User A's search terms might also score highly for User B.

---

## 7. Scoring Pipeline (Four-Tier Cascade)

The core intelligence of the app. Each tier is dramatically cheaper than the next, and each filters down the candidate set.

### Tier 1: Vector Similarity (Qdrant)

- Query Qdrant with each of the user's interest embeddings (multi-vector search)
- Scope by metadata filters (date range, source, blocklist)
- Retrieve top-N candidates per interest vector, merge and deduplicate
- Cast a wide net — threshold is intentionally generous
- **Cost:** Near-zero. Milliseconds.

### Tier 2: Cross-Encoder Reranking

- A small ML model (not a generative LLM) that takes a (query, document) pair and outputs a relevance score
- 100-1000x cheaper than an LLM call, runs on CPU
- **Model: `BAAI/bge-reranker-v2-m3`** (recommended over `ms-marco-MiniLM-L-6-v2` — supports longer inputs up to 8192 tokens and handles cross-domain relevance better, which matters for our narrative interest descriptions)
- Narrows ~200 candidates to ~30-50
- **Cost:** Seconds of compute, near-zero monetary cost if self-hosted.

### Tier 3: LLM Scoring (Borderline + Safety Net)

- **Borderline articles:** Articles where the cross-encoder score is ambiguous (near the inclusion/exclusion threshold). LLM receives the article alongside the user's full interest profile, reasons about relevance.
- **Clear-pass articles:** The top 5 articles that clearly passed Tier 2 also go through Tier 3. This prevents them from being systematically disadvantaged in ranking (they'd otherwise only have a discounted rerank_score).
- **Safety net sample:** Each cycle, 10-15 random articles that *failed* Tier 2 are sent to the LLM. This measures the false negative rate — articles the cascade missed that the LLM catches. Results are logged as "cascade misses" and used to tune Tier 1/2 thresholds and generate better HyDE vectors.
- Assigns a relevance score with explanation
- Assigns topic categories
- Flags priority level (routine / important / critical)
- **Cost:** ~20-35 LLM calls per user per briefing cycle (slightly more than borderline-only, but catches the non-obvious connections that justify the system's existence).

### Tier 4: LLM Summarization (Top Articles Only)

- Generates a concise summary focused on why this article matters to *this specific user*
- Runs on all articles that will be included in the briefing — both those that clearly passed Tier 2 and those confirmed by Tier 3
- **Cost:** ~10-15 LLM calls per user per briefing cycle.

### Score Normalization & Ranking

Scores from different tiers aren't directly comparable — cosine similarity (0.3–0.8), cross-encoder logits (model-dependent), and LLM scores (prompted 1–10) are on different scales. Raw scores must be normalized before combining:

1. **Per-tier normalization:** Convert each tier's raw scores to percentiles within that scoring cycle. A vector score at the 80th percentile and an LLM score at the 80th percentile mean the same thing: "better than 80% of articles scored by this method."
2. **Confidence discounting:** Apply tier-specific discount factors to normalized scores:
   ```
   display_score = normalized_llm_score ?? (normalized_rerank_score * 0.85) ?? (normalized_vector_score * 0.70)
   ```
3. **Imputed scores for clear-pass articles:** Articles that clearly pass Tier 2 and go through Tier 3 get their actual LLM score. If for any reason they skip Tier 3, they receive an imputed score at the 75th percentile of actual LLM scores, preventing them from being ranked below borderline articles.

The discount factors (0.85, 0.70) are starting values — calibrate with accumulated user feedback data over time.

### Model-Agnostic Design

The LLM is behind a provider adapter interface. Swapping models (Claude, OpenAI, local models) means writing a new adapter, not touching pipeline logic. Haystack's generator component abstraction handles most of this naturally.

### Why a Cascade (Not Just LLM Everything)

Running every article through an LLM would cost ~$50 per user for 5,000 articles and take 30+ minutes. The cascade reduces this to ~$2-3 and under a minute by using cheap methods to filter out obvious non-matches before the expensive reasoning kicks in.

### Alternatives Considered

- **Two-stage pipeline (vector + LLM only):** Skipping the cross-encoder means sending ~200 candidates to the LLM instead of ~20. 10x more expensive per briefing cycle.
- **Embedding-only (no LLM scoring):** Much cheaper but misses the non-obvious connections that are the core value proposition. Vector similarity alone wouldn't connect "brain-eating parasites in Saskatchewan deer" to "Alberta deer population management."
- **Full LLM on everything:** Accurate but cost-prohibitive and slow. The cascade achieves 90-95% of the quality at 5% of the cost.

---

## 8. Briefing Experience

### Daily Briefing (Main View)

**Two-Phase Page Load:**
The briefing page loads in two phases for responsive UX:
1. **Phase 1 (immediate):** Article list loads from already-scored data in PostgreSQL. Sub-second response. The page is immediately useful.
2. **Phase 2 (async):** Executive summary is generated on-demand via a separate API call. Frontend shows "Generating executive summary..." indicator, fills it in when ready (5-15 seconds). If the LLM fails, the page still works — articles are the primary value.

**Executive Summary (top of page):**
- AI-generated "here's what you need to know today" paragraph
- Inline references to the 1-2 most critical articles only if something rises to that level
- Date and time of last pipeline run visible
- Graceful degradation: if LLM is unavailable, shows "Executive summary temporarily unavailable" — articles remain fully functional

**Article Feed (below):**
- Prioritized list of articles the user hasn't been briefed on yet
- Each article shows: headline, source, personalized AI summary, relevance indicator, category tags, link to original
- Category filter — toggle categories on/off
- Search — full-text search across headlines and summaries
- Feedback controls on each article — relevant / not relevant / relevant but missed (with annotation field)

### Briefing Lifecycle

1. User opens the page → frontend calls `GET /api/briefing` → ASP.NET returns scored articles from PostgreSQL (fast, no LLM call)
2. Frontend displays article list immediately, starts async call to `POST /api/briefing/summary` for executive summary generation
3. ASP.NET calls Python reasoning module for executive summary (1 LLM call, 5-15 seconds)
4. Frontend fills in executive summary when it arrives
5. Articles included in the briefing are marked as `briefed` — they leave the feed permanently
6. The assembled briefing (executive summary + article list with summaries) is stored for history

### Briefing History

- Access past briefings for up to 30 days
- Read-only view — browse what was flagged on any given day
- After 30 days, briefing display data is cleaned up

### Interest Profile Management

- View and edit interest description blocks
- Add/remove/reorder blocks
- Manage source blocklist and priority list
- View feedback history

---

## 9. Article Lifecycle & State Management

### Design Philosophy

The app is a **discovery and alerting tool**, not an article archive. Its job is to surface relevant articles the user hasn't seen. Once briefed, an article is done — it exists in history for reference but is never re-scored, re-ranked, or re-surfaced.

### User-Article State

Single `user_articles` table with a `status` enum and supporting timestamps:

| Status | Meaning | What happens next |
|---|---|---|
| `ready` | Scored above briefing threshold, waiting for next briefing | Will appear in next briefing |
| `below_threshold` | Scored but not relevant enough to brief | Ages out, or re-scored if profile changes |
| `briefed` | Included in a briefing | Moves to history. Never re-scored. |
| `seen` | User viewed/interacted in the briefing | Terminal for compute purposes. |
| `dismissed` | User marked as not relevant | Feedback recorded. Disappears. |

Timestamps (`scored_at`, `briefed_at`, `seen_at`, `feedback_at`) are kept alongside the status for debugging and audit, but queries filter on `status` for simplicity.

### Profile Change Handling

When a user updates their interest profile:

1. **Embedding delta check:** Compare old and new profile embeddings. If cosine similarity change < 0.05, it's a trivial edit (typo fix). Skip re-scoring, just bump version.
2. **Background re-scoring job:** For non-trivial changes, kick off a background job that re-runs vector similarity on unbriefed active articles (cheap, seconds). Only escalate to cross-encoder/LLM where vector scores changed significantly.
3. **Already-briefed articles are never re-scored.** They are historical facts.
4. **Debounce rapid edits.** Multiple profile changes within 15 minutes are coalesced. Only the final version triggers re-scoring.
5. **If user requests a briefing before re-scoring finishes,** generate with best available scores and indicate "scores updating."

### Deduplication

Layered dedup at ingestion time:

| Check | What it catches |
|---|---|
| Exact URL match | Same article, same source |
| Content hash | Same article syndicated verbatim to different URL |
| Normalized title + author fuzzy match (90%+) | Same article republished with minor headline edits |

Same title + different author = different article (different perspectives), let it through.

### Retention & Cleanup

| Data | Kept forever | Cleaned at 14 days | Cleaned at 30 days |
|---|---|---|---|
| Article dedup shell (URL, content hash, title, author) | Yes | | |
| User-article slim row (user_id, article_id, status, feedback) | Yes | | |
| Qdrant vectors | | Deleted | |
| Article body content | | | Stripped |
| Briefing display data (summaries, executive briefing, scores) | | | Deleted |

**Clarification on "kept forever":**
- The **article dedup shell** (URL, content hash, title, author) is kept forever to prevent re-ingesting duplicates. This is a few bytes per article.
- The **user-article slim row** (user_id, article_id, status) is kept forever to prevent re-showing articles to a user. Also a few bytes per row.
- **Feedback data** (feedback type + annotation) on those slim rows is retained for up to 365 days for AI training value, then stripped. The slim row itself remains.

### Alternatives Considered

**Event-sourced state machine (8 states + event log):** Rejected. The append-only event log adds a second table that must stay in sync with the state table, creating a consistency problem. The 8 states conflate pipeline processing stages with user-facing states. Adding new states requires migration + updating transition rules + updating event schemas + updating every query. Over-engineered for a 1-2 person team.

**Timestamps-only (no status column):** Partially adopted. Timestamps are valuable for audit/debugging, but compound WHERE clauses on nullable timestamps get fragile fast with 5+ logical states. A status enum gives simple query filters (`WHERE status = 'pending'`) while timestamps provide the detail.

**Five-tier storage (HOT/WARM/COLD/ARCHIVED/PURGED):** Rejected. 5 tiers x 6 states = 30 combinations, half of which are undefined edge cases. Two independent state systems (article tier + user-article state) updated by different code paths at different times creates hard-to-debug consistency issues. Fixed time windows (48h HOT) don't match reality — a policy change might be relevant for weeks. Collapsed to a simpler model where the user-article status drives behavior and time-based cleanup is straightforward.

---

## 10. Data Model

### Core Entities

**users**
- Auth credentials (ASP.NET Identity)
- `current_profile_version` integer

**user_profiles**
- `user_id`, `version`, `interests_text`, `interests_embedding`, `is_current`
- Versioned — old versions retained for reference

**articles**
- `url`, `content_hash`, `title_normalized`, `author_normalized` (dedup fields, kept forever)
- `title`, `raw_content`, `source_name`, `published_at`, `fetched_at`
- `qdrant_point_id` (null after Qdrant eviction)
- `raw_content` stripped at 30 days; dedup shell persists

**user_articles**
- `user_id`, `article_id` (composite PK)
- `status` enum: ready / below_threshold / briefed / seen / dismissed
- `vector_score`, `rerank_score`, `llm_score`, `summary`
- `profile_version`
- `scored_at`, `briefed_at`, `seen_at`
- `feedback`, `feedback_note`, `feedback_at`
- Scores and summary stripped at 30 days; slim row persists

**interest_conversations** (future — added with guided conversation feature)
- `id`, `interest_description_id` (nullable), `user_id`, `status` (active/completed/abandoned)
- `initial_description`, `turns` (JSONB array of conversation turns)
- `created_at`, `expires_at`, `completed_at`

**expansion_contexts** (future — added with guided conversation feature)
- `id`, `interest_description_id`
- `label`, `description`, `hop_level` (0=direct, 1=one-hop, 2=two-hop)
- `reasoning` (why this expansion is relevant)
- `search_terms` (JSONB), `qdrant_point_ids` (JSONB)
- `conversation_id`, `created_at`

**source_preferences**
- `user_id` (or system-level)
- `type`: blocklist / priority
- `target`: source name, domain, or author

**briefings**
- `user_id`, `generated_at`, `executive_summary`, `profile_version`

**briefing_articles**
- `briefing_id`, `article_id`, `rank`, `score_snapshot`, `summary_snapshot`
- Deleted at 30 days along with parent briefing

### Relationships

```
User ──1:many──> User Profiles (versioned)
User ──1:many──> User Articles
User ──1:many──> Source Preferences
User ──1:many──> Briefings
Article ──1:many──> User Articles
Briefing ──many:many──> Articles (via briefing_articles)
```

---

## 11. Authentication

### Initial Implementation

- ASP.NET Identity with email/password
- JWT token-based auth for the Nuxt frontend
- Each authenticated user gets independent: interest profile, source preferences, feedback history, briefing history

### What We're NOT Building

- No team/organization features
- No shared briefings or collaborative profiles
- No admin panel
- No SSO/OAuth

These can come later if demand warrants. Each user is fully independent.

---

## 12. Future Roadmap (Not In Scope)

Documented here as deliberate architectural decisions for portfolio purposes:

- **Ingestion microservice extraction:** The ingestion module has a clean interface for extraction into a standalone service. Enables independent scaling and connecting proprietary data sources.
- **Continuous monitoring / breaking news:** The scheduler is a thin wrapper. Swapping "run once at 5 AM" for "run every 30 minutes" is a config change. The harder UX questions (incremental summaries, notification states) are deferred.
- **Push notifications / email digests:** Delivery channel beyond the web app.
- **Internal report integration:** The source plugin system supports this — write a new plugin that reads from an internal document store.
- **Cross-encoder fine-tuning:** Train the cross-encoder on accumulated feedback data (relevant/not relevant pairs) to improve scoring quality over time.
- **Guided conversation profile builder:** AI-assisted profile creation with causal expansion reasoning. Wizard-style UI (Seed → Expand → Confirm) that helps users discover non-obvious information needs. Produces expansion contexts that widen retrieval scope. See Section 5 for full design.
- **Retrieval path tagging:** Track which search terms and embedding vectors led to each article's retrieval. Enables per-expansion noise rate monitoring and data-driven threshold tuning.

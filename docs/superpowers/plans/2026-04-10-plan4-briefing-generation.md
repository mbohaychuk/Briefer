# Plan 4: Briefing Generation & Delivery — Implementation Plan

**Goal:** Build the briefing generation module in the Python ML service. This takes already-scored articles (status `ready` in `user_articles`) and produces an executive summary briefing — a personalized "here's what you need to know" for each user profile. Briefings are stored in PostgreSQL and served via API endpoints.

**Depends on:** Plan 2 (ingestion) and Plan 3 (scoring pipeline) — both implemented.

**Architecture:** The briefing module sits on top of the scoring pipeline. It reads scored articles, generates an executive summary via LLM, bundles everything into a briefing record, and marks source articles as `briefed`. The ASP.NET API (Plan 1) will later call these endpoints; for now they're directly accessible.

**Key Design Decisions (from design spec Section 8):**
- Two-phase page load: article list is instant (already in DB), executive summary is generated on-demand (5-15s LLM call)
- Executive summary is 1 LLM call summarizing the top articles as a cohesive narrative
- If LLM fails, articles are still returned — graceful degradation
- Briefings are stored for 30-day history
- Articles included in a briefing are marked `briefed` and leave the active feed permanently

---

## File Structure

```
src/ml-service/
├── app/
│   ├── briefing/
│   │   ├── __init__.py
│   │   ├── generator.py          # Executive summary LLM generation
│   │   ├── models.py             # Briefing, BriefingArticle dataclasses
│   │   └── repository.py         # PostgreSQL CRUD for briefings
│   └── routers/
│       └── briefing.py           # API endpoints
├── tests/
│   └── briefing/
│       ├── __init__.py
│       ├── conftest.py           # Shared test helpers
│       ├── test_generator.py     # Executive summary generation tests
│       ├── test_repository.py    # Repository CRUD tests
│       └── test_briefing_api.py  # Router endpoint tests
```

---

## Task 1: Database Tables

**Files:**
- Modify: `app/database.py`

- [ ] **Step 1: Add `briefings` table**

```sql
CREATE TABLE IF NOT EXISTS briefings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    executive_summary TEXT,
    article_count INTEGER NOT NULL DEFAULT 0,
    profile_version INTEGER NOT NULL DEFAULT 1,
    status TEXT NOT NULL DEFAULT 'pending',
    generated_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_briefings_user_created
    ON briefings(user_id, created_at DESC);
```

Status values: `pending` (created, no summary yet), `complete` (summary generated), `failed` (LLM failed, articles still valid).

- [ ] **Step 2: Add `briefing_articles` table**

```sql
CREATE TABLE IF NOT EXISTS briefing_articles (
    briefing_id UUID NOT NULL,
    article_id UUID NOT NULL,
    rank INTEGER NOT NULL,
    display_score REAL,
    summary TEXT,
    priority TEXT,
    explanation TEXT,
    PRIMARY KEY (briefing_id, article_id),
    FOREIGN KEY (briefing_id) REFERENCES briefings(id),
    FOREIGN KEY (article_id) REFERENCES articles(id)
);
```

Snapshots the article's score/summary at briefing time so history is self-contained even after score cleanup.

---

## Task 2: Briefing Models

**Files:**
- Create: `app/briefing/__init__.py`
- Create: `app/briefing/models.py`

- [ ] **Step 1: Define dataclasses**

```python
@dataclass
class BriefingArticle:
    article_id: UUID
    title: str
    source_name: str
    rank: int
    display_score: float
    summary: str | None
    priority: str | None
    explanation: str | None
    url: str | None = None

@dataclass
class Briefing:
    id: UUID
    user_id: UUID
    status: str  # pending, complete, failed
    article_count: int
    articles: list[BriefingArticle]
    executive_summary: str | None = None
    generated_at: datetime | None = None
    created_at: datetime | None = None
```

---

## Task 3: BriefingRepository

**Files:**
- Create: `app/briefing/repository.py`

- [ ] **Step 1: Create briefing record**

Insert a new `briefings` row with status `pending`. Returns the briefing UUID.

- [ ] **Step 2: Add articles to briefing**

Insert `briefing_articles` rows with snapshot data from `user_articles` joined with `articles` (for title, source, url). Update `user_articles.status` to `briefed` and set `briefed_at`.

- [ ] **Step 3: Complete briefing**

Update briefing status to `complete`, set `executive_summary` and `generated_at`.

- [ ] **Step 4: Mark briefing failed**

Update briefing status to `failed`, set `generated_at` (so we know it was attempted).

- [ ] **Step 5: Retrieve briefings**

- `get_briefing(briefing_id)` — full briefing with articles
- `get_latest(user_id)` — most recent briefing for a user
- `get_history(user_id, limit)` — list of recent briefings (metadata only, no articles)

---

## Task 4: BriefingGenerator

**Files:**
- Create: `app/briefing/generator.py`

- [ ] **Step 1: Executive summary generation**

Takes a list of BriefingArticles and a UserProfile. Constructs a prompt with the user's interests and the top articles (title + summary + priority). Calls `provider.generate()` with a system prompt instructing it to write a concise executive briefing paragraph.

```python
class BriefingGenerator:
    def __init__(self, provider: LlmProvider):
        self.provider = provider

    def generate_summary(
        self, articles: list[BriefingArticle], profile: UserProfile
    ) -> str | None:
        # Build prompt from top articles and profile
        # Call LLM, return summary text
        # Return None on failure (graceful degradation)
```

The prompt should:
- Reference the user's role/interests
- Highlight the most critical items first
- Note how many articles are in the briefing
- Be 3-5 sentences, executive style

---

## Task 5: Briefing Router

**Files:**
- Create: `app/routers/briefing.py`

- [ ] **Step 1: POST /api/briefing/generate**

Accepts `user_id` (from profile). Collects `ready` articles for that user, creates a briefing record, snapshots articles, generates executive summary, returns the complete briefing.

Response: `{ briefing_id, status, executive_summary, article_count, articles: [...] }`

- [ ] **Step 2: GET /api/briefing/latest/{user_id}**

Returns the most recent briefing for a user. Used for the main briefing page load.

- [ ] **Step 3: GET /api/briefing/{briefing_id}**

Returns a specific briefing by ID with full article list.

- [ ] **Step 4: GET /api/briefing/history/{user_id}**

Returns list of recent briefings (metadata only) for the history view.

---

## Task 6: Wire Into Main App

**Files:**
- Modify: `app/main.py`

- [ ] **Step 1: Initialize BriefingGenerator in lifespan**

Create `BriefingGenerator(llm_provider)` and store as module-level instance.

- [ ] **Step 2: Register briefing router**

Add `app.include_router(briefing.router)`.

---

## Task 7: Tests

**Files:**
- Create: `tests/briefing/__init__.py`
- Create: `tests/briefing/conftest.py`
- Create: `tests/briefing/test_generator.py`
- Create: `tests/briefing/test_repository.py`
- Create: `tests/briefing/test_briefing_api.py`

- [ ] **Step 1: Generator tests**
- Test prompt construction includes profile and articles
- Test graceful failure returns None
- Test empty article list handling

- [ ] **Step 2: Repository tests (mocked DB)**
- Test create_briefing returns UUID
- Test add_articles_to_briefing executes correct SQL
- Test complete_briefing updates status
- Test mark_failed updates status
- Test get_latest returns most recent

- [ ] **Step 3: API endpoint tests**
- Test generate endpoint returns briefing
- Test generate with no ready articles returns empty briefing
- Test latest endpoint
- Test history endpoint
- Test specific briefing endpoint

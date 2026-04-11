# Briefer Frontend — Design Specification

**Date:** 2026-04-11
**Status:** Approved

---

## 1. Overview

A Vue/Nuxt frontend for the Briefer news intelligence platform. The backend is complete: ASP.NET Web API (JWT auth, user profiles, source preferences, briefing proxy endpoints) and Python ML service (ingestion, scoring, briefing generation). The frontend provides a dashboard for viewing AI-generated briefings, managing interest profiles, browsing briefing history, and triggering the ingestion/scoring pipeline for live demos.

### Scope

Demo-optimized first version:

- Login / register
- Briefing dashboard (executive summary + scored article feed)
- Interest profile management
- Briefing history (30 days)
- Pipeline trigger controls (ingestion, scoring, briefing generation)

Deferred to a later iteration: source preferences management, feedback controls (relevant/not relevant), search, guided profile builder.

---

## 2. Tech Stack & Architecture

| Component | Choice | Why |
|---|---|---|
| Framework | Nuxt 3 | File-based routing, SSR-capable, Vue 3 composition API |
| CSS | Tailwind CSS with custom theme | Utility-first, single source of truth for design tokens |
| Component library | None (hand-rolled) | Maximum design control, minimal dependencies, portfolio-appropriate |
| State management | Pinia | Vue's official store, reactive, integrates with Nuxt |
| Auth persistence | localStorage | JWT stored client-side, hydrated on app start |
| HTTP client | Nuxt `$fetch` | Built-in, supports interceptors via composable wrapper |

### Architecture: Pages + Composables

Flat structure. Nuxt file-based routing handles pages, composables handle API calls and shared state. No abstraction layers beyond what Nuxt provides.

```
src/frontend/
├── nuxt.config.ts
├── tailwind.config.ts
├── app.vue
├── pages/
│   ├── login.vue
│   ├── index.vue
│   ├── history.vue
│   └── profile.vue
├── composables/
│   ├── useAuth.ts
│   ├── useApi.ts
│   ├── useBriefing.ts
│   ├── useProfile.ts
│   ├── usePipeline.ts
│   └── useToast.ts
├── components/
│   ├── AppNav.vue
│   ├── ArticleCard.vue
│   ├── ExecutiveSummary.vue
│   ├── StatsBar.vue
│   ├── InterestBlock.vue
│   ├── PipelineStatus.vue
│   └── ToastContainer.vue
├── layouts/
│   └── default.vue
├── middleware/
│   └── auth.global.ts
├── stores/
│   └── auth.ts
└── types/
    └── index.ts
```

---

## 3. Design Tokens (Tailwind Config)

All colors defined in `tailwind.config.ts` as the single source of truth. Changing a color here updates every component that references it.

```ts
// tailwind.config.ts
export default {
  theme: {
    extend: {
      colors: {
        primary: '#2563eb',
        'primary-light': '#eff6ff',
        danger: '#dc2626',
        'danger-light': '#fef2f2',
        surface: '#fafbfc',
        'surface-card': '#ffffff',
        border: '#e5e7eb',
        'text-primary': '#111827',
        'text-secondary': '#6b7280',
        'text-muted': '#9ca3af',
      }
    }
  }
}
```

### Visual Style

Clean/minimal with strategic data density. Light theme, modern sans-serif typography, whitespace-forward layout. Relevance scores and article counts are surfaced prominently where useful, but the overall feel is restrained and professional.

---

## 4. Authentication

### Login Page (`pages/login.vue`)

Centered card with two tabs: Login and Register. Email/password form for both. On success, JWT is stored in Pinia + localStorage, then redirect to `/`.

### Auth Store (`stores/auth.ts`)

Pinia store holding:

- `token: string | null` — the JWT
- `user: { email: string, id: string } | null` — decoded from JWT claims
- `isAuthenticated: boolean` — computed from token presence and expiry

Methods: `login(email, password)`, `register(email, password)`, `logout()`, `hydrate()` (load from localStorage on app start).

### API Wrapper (`composables/useApi.ts`)

Thin wrapper around Nuxt's `$fetch`:

- Attaches `Authorization: Bearer <token>` to every request
- On 401 response: clears auth store, redirects to `/login`
- On 5xx: returns error object for the calling component to handle
- On network error: returns error with "Service unavailable" message
- Base URL from `NUXT_PUBLIC_API_URL` runtime config

### Auth Middleware (`middleware/auth.global.ts`)

Runs on every route except `/login`. If no token or token is expired (decoded client-side from JWT `exp` claim), clear the store and redirect to `/login`.

No refresh token flow. The ASP.NET API issues 60-minute JWTs without a refresh endpoint. Token expiry means re-login, which is acceptable for a portfolio demo.

---

## 5. Briefing Dashboard (`pages/index.vue`)

The main view after login. Core of the application.

### Two-Phase Page Load

1. **Phase 1 (immediate):** `GET /api/briefing/latest` returns the most recent briefing with scored articles and executive summary (if previously generated). Article list and any existing summary render instantly.
2. **Phase 2 (on-demand):** User clicks "Generate Briefing" to create a new briefing via `POST /api/briefing/generate`. This triggers LLM summary generation (5-15 seconds). A spinner displays with "Generating executive summary..." while the page shows a loading state. On completion, the page refreshes with the new briefing data.

### Layout (top to bottom)

**Stats bar + pipeline controls row:**
- Left: three stat cards — "Scored" (total), "Relevant" (above threshold), "Critical" (90%+). Pulled from the briefing response article counts.
- Right: "Last run: Xh ago" timestamp, "Ingest Articles" button, "Run Scoring" button, "Generate Briefing" primary button.

**Executive summary card:**
- Label: "Executive Summary" with date
- Body: AI-generated paragraph summarizing the most important developments for this user
- Loading state: left blue border accent, spinner, "Generating executive summary... Articles are ready below. Summary typically takes 5-15 seconds."
- Error state: muted text "Executive summary temporarily unavailable" — articles remain fully functional

**Category filter pills:**
- Horizontal row of pill-shaped toggles derived from article tags
- "All" selected by default (filled primary color), others outlined
- Clicking a category filters the article list client-side

**Article feed:**
- Vertical list of `ArticleCard` components sorted by relevance score descending
- Each card shows:
  - Relevance badge: percentage score with color coding (red background `danger-light` for 90%+, blue background `primary-light` for 70-89%)
  - Headline (font-weight 600)
  - Source name and time ago
  - Personalized AI summary (2-3 sentences explaining why this matters to the user)
  - Category tags as small pills
  - "Read original" link opening the source URL in a new tab

### Relevance Badge Colors

| Score Range | Badge Background | Badge Text Color |
|---|---|---|
| 90-100% | `danger-light` (#fef2f2) | `danger` (#dc2626) |
| 70-89% | `primary-light` (#eff6ff) | `primary` (#2563eb) |
| Below 70% | gray-100 (#f1f5f9) | gray-600 (#475569) |

---

## 6. Profile Management (`pages/profile.vue`)

Where users manage their interest blocks — the narrative descriptions that drive the scoring pipeline.

### Layout

- Page heading: "Interest Profile" with subheading explaining that interests are described in natural language
- Interest blocks displayed as editable cards:
  - Label field (e.g., "Primary Role") — editable inline
  - Text body — textarea, editable inline
  - Delete button with confirmation
- "Add Interest" button at the bottom — adds a new empty block in edit mode

### Data Flow

- `useProfile.ts` composable fetches from `GET /api/profile` on mount
- Each block mutation calls `POST /api/profile/interests` (create) or `PUT /api/profile/interests/{id}` (update) or `DELETE /api/profile/interests/{id}` (delete)
- Local state updates on API success
- Profile sync to ML service happens server-side automatically via the fire-and-forget pattern — the frontend is unaware of it

### Empty State

First-time user with no interest blocks sees: "Describe what you care about and why. Each interest block captures a facet of your work — your role, your responsibilities, the topics you monitor." with a single empty block ready to fill in.

---

## 7. Briefing History (`pages/history.vue`)

Browse past briefings for the last 30 days.

### Layout

- List of briefing cards, one per generated briefing, newest first
- Each card shows: date, article count, executive summary preview (first ~100 characters, truncated)
- Clicking a card expands it inline to show the full executive summary and article list (reuses `ArticleCard` component, read-only)

### Data Flow

- `GET /api/briefing/history` returns briefing metadata (id, date, article count, summary snippet)
- Clicking a card calls `GET /api/briefing/{id}` for the full briefing with articles
- Client-side caching: once a briefing detail is fetched, store it in the composable to avoid re-fetching on repeated clicks

### Empty State

"No briefings yet. Generate your first briefing from the dashboard."

---

## 8. Pipeline Controls

Integrated into the briefing dashboard (top-right), not a separate page.

### Trigger Flow

1. User clicks "Ingest Articles", "Run Scoring", or "Generate Briefing"
2. Button shows spinner, disables to prevent double-clicks
3. `usePipeline.ts` calls `POST /api/ingestion/trigger`, `POST /api/scoring/trigger`, or `POST /api/briefing/generate`
4. For ingestion and scoring: polls the corresponding status endpoint (`GET /api/ingestion/status`, `GET /api/scoring/status`) every 3 seconds
5. On `completed`: stop polling, show success toast, refresh briefing data
6. On `failed` or polling exceeds 2 minutes: stop polling, show error toast

### Status Display

While a pipeline operation is running, the trigger button shows a spinner and the status text updates (e.g., "Ingesting... 47 articles found"). When complete, a toast notification confirms success.

---

## 9. Toast Notifications

A simple reactive system — no library needed.

### Implementation

- `useToast.ts` composable: reactive array of `{ id, message, type, timeout }` objects
- Components push messages via `useToast().show('message', 'success')`
- `ToastContainer.vue` in the default layout renders toasts in the bottom-right corner
- Auto-dismiss after 5 seconds, with manual close button
- Types: `success` (green accent), `error` (red accent), `info` (blue accent)

---

## 10. Composables Detail

### `useAuth.ts`

Wraps the Pinia auth store for convenience. Exposes `login()`, `register()`, `logout()`, `isAuthenticated`, `user`. Handles the login/register API calls and store mutations in one place.

### `useApi.ts`

Factory function returning a configured `$fetch` instance. All other composables use this rather than calling `$fetch` directly. Centralizes auth headers and error handling.

### `useBriefing.ts`

- `fetchLatest()` — `GET /api/briefing/latest`, returns briefing with articles
- `generate()` — `POST /api/briefing/generate`, triggers async generation
- `briefing` — reactive ref holding the current briefing data
- `isGenerating` — reactive ref for loading state

### `useProfile.ts`

- `fetchProfile()` — `GET /api/profile`
- `addInterest(label, text)` — `POST /api/profile/interests`
- `updateInterest(id, label, text)` — `PUT /api/profile/interests/{id}`
- `deleteInterest(id)` — `DELETE /api/profile/interests/{id}`
- `interests` — reactive ref holding the interest blocks array

### `usePipeline.ts`

- `triggerIngestion()` — `POST /api/ingestion/trigger`, starts polling
- `triggerScoring()` — `POST /api/scoring/trigger`, starts polling
- `ingestionStatus` / `scoringStatus` — reactive refs
- `isIngesting` / `isScoring` — reactive boolean refs
- Polling logic: 3-second interval, stops on completion/failure/2-minute timeout

### `useToast.ts`

- `show(message, type)` — add a toast
- `dismiss(id)` — remove a toast
- `toasts` — reactive array for `ToastContainer` to render

---

## 11. TypeScript Interfaces

```ts
// types/index.ts

interface User {
  id: string
  email: string
}

interface AuthResponse {
  token: string
}

interface InterestBlock {
  id: string
  label: string
  text: string
}

interface Profile {
  id: string
  userId: string
  version: number
  interests: InterestBlock[]
}

interface Article {
  id: string
  title: string
  source: string
  url: string
  publishedAt: string
  summary: string        // personalized AI summary
  displayScore: number   // 0-100 percentile
  tags: string[]
}

interface Briefing {
  id: string
  createdAt: string
  executiveSummary: string | null
  articles: Article[]
  articleCount: number
}

interface BriefingHistoryItem {
  id: string
  createdAt: string
  articleCount: number
  summaryPreview: string
}

interface PipelineStatus {
  status: 'idle' | 'running' | 'completed' | 'failed'
  message?: string
  articleCount?: number
}
```

---

## 12. Runtime Configuration

```ts
// nuxt.config.ts
export default defineNuxtConfig({
  runtimeConfig: {
    public: {
      apiUrl: 'http://localhost:5000/api'  // ASP.NET Web API
    }
  }
})
```

Overridden via `NUXT_PUBLIC_API_URL` environment variable in production/Docker.

---

## 13. Development & Build

```bash
# Development
cd src/frontend
npm install
npm run dev    # starts on http://localhost:3000

# Production build
npm run build
npm run preview
```

The Nuxt dev server proxies API calls or the frontend is configured to hit the ASP.NET API URL directly via `NUXT_PUBLIC_API_URL`. In Docker Compose, both services run behind a reverse proxy or the frontend is configured with the internal service URL.

---

## 14. What's Deferred

These features exist in the backend but are not included in this frontend iteration:

| Feature | Backend Endpoint | Why Deferred |
|---|---|---|
| Source preferences | `GET/POST/DELETE /api/sourcepreferences` | Low demo value, straightforward CRUD |
| Feedback controls | Not yet implemented | Requires backend feedback endpoint |
| Full-text search | Would need new endpoint | Article summaries are searchable enough for demo |
| Guided profile builder | Planned, not built | Requires multi-turn LLM conversation backend |

# Briefer Frontend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Vue/Nuxt frontend dashboard for the Briefer news intelligence platform, connecting to the existing ASP.NET Web API backend.

**Architecture:** Nuxt 3 with file-based routing, Tailwind CSS for styling with centralized design tokens, Pinia for auth state, hand-rolled components. Pages + composables flat structure — no abstraction layers beyond what Nuxt provides.

**Tech Stack:** Nuxt 3, Vue 3 Composition API, Tailwind CSS, Pinia, TypeScript

**Spec:** `docs/superpowers/specs/2026-04-11-frontend-design.md`

---

## File Structure

```
src/frontend/
├── package.json
├── nuxt.config.ts
├── tailwind.config.ts
├── tsconfig.json
├── app.vue
├── types/
│   └── index.ts              # All TypeScript interfaces
├── stores/
│   └── auth.ts               # Pinia auth store (token, user, hydrate)
├── composables/
│   ├── useApi.ts             # $fetch wrapper with auth headers + 401 handling
│   ├── useAuth.ts            # Wraps auth store, exposes login/register/logout
│   ├── useToast.ts           # Reactive toast notification system
│   ├── useBriefing.ts        # Fetch latest, generate, briefing state
│   ├── useProfile.ts         # Interest blocks CRUD
│   └── usePipeline.ts        # Ingestion/scoring triggers + status
├── middleware/
│   └── auth.global.ts        # Redirect to /login if no valid token
├── layouts/
│   └── default.vue           # Nav bar + toast container wrapper
├── components/
│   ├── AppNav.vue            # Top navigation bar
│   ├── ToastContainer.vue    # Renders toast notifications
│   ├── StatsBar.vue          # Article count stat cards
│   ├── ExecutiveSummary.vue  # Summary card with loading/error states
│   ├── ArticleCard.vue       # Single article in the feed
│   ├── InterestBlock.vue     # Editable interest block card
│   └── PipelineControls.vue  # Ingest/Score/Generate buttons with status
├── pages/
│   ├── login.vue             # Login + register tabbed form
│   ├── index.vue             # Briefing dashboard (main view)
│   ├── profile.vue           # Interest profile management
│   └── history.vue           # Past briefings list + detail
└── public/
    └── favicon.ico
```

---

## Task 1: Scaffold Nuxt Project with Tailwind

**Files:**
- Create: `src/frontend/package.json`
- Create: `src/frontend/nuxt.config.ts`
- Create: `src/frontend/tailwind.config.ts`
- Create: `src/frontend/tsconfig.json`
- Create: `src/frontend/app.vue`
- Create: `src/frontend/.gitignore`

- [ ] **Step 1: Initialize Nuxt project**

```bash
cd /mnt/c/Users/mark/source/repos/Briefer/src
npx nuxi@latest init frontend --packageManager npm --gitInit false
```

When prompted, accept defaults. This creates the base Nuxt project.

- [ ] **Step 2: Install dependencies**

```bash
cd /mnt/c/Users/mark/source/repos/Briefer/src/frontend
npm install @pinia/nuxt pinia
npm install -D @nuxtjs/tailwindcss tailwindcss
```

- [ ] **Step 3: Create Tailwind config with design tokens**

Create `src/frontend/tailwind.config.ts`:

```ts
import type { Config } from 'tailwindcss'

export default {
  content: [
    './components/**/*.vue',
    './layouts/**/*.vue',
    './pages/**/*.vue',
    './composables/**/*.ts',
    './app.vue',
  ],
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
      },
    },
  },
} satisfies Config
```

- [ ] **Step 4: Configure Nuxt**

Replace `src/frontend/nuxt.config.ts` with:

```ts
export default defineNuxtConfig({
  modules: ['@nuxtjs/tailwindcss', '@pinia/nuxt'],
  devtools: { enabled: false },
  ssr: false,
  runtimeConfig: {
    public: {
      apiUrl: 'http://localhost:5000/api',
    },
  },
  app: {
    head: {
      title: 'Briefer',
      meta: [
        { name: 'description', content: 'AI-powered news intelligence platform' },
      ],
    },
  },
})
```

Note: `ssr: false` because this is a client-side SPA that talks to a separate API. No server-side rendering needed.

- [ ] **Step 5: Create minimal app.vue**

Replace `src/frontend/app.vue` with:

```vue
<template>
  <NuxtLayout>
    <NuxtPage />
  </NuxtLayout>
</template>
```

- [ ] **Step 6: Create .gitignore**

Create `src/frontend/.gitignore`:

```
node_modules/
.nuxt/
.output/
dist/
.env
```

- [ ] **Step 7: Verify it runs**

```bash
cd /mnt/c/Users/mark/source/repos/Briefer/src/frontend
npm run dev
```

Expected: Nuxt dev server starts on http://localhost:3000 with no errors. You'll see a blank page (no pages defined yet). Stop the dev server after confirming.

- [ ] **Step 8: Commit**

```bash
cd /mnt/c/Users/mark/source/repos/Briefer
git add src/frontend/
git commit -m "feat(frontend): scaffold Nuxt 3 project with Tailwind and Pinia"
```

---

## Task 2: TypeScript Interfaces and Auth Store

**Files:**
- Create: `src/frontend/types/index.ts`
- Create: `src/frontend/stores/auth.ts`

- [ ] **Step 1: Create TypeScript interfaces**

Create `src/frontend/types/index.ts`:

```ts
export interface User {
  id: string
  email: string
}

export interface AuthResponse {
  token: string
}

export interface RegisterRequest {
  email: string
  password: string
}

export interface LoginRequest {
  email: string
  password: string
}

export interface InterestBlock {
  id: string
  title: string
  description: string
  sortOrder: number
}

export interface InterestRequest {
  title: string
  description: string
  sortOrder?: number
}

export interface Profile {
  version: number
  interests: InterestBlock[]
}

export interface BriefingArticle {
  article_id: string
  title: string
  source_name: string
  url: string
  rank: number
  display_score: number | null
  summary: string | null
  priority: string | null
  explanation: string | null
}

export interface Briefing {
  id: string
  user_id: string
  status: string
  article_count: number
  executive_summary: string | null
  profile_version: number
  generated_at: string | null
  created_at: string | null
  articles: BriefingArticle[]
}

export interface BriefingHistoryItem {
  id: string
  status: string
  article_count: number
  has_summary: boolean
  generated_at: string | null
  created_at: string | null
}

export interface IngestionResult {
  fetched: number
  extracted: number
  new: number
  embedded: number
}

export interface IngestionTriggerResponse {
  status: string
  result: IngestionResult
}

export interface IngestionStatus {
  running: boolean
  last_result: IngestionResult | null
  last_run_at: string | null
}

export interface ScoringUserResult {
  user_id: string | null
  candidates_retrieved: number
  reranked: number
  llm_scored: number
  summarized: number
  stored: number
}

export interface ScoringTriggerResponse {
  status: string
  results: ScoringUserResult[]
}

export interface ScoringStatus {
  running: boolean
  last_results: ScoringUserResult[] | null
  last_run_at: string | null
}

export interface ApiError {
  error?: string
  errors?: string[]
  detail?: string
}
```

- [ ] **Step 2: Create Pinia auth store**

Create `src/frontend/stores/auth.ts`:

```ts
import { defineStore } from 'pinia'
import type { User } from '~/types'

function decodeJwtPayload(token: string): Record<string, unknown> | null {
  try {
    const base64 = token.split('.')[1]
    const json = atob(base64.replace(/-/g, '+').replace(/_/g, '/'))
    return JSON.parse(json)
  } catch {
    return null
  }
}

function isTokenExpired(token: string): boolean {
  const payload = decodeJwtPayload(token)
  if (!payload || typeof payload.exp !== 'number') return true
  return Date.now() >= payload.exp * 1000
}

function extractUser(token: string): User | null {
  const payload = decodeJwtPayload(token)
  if (!payload) return null
  const id = (payload.nameid ?? payload.sub ?? '') as string
  const email = (payload.email ?? payload.unique_name ?? '') as string
  if (!id || !email) return null
  return { id, email }
}

export const useAuthStore = defineStore('auth', {
  state: () => ({
    token: null as string | null,
    user: null as User | null,
  }),

  getters: {
    isAuthenticated(): boolean {
      return this.token !== null && !isTokenExpired(this.token)
    },
  },

  actions: {
    setToken(token: string) {
      this.token = token
      this.user = extractUser(token)
      localStorage.setItem('briefer_token', token)
    },

    logout() {
      this.token = null
      this.user = null
      localStorage.removeItem('briefer_token')
    },

    hydrate() {
      const token = localStorage.getItem('briefer_token')
      if (token && !isTokenExpired(token)) {
        this.token = token
        this.user = extractUser(token)
      } else {
        localStorage.removeItem('briefer_token')
      }
    },
  },
})
```

- [ ] **Step 3: Verify types compile**

```bash
cd /mnt/c/Users/mark/source/repos/Briefer/src/frontend
npx nuxi typecheck
```

Expected: No type errors. (May show warnings on first run while Nuxt generates its types — that's fine.)

- [ ] **Step 4: Commit**

```bash
cd /mnt/c/Users/mark/source/repos/Briefer
git add src/frontend/types/ src/frontend/stores/
git commit -m "feat(frontend): add TypeScript interfaces and Pinia auth store"
```

---

## Task 3: API Wrapper and Auth Composables

**Files:**
- Create: `src/frontend/composables/useApi.ts`
- Create: `src/frontend/composables/useAuth.ts`
- Create: `src/frontend/composables/useToast.ts`

- [ ] **Step 1: Create useApi composable**

Create `src/frontend/composables/useApi.ts`:

```ts
import { useAuthStore } from '~/stores/auth'
import type { ApiError } from '~/types'

interface ApiOptions {
  method?: 'GET' | 'POST' | 'PUT' | 'DELETE'
  body?: unknown
  query?: Record<string, string | number>
}

interface ApiResult<T> {
  data: T | null
  error: string | null
}

export function useApi() {
  const config = useRuntimeConfig()
  const authStore = useAuthStore()

  async function request<T>(path: string, options: ApiOptions = {}): Promise<ApiResult<T>> {
    const headers: Record<string, string> = {}
    if (authStore.token) {
      headers['Authorization'] = `Bearer ${authStore.token}`
    }

    try {
      const data = await $fetch<T>(path, {
        baseURL: config.public.apiUrl as string,
        method: options.method ?? 'GET',
        headers,
        body: options.body,
        query: options.query,
      })
      return { data, error: null }
    } catch (err: unknown) {
      const fetchError = err as { statusCode?: number; data?: ApiError }

      if (fetchError.statusCode === 401) {
        authStore.logout()
        navigateTo('/login')
        return { data: null, error: 'Session expired' }
      }

      const apiError = fetchError.data
      const message =
        apiError?.error ??
        apiError?.detail ??
        apiError?.errors?.join(', ') ??
        'Service unavailable'
      return { data: null, error: message }
    }
  }

  return { request }
}
```

- [ ] **Step 2: Create useAuth composable**

Create `src/frontend/composables/useAuth.ts`:

```ts
import { useAuthStore } from '~/stores/auth'
import type { AuthResponse } from '~/types'

export function useAuth() {
  const authStore = useAuthStore()
  const { request } = useApi()

  async function login(email: string, password: string): Promise<string | null> {
    const { data, error } = await request<AuthResponse>('/auth/login', {
      method: 'POST',
      body: { email, password },
    })
    if (error) return error
    authStore.setToken(data!.token)
    return null
  }

  async function register(email: string, password: string): Promise<string | null> {
    const { data, error } = await request<AuthResponse>('/auth/register', {
      method: 'POST',
      body: { email, password },
    })
    if (error) return error
    authStore.setToken(data!.token)
    return null
  }

  function logout() {
    authStore.logout()
    navigateTo('/login')
  }

  return {
    login,
    register,
    logout,
    get isAuthenticated() { return authStore.isAuthenticated },
    get user() { return authStore.user },
  }
}
```

- [ ] **Step 3: Create useToast composable**

Create `src/frontend/composables/useToast.ts`:

```ts
import { ref } from 'vue'

export interface Toast {
  id: number
  message: string
  type: 'success' | 'error' | 'info'
}

const toasts = ref<Toast[]>([])
let nextId = 0

export function useToast() {
  function show(message: string, type: Toast['type'] = 'info') {
    const id = nextId++
    toasts.value.push({ id, message, type })
    setTimeout(() => dismiss(id), 5000)
  }

  function dismiss(id: number) {
    toasts.value = toasts.value.filter(t => t.id !== id)
  }

  return { toasts, show, dismiss }
}
```

- [ ] **Step 4: Commit**

```bash
cd /mnt/c/Users/mark/source/repos/Briefer
git add src/frontend/composables/useApi.ts src/frontend/composables/useAuth.ts src/frontend/composables/useToast.ts
git commit -m "feat(frontend): add API wrapper, auth, and toast composables"
```

---

## Task 4: Auth Middleware, Layout, and Login Page

**Files:**
- Create: `src/frontend/middleware/auth.global.ts`
- Create: `src/frontend/layouts/default.vue`
- Create: `src/frontend/components/AppNav.vue`
- Create: `src/frontend/components/ToastContainer.vue`
- Create: `src/frontend/pages/login.vue`

- [ ] **Step 1: Create auth middleware**

Create `src/frontend/middleware/auth.global.ts`:

```ts
import { useAuthStore } from '~/stores/auth'

export default defineNuxtRouteMiddleware((to) => {
  const authStore = useAuthStore()

  if (to.path !== '/login') {
    authStore.hydrate()
    if (!authStore.isAuthenticated) {
      return navigateTo('/login')
    }
  }
})
```

- [ ] **Step 2: Create AppNav component**

Create `src/frontend/components/AppNav.vue`:

```vue
<template>
  <nav class="bg-surface-card border-b border-border px-8 py-3 flex justify-between items-center">
    <span class="text-text-primary text-lg font-bold tracking-tight">Briefer</span>
    <div class="flex items-center gap-7 text-sm">
      <NuxtLink
        to="/"
        class="font-semibold"
        :class="route.path === '/' ? 'text-text-primary border-b-2 border-primary pb-2.5 -mb-3.5' : 'text-text-secondary hover:text-text-primary'"
      >
        Briefing
      </NuxtLink>
      <NuxtLink
        to="/profile"
        class="font-semibold"
        :class="route.path === '/profile' ? 'text-text-primary border-b-2 border-primary pb-2.5 -mb-3.5' : 'text-text-secondary hover:text-text-primary'"
      >
        Profile
      </NuxtLink>
      <NuxtLink
        to="/history"
        class="font-semibold"
        :class="route.path === '/history' ? 'text-text-primary border-b-2 border-primary pb-2.5 -mb-3.5' : 'text-text-secondary hover:text-text-primary'"
      >
        History
      </NuxtLink>
      <span class="text-text-muted">{{ user?.email }}</span>
      <button
        class="text-text-secondary hover:text-text-primary text-sm"
        @click="logout"
      >
        Logout
      </button>
    </div>
  </nav>
</template>

<script setup lang="ts">
const route = useRoute()
const { user, logout } = useAuth()
</script>
```

- [ ] **Step 3: Create ToastContainer component**

Create `src/frontend/components/ToastContainer.vue`:

```vue
<template>
  <div class="fixed bottom-6 right-6 z-50 flex flex-col gap-3 w-80">
    <TransitionGroup name="toast">
      <div
        v-for="toast in toasts"
        :key="toast.id"
        class="rounded-lg px-4 py-3 shadow-lg border flex items-start justify-between gap-3 text-sm"
        :class="colorClasses[toast.type]"
      >
        <span>{{ toast.message }}</span>
        <button
          class="opacity-60 hover:opacity-100 shrink-0"
          @click="dismiss(toast.id)"
        >
          &times;
        </button>
      </div>
    </TransitionGroup>
  </div>
</template>

<script setup lang="ts">
const { toasts, dismiss } = useToast()

const colorClasses: Record<string, string> = {
  success: 'bg-green-50 border-green-200 text-green-800',
  error: 'bg-danger-light border-red-200 text-danger',
  info: 'bg-primary-light border-blue-200 text-primary',
}
</script>

<style scoped>
.toast-enter-active,
.toast-leave-active {
  transition: all 0.3s ease;
}
.toast-enter-from {
  opacity: 0;
  transform: translateX(40px);
}
.toast-leave-to {
  opacity: 0;
  transform: translateX(40px);
}
</style>
```

- [ ] **Step 4: Create default layout**

Create `src/frontend/layouts/default.vue`:

```vue
<template>
  <div class="min-h-screen bg-surface">
    <AppNav />
    <main class="px-8 py-7">
      <slot />
    </main>
    <ToastContainer />
  </div>
</template>
```

- [ ] **Step 5: Create login page**

Create `src/frontend/pages/login.vue`:

```vue
<template>
  <div class="min-h-screen bg-surface flex items-center justify-center">
    <div class="bg-surface-card border border-border rounded-xl p-8 w-full max-w-sm shadow-sm">
      <h1 class="text-2xl font-bold text-text-primary mb-6 text-center">Briefer</h1>

      <!-- Tabs -->
      <div class="flex border-b border-border mb-6">
        <button
          class="flex-1 pb-3 text-sm font-semibold"
          :class="tab === 'login' ? 'text-primary border-b-2 border-primary' : 'text-text-muted'"
          @click="tab = 'login'"
        >
          Login
        </button>
        <button
          class="flex-1 pb-3 text-sm font-semibold"
          :class="tab === 'register' ? 'text-primary border-b-2 border-primary' : 'text-text-muted'"
          @click="tab = 'register'"
        >
          Register
        </button>
      </div>

      <!-- Form -->
      <form @submit.prevent="handleSubmit">
        <div class="mb-4">
          <label class="block text-xs font-medium text-text-secondary mb-1.5">Email</label>
          <input
            v-model="email"
            type="email"
            required
            class="w-full border border-border rounded-lg px-3 py-2 text-sm text-text-primary bg-surface-card focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary"
            placeholder="you@example.com"
          />
        </div>
        <div class="mb-6">
          <label class="block text-xs font-medium text-text-secondary mb-1.5">Password</label>
          <input
            v-model="password"
            type="password"
            required
            minlength="8"
            class="w-full border border-border rounded-lg px-3 py-2 text-sm text-text-primary bg-surface-card focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary"
            placeholder="Min 8 characters"
          />
        </div>

        <p v-if="error" class="text-danger text-xs mb-4">{{ error }}</p>

        <button
          type="submit"
          :disabled="loading"
          class="w-full bg-primary text-white rounded-lg py-2.5 text-sm font-medium hover:bg-blue-700 disabled:opacity-50 transition-colors"
        >
          <span v-if="loading">{{ tab === 'login' ? 'Signing in...' : 'Creating account...' }}</span>
          <span v-else>{{ tab === 'login' ? 'Sign In' : 'Create Account' }}</span>
        </button>
      </form>
    </div>
  </div>
</template>

<script setup lang="ts">
definePageMeta({ layout: false })

const { login, register } = useAuth()

const tab = ref<'login' | 'register'>('login')
const email = ref('')
const password = ref('')
const error = ref<string | null>(null)
const loading = ref(false)

async function handleSubmit() {
  error.value = null
  loading.value = true

  const result = tab.value === 'login'
    ? await login(email.value, password.value)
    : await register(email.value, password.value)

  loading.value = false

  if (result) {
    error.value = result
  } else {
    navigateTo('/')
  }
}
</script>
```

Note: `definePageMeta({ layout: false })` prevents the default layout (with nav bar) from rendering on the login page.

- [ ] **Step 6: Verify login page renders**

```bash
cd /mnt/c/Users/mark/source/repos/Briefer/src/frontend
npm run dev
```

Open http://localhost:3000 in a browser. Expected: You should be redirected to `/login` and see the login/register card. The form should render with both tabs, email/password fields, and submit button. Stop the dev server.

- [ ] **Step 7: Commit**

```bash
cd /mnt/c/Users/mark/source/repos/Briefer
git add src/frontend/middleware/ src/frontend/layouts/ src/frontend/components/AppNav.vue src/frontend/components/ToastContainer.vue src/frontend/pages/login.vue
git commit -m "feat(frontend): add auth middleware, layout, nav, toasts, and login page"
```

---

## Task 5: Briefing Composables (Briefing + Pipeline)

**Files:**
- Create: `src/frontend/composables/useBriefing.ts`
- Create: `src/frontend/composables/usePipeline.ts`

- [ ] **Step 1: Create useBriefing composable**

Create `src/frontend/composables/useBriefing.ts`:

```ts
import { ref } from 'vue'
import type { Briefing } from '~/types'

const briefing = ref<Briefing | null>(null)
const isLoading = ref(false)
const isGenerating = ref(false)
const error = ref<string | null>(null)

export function useBriefing() {
  const { request } = useApi()

  async function fetchLatest() {
    isLoading.value = true
    error.value = null
    const { data, error: err } = await request<Briefing>('/briefing/latest')
    isLoading.value = false
    if (err) {
      // 404 means no briefings yet — not an error state
      if (err === 'No briefings found') {
        briefing.value = null
        return
      }
      error.value = err
      return
    }
    briefing.value = data
  }

  async function generate() {
    isGenerating.value = true
    error.value = null
    const { data, error: err } = await request<Briefing>('/briefing/generate', {
      method: 'POST',
    })
    isGenerating.value = false
    if (err) {
      error.value = err
      return
    }
    briefing.value = data
  }

  return { briefing, isLoading, isGenerating, error, fetchLatest, generate }
}
```

- [ ] **Step 2: Create usePipeline composable**

Create `src/frontend/composables/usePipeline.ts`:

```ts
import { ref } from 'vue'
import type {
  IngestionTriggerResponse,
  IngestionStatus,
  ScoringTriggerResponse,
  ScoringStatus,
} from '~/types'

const isIngesting = ref(false)
const isScoring = ref(false)
const ingestionStatus = ref<IngestionStatus | null>(null)
const scoringStatus = ref<ScoringStatus | null>(null)

export function usePipeline() {
  const { request } = useApi()
  const { show } = useToast()

  async function fetchIngestionStatus() {
    const { data } = await request<IngestionStatus>('/ingestion/status')
    if (data) ingestionStatus.value = data
  }

  async function fetchScoringStatus() {
    const { data } = await request<ScoringStatus>('/scoring/status')
    if (data) scoringStatus.value = data
  }

  async function triggerIngestion() {
    isIngesting.value = true
    const { data, error } = await request<IngestionTriggerResponse>('/ingestion/trigger', {
      method: 'POST',
    })
    isIngesting.value = false

    if (error) {
      show(error, 'error')
      return
    }

    const result = data!.result
    show(`Ingestion complete: ${result.new} new articles (${result.fetched} fetched)`, 'success')
    await fetchIngestionStatus()
  }

  async function triggerScoring() {
    isScoring.value = true
    const { data, error } = await request<ScoringTriggerResponse>('/scoring/trigger', {
      method: 'POST',
    })
    isScoring.value = false

    if (error) {
      show(error, 'error')
      return
    }

    const total = data!.results.reduce((sum, r) => sum + r.stored, 0)
    show(`Scoring complete: ${total} articles scored`, 'success')
    await fetchScoringStatus()
  }

  return {
    isIngesting,
    isScoring,
    ingestionStatus,
    scoringStatus,
    fetchIngestionStatus,
    fetchScoringStatus,
    triggerIngestion,
    triggerScoring,
  }
}
```

- [ ] **Step 3: Commit**

```bash
cd /mnt/c/Users/mark/source/repos/Briefer
git add src/frontend/composables/useBriefing.ts src/frontend/composables/usePipeline.ts
git commit -m "feat(frontend): add briefing and pipeline composables"
```

---

## Task 6: Briefing Dashboard Components

**Files:**
- Create: `src/frontend/components/StatsBar.vue`
- Create: `src/frontend/components/ExecutiveSummary.vue`
- Create: `src/frontend/components/ArticleCard.vue`
- Create: `src/frontend/components/PipelineControls.vue`

- [ ] **Step 1: Create StatsBar component**

Create `src/frontend/components/StatsBar.vue`:

```vue
<template>
  <div class="flex gap-3.5">
    <div class="bg-surface-card border border-border rounded-lg px-5 py-3 min-w-[100px]">
      <div class="text-2xl font-bold text-text-primary">{{ total }}</div>
      <div class="text-xs text-text-muted mt-0.5">Scored</div>
    </div>
    <div class="bg-surface-card border border-border rounded-lg px-5 py-3 min-w-[100px]">
      <div class="text-2xl font-bold text-primary">{{ relevant }}</div>
      <div class="text-xs text-text-muted mt-0.5">Relevant</div>
    </div>
    <div class="bg-surface-card border border-border rounded-lg px-5 py-3 min-w-[100px]">
      <div class="text-2xl font-bold text-danger">{{ critical }}</div>
      <div class="text-xs text-text-muted mt-0.5">Critical</div>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { BriefingArticle } from '~/types'

const props = defineProps<{
  articles: BriefingArticle[]
}>()

const total = computed(() => props.articles.length)
const relevant = computed(() =>
  props.articles.filter(a => (a.display_score ?? 0) >= 70).length
)
const critical = computed(() =>
  props.articles.filter(a => (a.display_score ?? 0) >= 90).length
)
</script>
```

- [ ] **Step 2: Create ExecutiveSummary component**

Create `src/frontend/components/ExecutiveSummary.vue`:

```vue
<template>
  <!-- Generating state -->
  <div
    v-if="generating"
    class="bg-surface-card border border-border border-l-[3px] border-l-primary rounded-xl p-6 mb-5"
  >
    <div class="flex items-center gap-2.5 mb-2">
      <div class="w-3.5 h-3.5 border-2 border-primary border-t-transparent rounded-full animate-spin" />
      <span class="text-xs uppercase tracking-wider text-primary font-medium">
        Generating executive summary...
      </span>
    </div>
    <p class="text-sm text-text-muted">Articles are ready below. Summary typically takes 5-15 seconds.</p>
  </div>

  <!-- Summary loaded -->
  <div
    v-else-if="summary"
    class="bg-surface-card border border-border rounded-xl p-6 mb-5"
  >
    <div class="flex justify-between items-center mb-3">
      <span class="text-xs uppercase tracking-wider text-text-muted">Executive Summary</span>
      <span class="text-xs text-text-muted">{{ formattedDate }}</span>
    </div>
    <p class="text-sm leading-7 text-text-secondary">{{ summary }}</p>
  </div>

  <!-- Error state -->
  <div
    v-else-if="error"
    class="bg-surface-card border border-border rounded-xl p-6 mb-5"
  >
    <p class="text-sm text-text-muted">Executive summary temporarily unavailable.</p>
  </div>
</template>

<script setup lang="ts">
const props = defineProps<{
  summary: string | null
  generating: boolean
  error: boolean
  date: string | null
}>()

const formattedDate = computed(() => {
  if (!props.date) return ''
  return new Date(props.date).toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
  })
})
</script>
```

- [ ] **Step 3: Create ArticleCard component**

Create `src/frontend/components/ArticleCard.vue`:

```vue
<template>
  <div class="bg-surface-card border border-border rounded-xl p-5 flex gap-4 items-start">
    <!-- Relevance badge -->
    <div
      class="text-xs font-bold px-2.5 py-1 rounded-md min-w-[42px] text-center shrink-0"
      :class="badgeClasses"
    >
      {{ scoreDisplay }}
    </div>

    <div class="flex-1 min-w-0">
      <!-- Headline -->
      <h3 class="text-[15px] font-semibold text-text-primary leading-snug">
        {{ article.title }}
      </h3>

      <!-- Source + time -->
      <p class="text-xs text-text-muted mt-1.5">
        {{ article.source_name }}<span v-if="timeAgo"> &bull; {{ timeAgo }}</span>
      </p>

      <!-- AI summary -->
      <p
        v-if="article.summary"
        class="text-sm text-text-secondary mt-2.5 leading-relaxed"
      >
        {{ article.summary }}
      </p>

      <!-- Tags + link row -->
      <div class="flex items-center gap-2 mt-3 flex-wrap">
        <span
          v-if="article.priority"
          class="text-[11px] bg-gray-100 text-gray-600 px-2.5 py-0.5 rounded"
        >
          {{ article.priority }}
        </span>
        <a
          :href="article.url"
          target="_blank"
          rel="noopener"
          class="text-xs text-primary hover:underline ml-auto shrink-0"
        >
          Read original &rarr;
        </a>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { BriefingArticle } from '~/types'

const props = defineProps<{
  article: BriefingArticle
}>()

const score = computed(() => props.article.display_score ?? 0)
const scoreDisplay = computed(() => `${Math.round(score.value)}%`)

const badgeClasses = computed(() => {
  if (score.value >= 90) return 'bg-danger-light text-danger'
  if (score.value >= 70) return 'bg-primary-light text-primary'
  return 'bg-gray-100 text-gray-600'
})

const timeAgo = computed(() => {
  if (!props.article.rank) return null
  // Articles don't carry a publishedAt field from the briefing endpoint,
  // so we show rank instead if no timestamp is available
  return `#${props.article.rank}`
})
</script>
```

- [ ] **Step 4: Create PipelineControls component**

Create `src/frontend/components/PipelineControls.vue`:

```vue
<template>
  <div class="flex items-center gap-2">
    <span v-if="lastRunLabel" class="text-xs text-text-muted mr-1">{{ lastRunLabel }}</span>

    <button
      :disabled="isIngesting"
      class="bg-surface-card border border-border rounded-md px-3.5 py-1.5 text-xs text-text-secondary hover:bg-gray-50 disabled:opacity-50 transition-colors"
      @click="handleIngest"
    >
      <span v-if="isIngesting" class="flex items-center gap-1.5">
        <span class="w-3 h-3 border-2 border-text-muted border-t-transparent rounded-full animate-spin" />
        Ingesting...
      </span>
      <span v-else>Ingest Articles</span>
    </button>

    <button
      :disabled="isScoring"
      class="bg-surface-card border border-border rounded-md px-3.5 py-1.5 text-xs text-text-secondary hover:bg-gray-50 disabled:opacity-50 transition-colors"
      @click="handleScore"
    >
      <span v-if="isScoring" class="flex items-center gap-1.5">
        <span class="w-3 h-3 border-2 border-text-muted border-t-transparent rounded-full animate-spin" />
        Scoring...
      </span>
      <span v-else>Run Scoring</span>
    </button>

    <button
      :disabled="isGenerating"
      class="bg-primary text-white rounded-md px-3.5 py-1.5 text-xs font-medium hover:bg-blue-700 disabled:opacity-50 transition-colors"
      @click="$emit('generate')"
    >
      <span v-if="isGenerating" class="flex items-center gap-1.5">
        <span class="w-3 h-3 border-2 border-white border-t-transparent rounded-full animate-spin" />
        Generating...
      </span>
      <span v-else>Generate Briefing</span>
    </button>
  </div>
</template>

<script setup lang="ts">
defineEmits<{
  generate: []
}>()

defineProps<{
  isGenerating: boolean
}>()

const {
  isIngesting,
  isScoring,
  ingestionStatus,
  triggerIngestion,
  triggerScoring,
  fetchIngestionStatus,
} = usePipeline()

const { fetchLatest } = useBriefing()

const lastRunLabel = computed(() => {
  const lastRun = ingestionStatus.value?.last_run_at
  if (!lastRun) return null
  const diff = Date.now() - new Date(lastRun).getTime()
  const hours = Math.floor(diff / 3600000)
  if (hours < 1) return 'Last run: just now'
  return `Last run: ${hours}h ago`
})

async function handleIngest() {
  await triggerIngestion()
}

async function handleScore() {
  await triggerScoring()
  await fetchLatest()
}

onMounted(() => {
  fetchIngestionStatus()
})
</script>
```

- [ ] **Step 5: Commit**

```bash
cd /mnt/c/Users/mark/source/repos/Briefer
git add src/frontend/components/StatsBar.vue src/frontend/components/ExecutiveSummary.vue src/frontend/components/ArticleCard.vue src/frontend/components/PipelineControls.vue
git commit -m "feat(frontend): add briefing dashboard components"
```

---

## Task 7: Briefing Dashboard Page

**Files:**
- Create: `src/frontend/pages/index.vue`

- [ ] **Step 1: Create the briefing dashboard page**

Create `src/frontend/pages/index.vue`:

```vue
<template>
  <div>
    <!-- Stats + Pipeline controls row -->
    <div class="flex justify-between items-start mb-5">
      <StatsBar :articles="articles" />
      <PipelineControls :is-generating="isGenerating" @generate="handleGenerate" />
    </div>

    <!-- Executive Summary -->
    <ExecutiveSummary
      :summary="briefing?.executive_summary ?? null"
      :generating="isGenerating"
      :error="!!error && !isGenerating"
      :date="briefing?.generated_at ?? briefing?.created_at ?? null"
    />

    <!-- Category filter pills -->
    <div v-if="categories.length > 1" class="flex gap-2 mb-5 flex-wrap">
      <button
        class="text-xs px-3 py-1 rounded-full transition-colors"
        :class="selectedCategory === null
          ? 'bg-primary text-white'
          : 'bg-surface-card border border-border text-text-secondary hover:bg-gray-50'"
        @click="selectedCategory = null"
      >
        All
      </button>
      <button
        v-for="cat in categories"
        :key="cat"
        class="text-xs px-3 py-1 rounded-full transition-colors"
        :class="selectedCategory === cat
          ? 'bg-primary text-white'
          : 'bg-surface-card border border-border text-text-secondary hover:bg-gray-50'"
        @click="selectedCategory = cat"
      >
        {{ cat }} ({{ categoryCounts[cat] }})
      </button>
    </div>

    <!-- Article feed -->
    <div v-if="filteredArticles.length" class="flex flex-col gap-3">
      <ArticleCard
        v-for="article in filteredArticles"
        :key="article.article_id"
        :article="article"
      />
    </div>

    <!-- Empty state -->
    <div
      v-else-if="!isLoading && !isGenerating"
      class="bg-surface-card border border-border rounded-xl p-12 text-center"
    >
      <p class="text-text-secondary mb-2">No briefing available yet.</p>
      <p class="text-sm text-text-muted">
        Click "Ingest Articles" to fetch news, then "Run Scoring" to score them, and finally "Generate Briefing" to create your first briefing.
      </p>
    </div>

    <!-- Loading state -->
    <div v-else-if="isLoading" class="flex justify-center py-12">
      <div class="w-6 h-6 border-2 border-primary border-t-transparent rounded-full animate-spin" />
    </div>
  </div>
</template>

<script setup lang="ts">
const { briefing, isLoading, isGenerating, error, fetchLatest, generate } = useBriefing()

const selectedCategory = ref<string | null>(null)

const articles = computed(() => {
  if (!briefing.value) return []
  return [...briefing.value.articles].sort(
    (a, b) => (b.display_score ?? 0) - (a.display_score ?? 0)
  )
})

const categories = computed(() => {
  const cats = new Set<string>()
  for (const a of articles.value) {
    if (a.priority) cats.add(a.priority)
  }
  return [...cats].sort()
})

const categoryCounts = computed(() => {
  const counts: Record<string, number> = {}
  for (const a of articles.value) {
    if (a.priority) {
      counts[a.priority] = (counts[a.priority] ?? 0) + 1
    }
  }
  return counts
})

const filteredArticles = computed(() => {
  if (!selectedCategory.value) return articles.value
  return articles.value.filter(a => a.priority === selectedCategory.value)
})

async function handleGenerate() {
  await generate()
}

onMounted(() => {
  fetchLatest()
})
</script>
```

- [ ] **Step 2: Verify the dashboard renders**

```bash
cd /mnt/c/Users/mark/source/repos/Briefer/src/frontend
npm run dev
```

Open http://localhost:3000 in a browser. Expected: After redirecting to `/login` and logging in (assuming the ASP.NET API is running), you should see the dashboard with empty state ("No briefing available yet") and the pipeline control buttons. If the API isn't running, you should still see the page structure — the API calls will fail gracefully. Stop the dev server.

- [ ] **Step 3: Commit**

```bash
cd /mnt/c/Users/mark/source/repos/Briefer
git add src/frontend/pages/index.vue
git commit -m "feat(frontend): add briefing dashboard page"
```

---

## Task 8: Profile Management

**Files:**
- Create: `src/frontend/composables/useProfile.ts`
- Create: `src/frontend/components/InterestBlock.vue`
- Create: `src/frontend/pages/profile.vue`

- [ ] **Step 1: Create useProfile composable**

Create `src/frontend/composables/useProfile.ts`:

```ts
import { ref } from 'vue'
import type { Profile, InterestBlock, InterestRequest } from '~/types'

const profile = ref<Profile | null>(null)
const isLoading = ref(false)
const error = ref<string | null>(null)

export function useProfile() {
  const { request } = useApi()
  const { show } = useToast()

  async function fetchProfile() {
    isLoading.value = true
    error.value = null
    const { data, error: err } = await request<Profile>('/profile')
    isLoading.value = false
    if (err) {
      // 404 means no profile yet
      if (err.includes('Not Found') || err.includes('404')) {
        profile.value = { version: 0, interests: [] }
        return
      }
      error.value = err
      return
    }
    profile.value = data
  }

  async function addInterest(title: string, description: string) {
    const body: InterestRequest = { title, description }
    const { data, error: err } = await request<InterestBlock>('/profile/interests', {
      method: 'POST',
      body,
    })
    if (err) {
      show(err, 'error')
      return null
    }
    if (profile.value && data) {
      profile.value.interests.push(data)
    }
    show('Interest added', 'success')
    return data
  }

  async function updateInterest(id: string, title: string, description: string) {
    const body: InterestRequest = { title, description }
    const { data, error: err } = await request<InterestBlock>(`/profile/interests/${id}`, {
      method: 'PUT',
      body,
    })
    if (err) {
      show(err, 'error')
      return
    }
    if (profile.value && data) {
      const idx = profile.value.interests.findIndex(i => i.id === id)
      if (idx >= 0) profile.value.interests[idx] = data
    }
    show('Interest updated', 'success')
  }

  async function deleteInterest(id: string) {
    const { error: err } = await request<void>(`/profile/interests/${id}`, {
      method: 'DELETE',
    })
    if (err) {
      show(err, 'error')
      return
    }
    if (profile.value) {
      profile.value.interests = profile.value.interests.filter(i => i.id !== id)
    }
    show('Interest removed', 'success')
  }

  return { profile, isLoading, error, fetchProfile, addInterest, updateInterest, deleteInterest }
}
```

- [ ] **Step 2: Create InterestBlock component**

Create `src/frontend/components/InterestBlock.vue`:

```vue
<template>
  <div class="bg-surface-card border border-border rounded-xl p-5">
    <!-- View mode -->
    <template v-if="!editing">
      <div class="flex justify-between items-start">
        <div>
          <h3 class="text-sm font-semibold text-text-primary">{{ interest.title }}</h3>
          <p class="text-sm text-text-secondary mt-2 leading-relaxed whitespace-pre-wrap">{{ interest.description }}</p>
        </div>
        <div class="flex gap-2 shrink-0 ml-4">
          <button
            class="text-xs text-text-muted hover:text-primary transition-colors"
            @click="startEdit"
          >
            Edit
          </button>
          <button
            class="text-xs text-text-muted hover:text-danger transition-colors"
            @click="confirmDelete"
          >
            Delete
          </button>
        </div>
      </div>
    </template>

    <!-- Edit mode -->
    <template v-else>
      <div class="space-y-3">
        <input
          v-model="editTitle"
          class="w-full border border-border rounded-lg px-3 py-2 text-sm text-text-primary bg-surface focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary"
          placeholder="Interest label (e.g., Primary Role)"
        />
        <textarea
          v-model="editDescription"
          rows="4"
          class="w-full border border-border rounded-lg px-3 py-2 text-sm text-text-primary bg-surface focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary resize-y"
          placeholder="Describe what you care about and why..."
        />
        <div class="flex gap-2">
          <button
            :disabled="saving"
            class="bg-primary text-white rounded-md px-3.5 py-1.5 text-xs font-medium hover:bg-blue-700 disabled:opacity-50 transition-colors"
            @click="save"
          >
            {{ saving ? 'Saving...' : 'Save' }}
          </button>
          <button
            class="text-xs text-text-muted hover:text-text-secondary transition-colors px-3.5 py-1.5"
            @click="cancelEdit"
          >
            Cancel
          </button>
        </div>
      </div>
    </template>

    <!-- Delete confirmation -->
    <div
      v-if="showDeleteConfirm"
      class="mt-3 p-3 bg-danger-light rounded-lg border border-red-200"
    >
      <p class="text-xs text-danger mb-2">Remove this interest block?</p>
      <div class="flex gap-2">
        <button
          class="bg-danger text-white rounded-md px-3 py-1 text-xs hover:bg-red-700 transition-colors"
          @click="handleDelete"
        >
          Remove
        </button>
        <button
          class="text-xs text-text-muted hover:text-text-secondary transition-colors px-3 py-1"
          @click="showDeleteConfirm = false"
        >
          Cancel
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { InterestBlock } from '~/types'

const props = defineProps<{
  interest: InterestBlock
  isNew?: boolean
}>()

const emit = defineEmits<{
  saved: []
  deleted: []
  cancelled: []
}>()

const { updateInterest, deleteInterest, addInterest } = useProfile()

const editing = ref(props.isNew ?? false)
const saving = ref(false)
const showDeleteConfirm = ref(false)
const editTitle = ref(props.interest.title)
const editDescription = ref(props.interest.description)

function startEdit() {
  editTitle.value = props.interest.title
  editDescription.value = props.interest.description
  editing.value = true
}

function cancelEdit() {
  editing.value = false
  if (props.isNew) emit('cancelled')
}

async function save() {
  if (!editTitle.value.trim() || !editDescription.value.trim()) return
  saving.value = true

  if (props.isNew) {
    const result = await addInterest(editTitle.value.trim(), editDescription.value.trim())
    saving.value = false
    if (result) emit('saved')
  } else {
    await updateInterest(props.interest.id, editTitle.value.trim(), editDescription.value.trim())
    saving.value = false
    editing.value = false
  }
}

function confirmDelete() {
  showDeleteConfirm.value = true
}

async function handleDelete() {
  await deleteInterest(props.interest.id)
  emit('deleted')
}
</script>
```

- [ ] **Step 3: Create profile page**

Create `src/frontend/pages/profile.vue`:

```vue
<template>
  <div class="max-w-2xl">
    <h1 class="text-xl font-bold text-text-primary mb-1">Interest Profile</h1>
    <p class="text-sm text-text-secondary mb-6">
      Describe what you care about in natural language. Each block captures a facet of your work — your role, responsibilities, topics you monitor.
    </p>

    <!-- Loading -->
    <div v-if="isLoading" class="flex justify-center py-12">
      <div class="w-6 h-6 border-2 border-primary border-t-transparent rounded-full animate-spin" />
    </div>

    <!-- Interest blocks -->
    <div v-else class="space-y-4">
      <InterestBlock
        v-for="interest in profile?.interests ?? []"
        :key="interest.id"
        :interest="interest"
        @deleted="fetchProfile"
      />

      <!-- New block being added -->
      <InterestBlock
        v-if="addingNew"
        :interest="emptyInterest"
        :is-new="true"
        @saved="onNewSaved"
        @cancelled="addingNew = false"
      />

      <!-- Empty state -->
      <div
        v-if="!profile?.interests?.length && !addingNew"
        class="bg-surface-card border border-border rounded-xl p-8 text-center"
      >
        <p class="text-text-secondary mb-2">No interests defined yet.</p>
        <p class="text-sm text-text-muted">
          Describe what you care about and why. Each interest block captures a facet of your work.
        </p>
      </div>

      <!-- Add button -->
      <button
        v-if="!addingNew"
        class="w-full border-2 border-dashed border-border rounded-xl py-4 text-sm text-text-muted hover:border-primary hover:text-primary transition-colors"
        @click="addingNew = true"
      >
        + Add Interest
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { InterestBlock } from '~/types'

const { profile, isLoading, fetchProfile } = useProfile()

const addingNew = ref(false)

const emptyInterest: InterestBlock = {
  id: '',
  title: '',
  description: '',
  sortOrder: 0,
}

function onNewSaved() {
  addingNew.value = false
  fetchProfile()
}

onMounted(() => {
  fetchProfile()
})
</script>
```

- [ ] **Step 4: Verify profile page renders**

```bash
cd /mnt/c/Users/mark/source/repos/Briefer/src/frontend
npm run dev
```

Open http://localhost:3000/profile. Expected: The profile page renders with heading, description text, empty state message, and "Add Interest" button. Stop the dev server.

- [ ] **Step 5: Commit**

```bash
cd /mnt/c/Users/mark/source/repos/Briefer
git add src/frontend/composables/useProfile.ts src/frontend/components/InterestBlock.vue src/frontend/pages/profile.vue
git commit -m "feat(frontend): add profile management page with interest blocks"
```

---

## Task 9: Briefing History Page

**Files:**
- Create: `src/frontend/pages/history.vue`

- [ ] **Step 1: Create history page**

Create `src/frontend/pages/history.vue`:

```vue
<template>
  <div class="max-w-3xl">
    <h1 class="text-xl font-bold text-text-primary mb-1">Briefing History</h1>
    <p class="text-sm text-text-secondary mb-6">Past briefings from the last 30 days.</p>

    <!-- Loading -->
    <div v-if="loading" class="flex justify-center py-12">
      <div class="w-6 h-6 border-2 border-primary border-t-transparent rounded-full animate-spin" />
    </div>

    <!-- History list -->
    <div v-else-if="history.length" class="space-y-3">
      <div
        v-for="item in history"
        :key="item.id"
        class="bg-surface-card border border-border rounded-xl overflow-hidden"
      >
        <!-- Summary row (always visible) -->
        <button
          class="w-full px-5 py-4 flex items-center justify-between text-left hover:bg-gray-50 transition-colors"
          @click="toggle(item.id)"
        >
          <div>
            <span class="text-sm font-semibold text-text-primary">
              {{ formatDate(item.created_at ?? item.generated_at) }}
            </span>
            <span class="text-xs text-text-muted ml-3">
              {{ item.article_count }} articles
            </span>
            <span v-if="item.has_summary" class="text-xs text-primary ml-2">
              Has summary
            </span>
          </div>
          <span class="text-text-muted text-sm">{{ expandedId === item.id ? '−' : '+' }}</span>
        </button>

        <!-- Expanded detail -->
        <div v-if="expandedId === item.id" class="border-t border-border px-5 py-4">
          <!-- Loading detail -->
          <div v-if="loadingDetail" class="flex justify-center py-8">
            <div class="w-5 h-5 border-2 border-primary border-t-transparent rounded-full animate-spin" />
          </div>

          <template v-else-if="expandedBriefing">
            <!-- Executive summary -->
            <div v-if="expandedBriefing.executive_summary" class="mb-4">
              <p class="text-xs uppercase tracking-wider text-text-muted mb-2">Executive Summary</p>
              <p class="text-sm leading-7 text-text-secondary">{{ expandedBriefing.executive_summary }}</p>
            </div>

            <!-- Articles -->
            <div class="space-y-3">
              <ArticleCard
                v-for="article in sortedArticles"
                :key="article.article_id"
                :article="article"
              />
            </div>
          </template>
        </div>
      </div>
    </div>

    <!-- Empty state -->
    <div
      v-else
      class="bg-surface-card border border-border rounded-xl p-12 text-center"
    >
      <p class="text-text-secondary mb-2">No briefings yet.</p>
      <p class="text-sm text-text-muted">
        Generate your first briefing from the
        <NuxtLink to="/" class="text-primary hover:underline">dashboard</NuxtLink>.
      </p>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { BriefingHistoryItem, Briefing } from '~/types'

const { request } = useApi()

const history = ref<BriefingHistoryItem[]>([])
const loading = ref(true)
const expandedId = ref<string | null>(null)
const expandedBriefing = ref<Briefing | null>(null)
const loadingDetail = ref(false)
const briefingCache = new Map<string, Briefing>()

async function fetchHistory() {
  loading.value = true
  const { data } = await request<BriefingHistoryItem[]>('/briefing/history')
  loading.value = false
  if (data) history.value = data
}

async function toggle(id: string) {
  if (expandedId.value === id) {
    expandedId.value = null
    expandedBriefing.value = null
    return
  }

  expandedId.value = id
  expandedBriefing.value = null

  if (briefingCache.has(id)) {
    expandedBriefing.value = briefingCache.get(id)!
    return
  }

  loadingDetail.value = true
  const { data } = await request<Briefing>(`/briefing/${id}`)
  loadingDetail.value = false
  if (data) {
    briefingCache.set(id, data)
    expandedBriefing.value = data
  }
}

const sortedArticles = computed(() => {
  if (!expandedBriefing.value) return []
  return [...expandedBriefing.value.articles].sort(
    (a, b) => (b.display_score ?? 0) - (a.display_score ?? 0)
  )
})

function formatDate(dateStr: string | null): string {
  if (!dateStr) return 'Unknown date'
  return new Date(dateStr).toLocaleDateString('en-US', {
    weekday: 'short',
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  })
}

onMounted(() => {
  fetchHistory()
})
</script>
```

- [ ] **Step 2: Verify history page renders**

```bash
cd /mnt/c/Users/mark/source/repos/Briefer/src/frontend
npm run dev
```

Open http://localhost:3000/history. Expected: The history page renders with heading, description, and empty state ("No briefings yet. Generate your first briefing from the dashboard." with a link to `/`). Stop the dev server.

- [ ] **Step 3: Commit**

```bash
cd /mnt/c/Users/mark/source/repos/Briefer
git add src/frontend/pages/history.vue
git commit -m "feat(frontend): add briefing history page with expandable details"
```

---

## Task 10: Final Wiring and Verification

**Files:**
- Modify: `src/frontend/nuxt.config.ts` (if CORS proxy needed)
- No new files — this task verifies everything works together

- [ ] **Step 1: Verify all pages render without errors**

```bash
cd /mnt/c/Users/mark/source/repos/Briefer/src/frontend
npm run dev
```

Check each page in the browser:
- http://localhost:3000/login — Login/register card with tabs
- http://localhost:3000 — Briefing dashboard (redirects to login if not authenticated)
- http://localhost:3000/profile — Interest profile management
- http://localhost:3000/history — Briefing history

Expected: All pages render with correct styling, nav bar shows on all pages except login, active nav link is highlighted. No console errors.

- [ ] **Step 2: Test auth flow (if ASP.NET API is running)**

If the ASP.NET API is running on localhost:5000:
1. Go to `/login`, register a new account
2. Should redirect to `/` after registration
3. Should see the nav bar with your email
4. Navigate to Profile, History — nav highlighting should update
5. Click Logout — should redirect to `/login`
6. Try accessing `/` directly — should redirect to `/login`

If the API is not running, verify that:
1. Login page renders and shows error when submitting ("Service unavailable")
2. Navigating to `/` without a token redirects to `/login`

- [ ] **Step 3: Run type check**

```bash
cd /mnt/c/Users/mark/source/repos/Briefer/src/frontend
npx nuxi typecheck
```

Expected: No type errors. Fix any that appear.

- [ ] **Step 4: Build production bundle**

```bash
cd /mnt/c/Users/mark/source/repos/Briefer/src/frontend
npm run build
```

Expected: Build completes successfully with no errors.

- [ ] **Step 5: Final commit**

```bash
cd /mnt/c/Users/mark/source/repos/Briefer
git add src/frontend/
git commit -m "feat(frontend): complete Vue/Nuxt frontend for Briefer dashboard"
```

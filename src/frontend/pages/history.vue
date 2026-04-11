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
          <span class="text-text-muted text-sm">{{ expandedId === item.id ? '\u2212' : '+' }}</span>
        </button>

        <!-- Expanded detail -->
        <div v-if="expandedId === item.id" class="border-t border-border px-5 py-4">
          <!-- Loading detail -->
          <div v-if="loadingDetail" class="flex justify-center py-8">
            <div class="w-5 h-5 border-2 border-primary border-t-transparent rounded-full animate-spin" />
          </div>

          <p v-else-if="detailError" class="text-sm text-text-muted py-4">
            Could not load briefing details.
          </p>

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
const detailError = ref(false)
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
  detailError.value = false
  const { data } = await request<Briefing>(`/briefing/${id}`)
  loadingDetail.value = false
  if (data) {
    briefingCache.set(id, data)
    expandedBriefing.value = data
  } else {
    detailError.value = true
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

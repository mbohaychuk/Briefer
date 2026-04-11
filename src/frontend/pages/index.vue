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

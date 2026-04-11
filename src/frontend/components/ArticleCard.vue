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

      <!-- Source + rank -->
      <p class="text-xs text-text-muted mt-1.5">
        {{ article.source_name }}<span v-if="article.rank"> &bull; #{{ article.rank }}</span>
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
</script>

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

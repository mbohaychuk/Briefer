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

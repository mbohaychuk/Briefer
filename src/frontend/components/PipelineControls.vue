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

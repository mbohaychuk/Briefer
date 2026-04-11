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

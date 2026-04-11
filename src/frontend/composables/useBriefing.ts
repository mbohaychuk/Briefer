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

  function reset() {
    briefing.value = null
    isLoading.value = false
    isGenerating.value = false
    error.value = null
  }

  return { briefing, isLoading, isGenerating, error, fetchLatest, generate, reset }
}

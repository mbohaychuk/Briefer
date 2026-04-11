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

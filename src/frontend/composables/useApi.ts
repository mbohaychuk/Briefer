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

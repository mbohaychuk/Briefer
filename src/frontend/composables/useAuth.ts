import { useAuthStore } from '~/stores/auth'
import type { AuthResponse } from '~/types'

export function useAuth() {
  const authStore = useAuthStore()
  const { request } = useApi()

  async function login(email: string, password: string): Promise<string | null> {
    const { data, error } = await request<AuthResponse>('/auth/login', {
      method: 'POST',
      body: { email, password },
    })
    if (error) return error
    authStore.setToken(data!.token)
    return null
  }

  async function register(email: string, password: string): Promise<string | null> {
    const { data, error } = await request<AuthResponse>('/auth/register', {
      method: 'POST',
      body: { email, password },
    })
    if (error) return error
    authStore.setToken(data!.token)
    return null
  }

  function logout() {
    useBriefing().reset()
    useProfile().reset()
    usePipeline().reset()
    authStore.logout()
    navigateTo('/login')
  }

  return {
    login,
    register,
    logout,
    get isAuthenticated() { return authStore.isAuthenticated },
    get user() { return authStore.user },
  }
}

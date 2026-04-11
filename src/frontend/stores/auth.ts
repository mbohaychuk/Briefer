import { defineStore } from 'pinia'
import type { User } from '~/types'

function decodeJwtPayload(token: string): Record<string, unknown> | null {
  try {
    const base64 = token.split('.')[1]
    const json = atob(base64.replace(/-/g, '+').replace(/_/g, '/'))
    return JSON.parse(json)
  } catch {
    return null
  }
}

function isTokenExpired(token: string): boolean {
  const payload = decodeJwtPayload(token)
  if (!payload || typeof payload.exp !== 'number') return true
  return Date.now() >= payload.exp * 1000
}

function extractUser(token: string): User | null {
  const payload = decodeJwtPayload(token)
  if (!payload) return null
  const id = (payload.nameid ?? payload.sub ?? '') as string
  const email = (payload.email ?? payload.unique_name ?? '') as string
  if (!id || !email) return null
  return { id, email }
}

export const useAuthStore = defineStore('auth', {
  state: () => ({
    token: null as string | null,
    user: null as User | null,
  }),

  getters: {
    isAuthenticated(): boolean {
      return this.token !== null && !isTokenExpired(this.token)
    },
  },

  actions: {
    setToken(token: string) {
      this.token = token
      this.user = extractUser(token)
      localStorage.setItem('briefer_token', token)
    },

    logout() {
      this.token = null
      this.user = null
      localStorage.removeItem('briefer_token')
    },

    hydrate() {
      const token = localStorage.getItem('briefer_token')
      if (token && !isTokenExpired(token)) {
        this.token = token
        this.user = extractUser(token)
      } else {
        localStorage.removeItem('briefer_token')
      }
    },
  },
})

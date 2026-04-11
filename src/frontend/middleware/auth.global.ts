import { useAuthStore } from '~/stores/auth'

export default defineNuxtRouteMiddleware((to) => {
  const authStore = useAuthStore()

  if (to.path === '/login') {
    if (authStore.isAuthenticated) return navigateTo('/')
    return
  }

  if (!authStore.isAuthenticated) {
    return navigateTo('/login')
  }
})

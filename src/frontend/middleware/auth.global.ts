import { useAuthStore } from '~/stores/auth'

export default defineNuxtRouteMiddleware((to) => {
  const authStore = useAuthStore()

  if (to.path !== '/login') {
    authStore.hydrate()
    if (!authStore.isAuthenticated) {
      return navigateTo('/login')
    }
  }
})

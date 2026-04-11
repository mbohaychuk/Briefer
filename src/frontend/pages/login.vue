<template>
  <div class="min-h-screen bg-surface flex items-center justify-center">
    <div class="bg-surface-card border border-border rounded-xl p-8 w-full max-w-sm shadow-sm">
      <h1 class="text-2xl font-bold text-text-primary mb-6 text-center">Briefer</h1>

      <!-- Tabs -->
      <div class="flex border-b border-border mb-6">
        <button
          class="flex-1 pb-3 text-sm font-semibold"
          :class="tab === 'login' ? 'text-primary border-b-2 border-primary' : 'text-text-muted'"
          @click="tab = 'login'"
        >
          Login
        </button>
        <button
          class="flex-1 pb-3 text-sm font-semibold"
          :class="tab === 'register' ? 'text-primary border-b-2 border-primary' : 'text-text-muted'"
          @click="tab = 'register'"
        >
          Register
        </button>
      </div>

      <!-- Form -->
      <form @submit.prevent="handleSubmit">
        <div class="mb-4">
          <label class="block text-xs font-medium text-text-secondary mb-1.5">Email</label>
          <input
            v-model="email"
            type="email"
            required
            class="w-full border border-border rounded-lg px-3 py-2 text-sm text-text-primary bg-surface-card focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary"
            placeholder="you@example.com"
          />
        </div>
        <div class="mb-6">
          <label class="block text-xs font-medium text-text-secondary mb-1.5">Password</label>
          <input
            v-model="password"
            type="password"
            required
            minlength="8"
            class="w-full border border-border rounded-lg px-3 py-2 text-sm text-text-primary bg-surface-card focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary"
            placeholder="Min 8 characters"
          />
        </div>

        <p v-if="error" class="text-danger text-xs mb-4">{{ error }}</p>

        <button
          type="submit"
          :disabled="loading"
          class="w-full bg-primary text-white rounded-lg py-2.5 text-sm font-medium hover:bg-blue-700 disabled:opacity-50 transition-colors"
        >
          <span v-if="loading">{{ tab === 'login' ? 'Signing in...' : 'Creating account...' }}</span>
          <span v-else>{{ tab === 'login' ? 'Sign In' : 'Create Account' }}</span>
        </button>
      </form>
    </div>
  </div>
</template>

<script setup lang="ts">
definePageMeta({ layout: false })

const { login, register } = useAuth()

const tab = ref<'login' | 'register'>('login')
const email = ref('')
const password = ref('')
const error = ref<string | null>(null)
const loading = ref(false)

async function handleSubmit() {
  error.value = null
  loading.value = true

  const result = tab.value === 'login'
    ? await login(email.value, password.value)
    : await register(email.value, password.value)

  loading.value = false

  if (result) {
    error.value = result
  } else {
    navigateTo('/')
  }
}
</script>

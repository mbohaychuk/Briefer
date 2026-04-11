<template>
  <nav class="bg-surface-card border-b border-border px-8 py-3 flex justify-between items-center">
    <span class="text-text-primary text-lg font-bold tracking-tight">Briefer</span>
    <div class="flex items-center gap-7 text-sm">
      <NuxtLink
        to="/"
        class="font-semibold"
        :class="route.path === '/' ? 'text-text-primary border-b-2 border-primary pb-2.5 -mb-3.5' : 'text-text-secondary hover:text-text-primary'"
      >
        Briefing
      </NuxtLink>
      <NuxtLink
        to="/profile"
        class="font-semibold"
        :class="route.path === '/profile' ? 'text-text-primary border-b-2 border-primary pb-2.5 -mb-3.5' : 'text-text-secondary hover:text-text-primary'"
      >
        Profile
      </NuxtLink>
      <NuxtLink
        to="/history"
        class="font-semibold"
        :class="route.path === '/history' ? 'text-text-primary border-b-2 border-primary pb-2.5 -mb-3.5' : 'text-text-secondary hover:text-text-primary'"
      >
        History
      </NuxtLink>
      <span class="text-text-muted">{{ user?.email }}</span>
      <button
        class="text-text-secondary hover:text-text-primary text-sm"
        @click="logout"
      >
        Logout
      </button>
    </div>
  </nav>
</template>

<script setup lang="ts">
const route = useRoute()
const { user, logout } = useAuth()
</script>

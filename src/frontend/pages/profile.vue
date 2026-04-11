<template>
  <div class="max-w-2xl">
    <h1 class="text-xl font-bold text-text-primary mb-1">Interest Profile</h1>
    <p class="text-sm text-text-secondary mb-6">
      Describe what you care about in natural language. Each block captures a facet of your work — your role, responsibilities, topics you monitor.
    </p>

    <!-- Loading -->
    <div v-if="isLoading" class="flex justify-center py-12">
      <div class="w-6 h-6 border-2 border-primary border-t-transparent rounded-full animate-spin" />
    </div>

    <!-- Interest blocks -->
    <div v-else class="space-y-4">
      <InterestBlock
        v-for="interest in profile?.interests ?? []"
        :key="interest.id"
        :interest="interest"
        @deleted="fetchProfile"
      />

      <!-- New block being added -->
      <InterestBlock
        v-if="addingNew"
        :interest="emptyInterest"
        :is-new="true"
        @saved="onNewSaved"
        @cancelled="addingNew = false"
      />

      <!-- Empty state -->
      <div
        v-if="!profile?.interests?.length && !addingNew"
        class="bg-surface-card border border-border rounded-xl p-8 text-center"
      >
        <p class="text-text-secondary mb-2">No interests defined yet.</p>
        <p class="text-sm text-text-muted">
          Describe what you care about and why. Each interest block captures a facet of your work.
        </p>
      </div>

      <!-- Add button -->
      <button
        v-if="!addingNew"
        class="w-full border-2 border-dashed border-border rounded-xl py-4 text-sm text-text-muted hover:border-primary hover:text-primary transition-colors"
        @click="addingNew = true"
      >
        + Add Interest
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { InterestBlock } from '~/types'

const { profile, isLoading, fetchProfile } = useProfile()

const addingNew = ref(false)

const emptyInterest: InterestBlock = {
  id: '',
  title: '',
  description: '',
  sortOrder: 0,
}

function onNewSaved() {
  addingNew.value = false
  fetchProfile()
}

onMounted(() => {
  fetchProfile()
})
</script>

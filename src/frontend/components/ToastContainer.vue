<template>
  <div class="fixed bottom-6 right-6 z-50 flex flex-col gap-3 w-80">
    <TransitionGroup name="toast">
      <div
        v-for="toast in toasts"
        :key="toast.id"
        class="rounded-lg px-4 py-3 shadow-lg border flex items-start justify-between gap-3 text-sm"
        :class="colorClasses[toast.type]"
      >
        <span>{{ toast.message }}</span>
        <button
          class="opacity-60 hover:opacity-100 shrink-0"
          @click="dismiss(toast.id)"
        >
          &times;
        </button>
      </div>
    </TransitionGroup>
  </div>
</template>

<script setup lang="ts">
const { toasts, dismiss } = useToast()

const colorClasses: Record<string, string> = {
  success: 'bg-green-50 border-green-200 text-green-800',
  error: 'bg-danger-light border-red-200 text-danger',
  info: 'bg-primary-light border-blue-200 text-primary',
}
</script>

<style scoped>
.toast-enter-active,
.toast-leave-active {
  transition: all 0.3s ease;
}
.toast-enter-from {
  opacity: 0;
  transform: translateX(40px);
}
.toast-leave-to {
  opacity: 0;
  transform: translateX(40px);
}
</style>

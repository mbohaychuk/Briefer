<template>
  <div class="bg-surface-card border border-border rounded-xl p-5">
    <!-- View mode -->
    <template v-if="!editing">
      <div class="flex justify-between items-start">
        <div>
          <h3 class="text-sm font-semibold text-text-primary">{{ interest.title }}</h3>
          <p class="text-sm text-text-secondary mt-2 leading-relaxed whitespace-pre-wrap">{{ interest.description }}</p>
        </div>
        <div class="flex gap-2 shrink-0 ml-4">
          <button
            class="text-xs text-text-muted hover:text-primary transition-colors"
            @click="startEdit"
          >
            Edit
          </button>
          <button
            class="text-xs text-text-muted hover:text-danger transition-colors"
            @click="confirmDelete"
          >
            Delete
          </button>
        </div>
      </div>
    </template>

    <!-- Edit mode -->
    <template v-else>
      <div class="space-y-3">
        <input
          v-model="editTitle"
          class="w-full border border-border rounded-lg px-3 py-2 text-sm text-text-primary bg-surface focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary"
          placeholder="Interest label (e.g., Primary Role)"
        />
        <textarea
          v-model="editDescription"
          rows="4"
          class="w-full border border-border rounded-lg px-3 py-2 text-sm text-text-primary bg-surface focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary resize-y"
          placeholder="Describe what you care about and why..."
        />
        <div class="flex gap-2">
          <button
            :disabled="saving"
            class="bg-primary text-white rounded-md px-3.5 py-1.5 text-xs font-medium hover:bg-blue-700 disabled:opacity-50 transition-colors"
            @click="save"
          >
            {{ saving ? 'Saving...' : 'Save' }}
          </button>
          <button
            class="text-xs text-text-muted hover:text-text-secondary transition-colors px-3.5 py-1.5"
            @click="cancelEdit"
          >
            Cancel
          </button>
        </div>
      </div>
    </template>

    <!-- Delete confirmation -->
    <div
      v-if="showDeleteConfirm"
      class="mt-3 p-3 bg-danger-light rounded-lg border border-red-200"
    >
      <p class="text-xs text-danger mb-2">Remove this interest block?</p>
      <div class="flex gap-2">
        <button
          class="bg-danger text-white rounded-md px-3 py-1 text-xs hover:bg-red-700 transition-colors"
          @click="handleDelete"
        >
          Remove
        </button>
        <button
          class="text-xs text-text-muted hover:text-text-secondary transition-colors px-3 py-1"
          @click="showDeleteConfirm = false"
        >
          Cancel
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { InterestBlock } from '~/types'

const props = defineProps<{
  interest: InterestBlock
  isNew?: boolean
}>()

const emit = defineEmits<{
  saved: []
  deleted: []
  cancelled: []
}>()

const { updateInterest, deleteInterest, addInterest } = useProfile()

const editing = ref(props.isNew ?? false)
const saving = ref(false)
const showDeleteConfirm = ref(false)
const editTitle = ref(props.interest.title)
const editDescription = ref(props.interest.description)

function startEdit() {
  editTitle.value = props.interest.title
  editDescription.value = props.interest.description
  editing.value = true
}

function cancelEdit() {
  editing.value = false
  if (props.isNew) emit('cancelled')
}

async function save() {
  if (!editTitle.value.trim() || !editDescription.value.trim()) return
  saving.value = true

  if (props.isNew) {
    const result = await addInterest(editTitle.value.trim(), editDescription.value.trim())
    saving.value = false
    if (result) emit('saved')
  } else {
    await updateInterest(props.interest.id, editTitle.value.trim(), editDescription.value.trim())
    saving.value = false
    editing.value = false
  }
}

function confirmDelete() {
  showDeleteConfirm.value = true
}

async function handleDelete() {
  await deleteInterest(props.interest.id)
  emit('deleted')
}
</script>

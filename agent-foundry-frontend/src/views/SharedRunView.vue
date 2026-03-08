<template>
  <div class="shared-run">
    <v-card v-if="run" class="pa-4">
      <v-card-title class="d-flex align-center gap-2">
        <span>Shared run – {{ run.chain_id ? 'AI Team #' + run.chain_id : 'Run' }}</span>
        <v-chip size="small" :color="statusColor(run.status)">{{ run.status }}</v-chip>
      </v-card-title>
      <v-divider class="my-3" />
      <p v-if="run.created_at" class="text-caption text-medium-emphasis mb-2">
        Run at {{ formatDate(run.created_at) }}
      </p>
      <FormattedOutput :content="run.content || run.error || run.summary" fallback="No output" class="shared-run-content" />
      <p v-if="expired" class="text-caption text-error mt-2">This link has expired.</p>
    </v-card>
    <v-card v-else-if="error" class="pa-4">
      <v-card-title>Link not found or expired</v-card-title>
      <p class="text-body-2">This shared run link is invalid or has expired.</p>
    </v-card>
    <v-progress-linear v-else indeterminate class="mb-4" />
  </div>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'
import { useRoute } from 'vue-router'
import api from '@/services/api'
import FormattedOutput from '@/components/FormattedOutput.vue'

const route = useRoute()
const run = ref(null)
const error = ref(false)
const expired = ref(false)

const token = computed(() => route.params.token)

function statusColor(status) {
  if (status === 'awaiting_approval') return 'warning'
  if (status === 'completed') return 'success'
  if (status === 'error') return 'error'
  return 'default'
}

function formatDate(iso) {
  if (!iso) return ''
  try {
    return new Date(iso).toLocaleString()
  } catch {
    return iso
  }
}

onMounted(async () => {
  if (!token.value) {
    error.value = true
    return
  }
  try {
    const { data } = await api.get(`/share/run/${token.value}`)
    run.value = data
  } catch (e) {
    if (e.response?.status === 404) {
      expired.value = e.response?.data?.detail?.includes?.('expired') ?? false
    }
    error.value = true
  }
})
</script>

<style scoped>
.shared-run-content {
  white-space: pre-wrap;
  word-break: break-word;
  max-height: 70vh;
  overflow-y: auto;
  font-size: 0.875rem;
  margin: 0;
  padding: 0.5rem 0;
}
</style>

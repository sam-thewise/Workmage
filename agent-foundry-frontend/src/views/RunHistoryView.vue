<template>
  <div class="run-history">
    <h1 class="text-h4 mb-4">Run history</h1>
    <p class="text-body-2 text-medium-emphasis mb-4">View results from your chain runs and respond to pending approvals.</p>
    <v-table v-if="runs.length">
      <thead>
        <tr>
          <th>Chain</th>
          <th>Status</th>
          <th>Date</th>
          <th></th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="r in runs" :key="r.id">
          <td>{{ r.chain_name || 'Chain #' + r.chain_id }}</td>
          <td>
            <v-chip :color="statusColor(r.status)" size="small">{{ r.status }}</v-chip>
          </td>
          <td>{{ formatDate(r.created_at) }}</td>
          <td>
            <v-btn size="small" variant="tonal" @click="openRun(r.id)">View</v-btn>
          </td>
        </tr>
      </tbody>
    </v-table>
    <p v-else-if="!loading" class="text-medium-emphasis">No runs yet. Run a chain from My Chains to see results here.</p>
    <p v-else class="text-medium-emphasis">Loading…</p>

    <v-dialog v-model="showDetail" max-width="560" class="run-history-dialog" @update:model-value="onDialogChange">
      <v-card v-if="selectedRun" class="pa-4 run-history-dialog-card">
        <v-card-title class="d-flex align-center justify-space-between">
          <span>{{ selectedRun.chain_name }} – {{ selectedRun.status }}</span>
          <v-btn icon variant="text" aria-label="Close" @click="closeDetail">
            <v-icon>mdi-close</v-icon>
          </v-btn>
        </v-card-title>
        <v-divider />
        <template v-if="selectedRun.status === 'awaiting_approval'">
          <p class="text-body-2 mb-2">Review the result below, then approve to continue or reject.</p>
          <pre class="detail-pre">{{ selectedRun.summary || 'No summary' }}</pre>
          <p v-if="selectedRun.next_stages?.length" class="text-caption mb-2">Next: {{ selectedRun.next_stages.map(s => s.label).join(', ') }}</p>
          <div class="d-flex gap-2 mt-3">
            <v-btn color="primary" :loading="approving" @click="approveSelected(true)">Approve & continue</v-btn>
            <v-btn variant="outlined" :loading="approving" @click="approveSelected(false)">Reject</v-btn>
          </div>
        </template>
        <template v-else>
          <pre class="detail-pre">{{ selectedRun.content || selectedRun.error || 'No output' }}</pre>
          <p v-if="selectedRun.usage" class="text-caption mt-2">Usage: {{ selectedRun.usage.prompt_tokens ?? 0 }} prompt, {{ selectedRun.usage.completion_tokens ?? 0 }} completion</p>
        </template>
      </v-card>
    </v-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import api from '@/services/api'

const route = useRoute()
const router = useRouter()
const runs = ref([])
const loading = ref(true)
const showDetail = ref(false)
const selectedRun = ref(null)
const approving = ref(false)

function statusColor(status) {
  if (status === 'awaiting_approval') return 'warning'
  if (status === 'completed') return 'success'
  if (status === 'error') return 'error'
  return 'default'
}

function formatDate(iso) {
  if (!iso) return ''
  try {
    const d = new Date(iso)
    return d.toLocaleString()
  } catch {
    return iso
  }
}

async function loadRuns() {
  loading.value = true
  try {
    const { data } = await api.get('/chains/runs', { params: { limit: 100 } })
    runs.value = data.items || []
  } catch {
    runs.value = []
  } finally {
    loading.value = false
  }
}

function closeDetail() {
  showDetail.value = false
  selectedRun.value = null
  if (route.query.open) {
    router.replace({ path: route.path, query: {} })
  }
}

function onDialogChange(isOpen) {
  if (!isOpen) {
    selectedRun.value = null
    if (route.query.open) {
      router.replace({ path: route.path, query: {} })
    }
  }
}

async function openRun(runId) {
  try {
    const { data } = await api.get(`/chains/runs/result/${runId}`)
    selectedRun.value = data
    showDetail.value = true
    await api.patch(`/chains/runs/${runId}/read`)
  } catch {
    selectedRun.value = null
  }
}

async function approveSelected(approved) {
  if (!selectedRun.value?.approval_id) return
  approving.value = true
  try {
    await api.post(`/chains/approvals/${selectedRun.value.approval_id}/approve`, { approved, next_stage_node_id: null })
    if (approved) {
      closeDetail()
      await loadRuns()
    } else {
      selectedRun.value = { ...selectedRun.value, status: 'rejected' }
      await loadRuns()
    }
  } finally {
    approving.value = false
  }
}

onMounted(() => {
  loadRuns()
  const openId = route.query.open
  if (openId) {
    openRun(Number(openId))
  }
})

watch(() => route.query.open, (openId) => {
  if (openId && !showDetail.value) {
    openRun(Number(openId))
  }
})
</script>

<style scoped>
.run-history-dialog-card {
  background: rgb(var(--v-theme-surface)) !important;
  border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
}
.detail-pre {
  white-space: pre-wrap;
  word-break: break-word;
  max-height: 360px;
  overflow-y: auto;
  font-size: 0.875rem;
  margin: 0;
}
</style>
<style>
.run-history-dialog.v-dialog .v-overlay__scrim {
  opacity: 1;
  background: rgba(0, 0, 0, 0.6) !important;
}
</style>

<template>
  <div class="run-history">
    <h1 class="text-h4 mb-4">Run history</h1>
    <p class="text-body-2 text-medium-emphasis mb-4">View results from your AI team runs and respond to pending approvals.</p>
    <v-table v-if="runs.length">
      <thead>
        <tr>
          <th>AI Team</th>
          <th>Status</th>
          <th>Date</th>
          <th></th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="r in runs" :key="r.id">
          <td>{{ r.chain_name || 'AI Team #' + r.chain_id }}</td>
          <td>
            <v-chip :color="statusColor(r.status)" size="small">{{ r.status }}</v-chip>
          </td>
          <td>{{ formatDate(r.created_at) }}</td>
          <td>
            <v-btn size="small" variant="tonal" @click="openRun(r.id, 'audit')">Audit</v-btn>
            <v-btn size="small" variant="tonal" class="ms-1" @click="openRun(r.id, 'view')">View</v-btn>
            <v-btn size="small" variant="tonal" class="ms-1" :loading="sharingRunId === r.id" @click="shareRun(r.id)">Share</v-btn>
          </td>
        </tr>
      </tbody>
    </v-table>
    <p v-else-if="!loading" class="text-medium-emphasis">No runs yet. Run an AI team from My AI Teams to see results here.</p>
    <p v-else class="text-medium-emphasis">Loading…</p>

    <v-dialog v-model="showShareDialog" max-width="480" persistent>
      <v-card v-if="shareLink" class="pa-4">
        <v-card-title>Share run output</v-card-title>
        <v-divider class="my-2" />
        <p class="text-body-2 text-medium-emphasis">Anyone with this link can view the run output.</p>
        <v-text-field
          :model-value="shareLinkFullUrl"
          readonly
          density="compact"
          hide-details
          class="mt-2"
        />
        <div class="d-flex gap-2 mt-3">
          <v-btn color="primary" @click="copyShareLink">Copy link</v-btn>
          <v-btn variant="text" @click="showShareDialog = false">Close</v-btn>
        </div>
      </v-card>
    </v-dialog>
    <v-dialog v-model="showDetail" :max-width="detailMode === 'view' ? 720 : 560" class="run-history-dialog" @update:model-value="onDialogChange">
      <v-card v-if="selectedRun" class="pa-4 run-history-dialog-card">
        <v-card-title class="d-flex align-center justify-space-between">
          <span>{{ selectedRun.chain_name }} – {{ selectedRun.status }} ({{ detailMode === 'audit' ? 'Audit' : 'Full result' }})</span>
          <v-btn icon variant="text" aria-label="Close" @click="closeDetail">
            <v-icon>mdi-close</v-icon>
          </v-btn>
        </v-card-title>
        <v-divider />
        <!-- Audit mode: audit trail first, then result snippet/approval -->
        <template v-if="detailMode === 'audit'">
          <section v-if="selectedRun.audit_trail?.length" class="audit-trail mb-4">
            <h3 class="text-subtitle-2 text-medium-emphasis mb-2">Audit trail</h3>
            <p class="text-caption text-medium-emphasis mb-2">Step-by-step summary of this run (for reviewing AI role performance).</p>
            <div class="audit-steps">
              <div
                v-for="(step, i) in selectedRun.audit_trail"
                :key="i"
                class="audit-step"
                :class="step.status"
              >
                <div class="audit-step-header">
                  <span class="audit-step-index">{{ i + 1 }}</span>
                  <span class="audit-step-label">{{ step.label }}</span>
                  <v-chip size="x-small" :color="auditStatusColor(step.status)" class="audit-step-type">{{ step.type }}</v-chip>
                  <v-chip size="x-small" :color="auditStatusColor(step.status)" variant="tonal">{{ step.status }}</v-chip>
                  <span v-if="step.duration_ms != null" class="text-caption ms-1">{{ step.duration_ms }}ms</span>
                </div>
                <div v-if="step.output_preview" class="audit-step-preview text-caption">{{ step.output_preview }}</div>
                <div v-if="step.usage && (step.usage.prompt_tokens || step.usage.completion_tokens)" class="text-caption text-medium-emphasis">
                  Tokens: {{ step.usage.prompt_tokens ?? 0 }} prompt, {{ step.usage.completion_tokens ?? 0 }} completion
                </div>
              </div>
            </div>
          </section>
          <v-divider v-if="selectedRun.audit_trail?.length" class="mb-3" />
        </template>
        <!-- View mode: full result first; audit trail in expandable section -->
        <template v-if="detailMode === 'view'">
          <template v-if="selectedRun.status === 'awaiting_approval'">
            <p class="text-body-2 mb-2">Review the result below, then approve to continue or reject.</p>
            <pre class="detail-pre detail-pre-full">{{ selectedRun.summary || 'No summary' }}</pre>
            <p v-if="selectedRun.next_stages?.length" class="text-caption mb-2">Next: {{ selectedRun.next_stages.map(s => s.label).join(', ') }}</p>
            <div class="d-flex gap-2 mt-3">
              <v-btn color="primary" :loading="approving" @click="approveSelected(true)">Approve & continue</v-btn>
              <v-btn variant="outlined" :loading="approving" @click="approveSelected(false)">Reject</v-btn>
            </div>
          </template>
          <template v-else>
            <pre class="detail-pre detail-pre-full">{{ selectedRun.content || selectedRun.error || 'No output' }}</pre>
            <p v-if="selectedRun.usage" class="text-caption mt-2">Usage: {{ selectedRun.usage.prompt_tokens ?? 0 }} prompt, {{ selectedRun.usage.completion_tokens ?? 0 }} completion</p>
          </template>
          <v-expansion-panels v-if="selectedRun.audit_trail?.length" class="mt-4" variant="accordion">
            <v-expansion-panel>
              <v-expansion-panel-title>Audit trail</v-expansion-panel-title>
              <v-expansion-panel-text>
                <div class="audit-steps">
                  <div
                    v-for="(step, i) in selectedRun.audit_trail"
                    :key="i"
                    class="audit-step"
                    :class="step.status"
                  >
                    <div class="audit-step-header">
                      <span class="audit-step-index">{{ i + 1 }}</span>
                      <span class="audit-step-label">{{ step.label }}</span>
                      <v-chip size="x-small" :color="auditStatusColor(step.status)">{{ step.type }}</v-chip>
                      <v-chip size="x-small" :color="auditStatusColor(step.status)" variant="tonal">{{ step.status }}</v-chip>
                      <span v-if="step.duration_ms != null" class="text-caption ms-1">{{ step.duration_ms }}ms</span>
                    </div>
                    <div v-if="step.output_preview" class="audit-step-preview text-caption">{{ step.output_preview }}</div>
                    <div v-if="step.usage && (step.usage.prompt_tokens || step.usage.completion_tokens)" class="text-caption text-medium-emphasis">
                      Tokens: {{ step.usage.prompt_tokens ?? 0 }} prompt, {{ step.usage.completion_tokens ?? 0 }} completion
                    </div>
                  </div>
                </div>
              </v-expansion-panel-text>
            </v-expansion-panel>
          </v-expansion-panels>
        </template>
        <!-- Audit mode: result/approval block below audit trail -->
        <template v-else>
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
        </template>
      </v-card>
    </v-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted, watch, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import api from '@/services/api'
import { useWorkspaceStore } from '@/stores/workspace'

const route = useRoute()
const router = useRouter()
const workspaceStore = useWorkspaceStore()
const workspaceId = computed(() => route.query.workspace_id ? Number(route.query.workspace_id) : workspaceStore.currentWorkspaceId)
const runs = ref([])
const loading = ref(true)
const showDetail = ref(false)
const selectedRun = ref(null)
const detailMode = ref('audit') // 'audit' | 'view'
const approving = ref(false)
const sharingRunId = ref(null)
const showShareDialog = ref(false)
const shareLink = ref(null)
const shareLinkFullUrl = ref('')

function statusColor(status) {
  if (status === 'awaiting_approval') return 'warning'
  if (status === 'completed') return 'success'
  if (status === 'error') return 'error'
  return 'default'
}

function auditStatusColor(status) {
  if (status === 'ok' || status === 'reached') return 'success'
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
    const params = { limit: 100 }
    if (workspaceId.value) params.workspace_id = workspaceId.value
    const { data } = await api.get('/chains/runs', { params })
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
  detailMode.value = 'audit'
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

async function openRun(runId, mode = 'audit') {
  try {
    const { data } = await api.get(`/chains/runs/result/${runId}`)
    selectedRun.value = data
    detailMode.value = mode
    showDetail.value = true
    await api.patch(`/chains/runs/${runId}/read`)
  } catch {
    selectedRun.value = null
  }
}

async function shareRun(runId) {
  sharingRunId.value = runId
  shareLink.value = null
  try {
    const { data } = await api.post(`/chains/runs/${runId}/share`, { expires_in_seconds: 604800 })
    shareLink.value = data
    shareLinkFullUrl.value = data.url
      ? (window.location.origin + (data.url.startsWith('/') ? data.url : '/' + data.url))
      : (window.location.origin + '/share/run/' + data.token)
    showShareDialog.value = true
  } catch {
    shareLink.value = null
  } finally {
    sharingRunId.value = null
  }
}

function copyShareLink() {
  if (!shareLinkFullUrl.value) return
  navigator.clipboard.writeText(shareLinkFullUrl.value).then(() => {
    // Could show snackbar: "Link copied"
  })
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
    openRun(Number(openId), 'view')
  }
})

watch(() => route.query.open, (openId) => {
  if (openId && !showDetail.value) {
    openRun(Number(openId), 'view')
  }
})
watch(workspaceId, () => {
  loadRuns()
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
.detail-pre-full {
  max-height: 70vh;
  min-height: 200px;
}
.audit-trail {
  text-align: left;
}
.audit-steps {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}
.audit-step {
  padding: 0.5rem 0.75rem;
  border-radius: 6px;
  border-left: 3px solid rgba(var(--v-border-color), 0.5);
  background: rgba(var(--v-theme-surface-variant), 0.3);
}
.audit-step.error {
  border-left-color: rgb(var(--v-theme-error));
  background: rgba(var(--v-theme-error), 0.08);
}
.audit-step-header {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.35rem;
}
.audit-step-index {
  font-weight: 600;
  min-width: 1.25rem;
}
.audit-step-label {
  font-weight: 500;
  flex: 1;
  min-width: 0;
}
.audit-step-preview {
  margin-top: 0.25rem;
  white-space: pre-wrap;
  word-break: break-word;
  max-height: 120px;
  overflow-y: auto;
  opacity: 0.9;
}
</style>
<style>
.run-history-dialog.v-dialog .v-overlay__scrim {
  opacity: 1;
  background: rgba(0, 0, 0, 0.6) !important;
}
</style>

<template>
  <div class="content-drafts mx-auto mt-4" style="max-width: 900px;">
    <h2 class="text-h5 mb-2">Content drafts</h2>
    <p class="text-body-2 text-medium-emphasis mb-4">
      Review, edit, and approve draft posts and replies from your X authority workflow. Approved drafts are ready to copy and post on X.
    </p>

    <div class="d-flex flex-wrap gap-2 mb-4">
      <v-select
        v-model="filterStatus"
        :items="statusOptions"
        item-title="title"
        item-value="value"
        label="Status"
        density="compact"
        hide-details
        style="max-width: 160px;"
        @update:model-value="fetchDrafts"
      />
      <v-select
        v-model="filterType"
        :items="typeOptions"
        item-title="title"
        item-value="value"
        label="Type"
        density="compact"
        hide-details
        style="max-width: 120px;"
        @update:model-value="fetchDrafts"
      />
      <v-btn variant="tonal" size="small" @click="fetchDrafts">Refresh</v-btn>
    </div>

    <v-progress-linear v-if="loading" indeterminate class="mb-4" />

    <v-card v-if="drafts.length === 0 && !loading" variant="tonal" class="pa-4">
      <p class="text-body-2 mb-0">No drafts yet. Run the X Content Writer chain and create drafts from the output, or add drafts manually via the API.</p>
    </v-card>

    <v-card v-else-if="drafts.length" variant="outlined" class="mb-4">
      <v-list lines="two">
        <v-list-item
          v-for="d in drafts"
          :key="d.id"
          class="text-left"
          :class="{ 'bg-success-container': d.status === 'approved' }"
        >
          <template #prepend>
            <v-chip size="small" :color="d.type === 'reply' ? 'secondary' : 'primary'" class="mr-2">
              {{ d.type }}
            </v-chip>
            <v-chip size="x-small" variant="flat" class="mr-2">{{ d.status }}</v-chip>
          </template>
          <v-list-item-title class="text-wrap">
            {{ bodyPreview(d.body) }}
          </v-list-item-title>
          <v-list-item-subtitle v-if="d.target_handle">
            Reply to @{{ d.target_handle }}
          </v-list-item-subtitle>
          <template #append>
            <div class="d-flex flex-column gap-1">
              <v-btn
                v-if="d.status === 'draft' || d.status === 'pending_approval'"
                size="small"
                variant="text"
                @click="openEdit(d)"
              >
                Edit
              </v-btn>
              <v-btn
                v-if="d.status === 'draft' || d.status === 'pending_approval'"
                size="small"
                variant="text"
                color="success"
                @click="approve(d.id)"
              >
                Approve
              </v-btn>
              <v-btn
                v-if="d.status === 'draft' || d.status === 'pending_approval'"
                size="small"
                variant="text"
                color="error"
                @click="reject(d.id)"
              >
                Reject
              </v-btn>
              <v-btn
                size="small"
                variant="text"
                @click="copyBody(d.body)"
              >
                Copy
              </v-btn>
            </div>
          </template>
        </v-list-item>
      </v-list>
    </v-card>

    <v-dialog v-model="showEdit" max-width="560" persistent>
      <v-card class="pa-4">
        <h3 class="text-h6 mb-3">Edit draft</h3>
        <v-textarea
          v-model="editBody"
          label="Content"
          rows="6"
          density="compact"
          hide-details
          class="mb-3"
        />
        <div class="d-flex gap-2 justify-end">
          <v-btn variant="text" @click="showEdit = false">Cancel</v-btn>
          <v-btn color="primary" :loading="saving" :disabled="!editBody.trim()" @click="saveEdit">
            Save
          </v-btn>
        </div>
      </v-card>
    </v-dialog>

    <v-snackbar v-model="snackbar" :timeout="2500" color="success">
      {{ snackbarText }}
    </v-snackbar>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import api from '@/services/api'

const loading = ref(false)
const saving = ref(false)
const drafts = ref([])
const filterStatus = ref(null)
const filterType = ref(null)
const showEdit = ref(false)
const editingId = ref(null)
const editBody = ref('')
const snackbar = ref(false)
const snackbarText = ref('')

const statusOptions = [
  { title: 'All', value: null },
  { title: 'Draft', value: 'draft' },
  { title: 'Pending approval', value: 'pending_approval' },
  { title: 'Approved', value: 'approved' },
  { title: 'Rejected', value: 'rejected' }
]
const typeOptions = [
  { title: 'All', value: null },
  { title: 'Post', value: 'post' },
  { title: 'Reply', value: 'reply' }
]

function bodyPreview(body, maxLen = 120) {
  if (!body || typeof body !== 'string') return '—'
  return body.length <= maxLen ? body : body.slice(0, maxLen) + '…'
}

async function fetchDrafts() {
  loading.value = true
  try {
    const params = {}
    if (filterStatus.value) params.status = filterStatus.value
    if (filterType.value) params.type = filterType.value
    const { data } = await api.get('/content-drafts', { params })
    drafts.value = data
  } catch (e) {
    drafts.value = []
    snackbarText.value = e.response?.data?.detail || 'Failed to load drafts'
    snackbar.value = true
  } finally {
    loading.value = false
  }
}

function openEdit(d) {
  editingId.value = d.id
  editBody.value = d.body
  showEdit.value = true
}

async function saveEdit() {
  if (!editingId.value || !editBody.value.trim()) return
  saving.value = true
  try {
    await api.patch(`/content-drafts/${editingId.value}`, { body: editBody.value.trim() })
    showEdit.value = false
    editingId.value = null
    snackbarText.value = 'Draft updated'
    snackbar.value = true
    fetchDrafts()
  } catch (e) {
    snackbarText.value = e.response?.data?.detail || 'Failed to update'
    snackbar.value = true
  } finally {
    saving.value = false
  }
}

async function approve(id) {
  try {
    await api.post(`/content-drafts/${id}/approve`)
    snackbarText.value = 'Draft approved'
    snackbar.value = true
    fetchDrafts()
  } catch (e) {
    snackbarText.value = e.response?.data?.detail || 'Failed to approve'
    snackbar.value = true
  }
}

async function reject(id) {
  try {
    await api.post(`/content-drafts/${id}/reject`)
    snackbarText.value = 'Draft rejected'
    snackbar.value = true
    fetchDrafts()
  } catch (e) {
    snackbarText.value = e.response?.data?.detail || 'Failed to reject'
    snackbar.value = true
  }
}

function copyBody(body) {
  if (!body) return
  navigator.clipboard.writeText(body).then(() => {
    snackbarText.value = 'Copied to clipboard'
    snackbar.value = true
  }).catch(() => {
    snackbarText.value = 'Copy failed'
    snackbar.value = true
  })
}

onMounted(() => {
  fetchDrafts()
})
</script>

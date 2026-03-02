<template>
  <div class="agent-management mx-auto" style="max-width: 800px;">
    <h1 class="text-h4 mb-2">My Agents</h1>
    <p v-if="authStore.user?.role !== 'expert' && authStore.user?.role !== 'admin'" class="mb-4">Experts and admins can create and manage agents here.</p>
    <template v-else>
      <div class="d-flex gap-2 mb-4">
        <v-btn color="primary" to="/dashboard/agents/create">Create Agent</v-btn>
        <v-btn variant="outlined" color="primary" to="/dashboard/settings">Stripe & Settings</v-btn>
      </div>
      <div v-if="loading" class="text-medium-emphasis mb-4">Loading...</div>
      <div v-else class="d-flex flex-column gap-2">
        <v-card v-for="a in agents" :key="a.id" variant="tonal" class="pa-4">
          <div class="d-flex justify-space-between align-start flex-wrap gap-2">
            <div class="flex-grow-1">
              <span class="font-weight-bold mr-2">{{ a.name }}</span>
              <v-chip :color="statusColor(a.status)" size="x-small" class="mr-2">{{ a.status }}</v-chip>
              <p v-if="a.description" class="text-body-2 text-medium-emphasis mt-1 mb-0">{{ a.description }}</p>
              <p v-if="a.status === 'rejected' && a.rejection_reason" class="text-error text-caption mt-1 mb-0">{{ a.rejection_reason }}</p>
            </div>
            <div class="d-flex gap-2">
              <v-btn size="small" variant="text" :to="`/dashboard/agents/${a.id}/edit`">Edit</v-btn>
              <v-btn
                v-if="a.status === 'draft' || a.status === 'rejected'"
                size="small"
                color="primary"
                @click="publish(a.id)"
              >
                {{ a.status === 'rejected' ? 'Resubmit' : 'Publish' }}
              </v-btn>
              <v-btn
                v-else-if="a.status === 'pending_review' || a.status === 'listed'"
                size="small"
                variant="outlined"
                @click="unpublish(a.id)"
              >
                Unpublish
              </v-btn>
            </div>
          </div>
        </v-card>
      </div>
      <p v-if="!loading && agents.length === 0" class="text-medium-emphasis mt-4">No agents yet. Create your first agent.</p>
    </template>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useAuthStore } from '@/stores/auth'
import api from '@/services/api'

const authStore = useAuthStore()
const agents = ref([])
const loading = ref(true)

function statusColor(status) {
  const m = { listed: 'success', draft: 'secondary', pending_review: 'warning', rejected: 'error' }
  return m[status] || 'secondary'
}

async function loadAgents() {
  loading.value = true
  try {
    const { data } = await api.get('/agents/my')
    agents.value = data
  } catch (e) {
    console.error(e)
  } finally {
    loading.value = false
  }
}

async function publish(id) {
  try {
    await api.patch(`/agents/${id}/publish`)
    await loadAgents()
  } catch (e) {
    console.error(e)
    alert(e.response?.data?.detail || 'Failed to publish')
  }
}

async function unpublish(id) {
  try {
    await api.patch(`/agents/${id}/unpublish`)
    await loadAgents()
  } catch (e) {
    console.error(e)
    alert(e.response?.data?.detail || 'Failed to unpublish')
  }
}

onMounted(() => {
  if (authStore.user?.role === 'expert' || authStore.user?.role === 'admin') loadAgents()
})
</script>

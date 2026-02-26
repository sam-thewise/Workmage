<template>
  <div class="agent-management">
    <h1>My Agents</h1>
    <p v-if="authStore.user?.role !== 'expert'">Experts can create and manage agents here.</p>
    <template v-else>
      <router-link to="/dashboard/agents/create" class="btn primary">Create Agent</router-link>
      <router-link to="/dashboard/settings" class="btn secondary">Stripe & Settings</router-link>
      <div v-if="loading" class="loading">Loading...</div>
      <ul v-else class="agent-list">
        <li v-for="a in agents" :key="a.id" class="agent-item">
          <div class="agent-info">
            <span class="agent-name">{{ a.name }}</span>
            <span class="agent-status" :class="a.status">{{ a.status }}</span>
            <span v-if="a.description" class="agent-desc">{{ a.description }}</span>
            <span v-if="a.status === 'rejected' && a.rejection_reason" class="rejection-reason">{{ a.rejection_reason }}</span>
          </div>
          <div class="agent-actions">
            <router-link :to="`/dashboard/agents/${a.id}/edit`" class="btn small">Edit</router-link>
            <button
              v-if="a.status === 'draft' || a.status === 'rejected'"
              @click="publish(a.id)"
              class="btn small primary"
            >
              {{ a.status === 'rejected' ? 'Resubmit' : 'Publish' }}
            </button>
            <button
              v-else-if="a.status === 'pending_review' || a.status === 'listed'"
              @click="unpublish(a.id)"
              class="btn small secondary"
            >
              Unpublish
            </button>
          </div>
        </li>
      </ul>
      <p v-if="!loading && agents.length === 0">No agents yet. Create your first agent.</p>
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
  if (authStore.user?.role === 'expert') loadAgents()
})
</script>

<style scoped>
.agent-management { max-width: 800px; }
.btn { display: inline-block; padding: 0.5rem 1rem; border-radius: 6px; text-decoration: none; border: none; cursor: pointer; margin-right: 0.5rem; }
.btn.primary { background: #7c3aed; color: white; }
.btn.secondary { background: #444; color: white; }
.btn.small { padding: 0.25rem 0.5rem; font-size: 0.875rem; }
.agent-list { list-style: none; padding: 0; }
.agent-item { display: flex; justify-content: space-between; align-items: flex-start; padding: 1rem; border: 1px solid #333; border-radius: 8px; margin-bottom: 0.5rem; }
.agent-info { flex: 1; }
.agent-name { font-weight: 600; margin-right: 0.5rem; }
.agent-status { font-size: 0.75rem; padding: 0.125rem 0.5rem; border-radius: 4px; }
.agent-status.listed { background: #065f46; color: #a7f3d0; }
.agent-status.draft { background: #444; color: #aaa; }
.agent-status.pending_review { background: #92400e; color: #fde68a; }
.agent-status.rejected { background: #7f1d1d; color: #fecaca; }
.rejection-reason { display: block; font-size: 0.8rem; color: #f87171; margin-top: 0.25rem; }
.agent-desc { display: block; color: #888; font-size: 0.875rem; margin-top: 0.25rem; }
.agent-actions { display: flex; gap: 0.5rem; }
.loading { color: #888; }
</style>

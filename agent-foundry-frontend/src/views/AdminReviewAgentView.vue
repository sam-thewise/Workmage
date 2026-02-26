<template>
  <div class="review-agent">
    <router-link to="/admin" class="back">← Back to Admin</router-link>
    <div v-if="loading" class="loading">Loading...</div>
    <div v-else-if="agent" class="review-content">
      <h1>{{ agent.name }}</h1>
      <p v-if="agent.description">{{ agent.description }}</p>
      <div class="meta">
        <span>Status: {{ agent.status }}</span>
        <span>Approval: {{ agent.approval_status }}</span>
        <span>Expert ID: {{ agent.expert_id }}</span>
        <span>Category: {{ agent.category || '—' }}</span>
      </div>
      <div class="manifest-section">
        <h3>Manifest (APIs / MCP)</h3>
        <pre class="manifest-pre">{{ JSON.stringify(agent.manifest, null, 2) }}</pre>
      </div>
      <p class="hint">Check for duplicates and verify APIs/MCPs are safe.</p>
      <div class="actions">
        <button @click="approve" class="btn primary">Approve</button>
        <button @click="reject" class="btn danger">Reject</button>
      </div>
    </div>
    <p v-else class="error">Agent not found.</p>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import api from '@/services/api'

const route = useRoute()
const router = useRouter()
const agent = ref(null)
const loading = ref(true)

async function load() {
  loading.value = true
  try {
    const { data } = await api.get(`/admin/agents/${route.params.id}`)
    agent.value = data
  } catch {
    agent.value = null
  } finally {
    loading.value = false
  }
}

async function approve() {
  try {
    await api.post(`/admin/agents/${route.params.id}/approve`)
    router.push('/admin')
  } catch (e) {
    alert(e.response?.data?.detail || 'Failed to approve')
  }
}

async function reject() {
  const reason = prompt('Rejection reason (optional):')
  if (reason === null) return
  try {
    await api.post(`/admin/agents/${route.params.id}/reject`, { reason: reason || undefined })
    router.push('/admin')
  } catch (e) {
    alert(e.response?.data?.detail || 'Failed to reject')
  }
}

onMounted(load)
</script>

<style scoped>
.review-agent { max-width: 900px; }
.back { color: #94a3b8; text-decoration: none; display: inline-block; margin-bottom: 1rem; }
.back:hover { color: #7c3aed; }
.loading, .error { color: #94a3b8; }
.meta { display: flex; gap: 1rem; flex-wrap: wrap; margin: 1rem 0; font-size: 0.875rem; color: #64748b; }
.manifest-section { margin: 1.5rem 0; }
.manifest-pre {
  background: #0f172a;
  padding: 1rem;
  border-radius: 8px;
  overflow-x: auto;
  font-size: 0.8rem;
  max-height: 400px;
  overflow-y: auto;
}
.hint { font-size: 0.875rem; color: #64748b; margin: 1rem 0; }
.actions { display: flex; gap: 0.5rem; margin-top: 1rem; }
.btn { padding: 0.5rem 1rem; border-radius: 6px; border: none; cursor: pointer; }
.btn.primary { background: #7c3aed; color: white; }
.btn.danger { background: #dc2626; color: white; }
</style>

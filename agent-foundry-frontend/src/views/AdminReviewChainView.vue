<template>
  <div class="review-chain">
    <router-link to="/admin" class="back">← Back to Admin</router-link>
    <div v-if="loading" class="loading">Loading...</div>
    <div v-else-if="chain" class="review-content">
      <h1>{{ chain.name }}</h1>
      <p v-if="chain.description">{{ chain.description }}</p>
      <div class="meta">
        <span>Status: {{ chain.status }}</span>
        <span>Approval: {{ chain.approval_status }}</span>
        <span>Expert ID: {{ chain.expert_id }}</span>
        <span>Category: {{ chain.category || '—' }}</span>
      </div>
      <div class="definition-section">
        <h3>Chain Definition</h3>
        <pre class="definition-pre">{{ JSON.stringify(chain.definition, null, 2) }}</pre>
      </div>
      <p class="hint">Check for duplicates and verify included APIs/MCP usage is safe.</p>
      <div class="actions">
        <button @click="approve" class="btn primary">Approve</button>
        <button @click="reject" class="btn danger">Reject</button>
      </div>
    </div>
    <p v-else class="error">Chain not found.</p>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import api from '@/services/api'

const route = useRoute()
const router = useRouter()
const chain = ref(null)
const loading = ref(true)

async function load() {
  loading.value = true
  try {
    const { data } = await api.get(`/admin/chains/${route.params.id}`)
    chain.value = data
  } catch {
    chain.value = null
  } finally {
    loading.value = false
  }
}

async function approve() {
  try {
    await api.post(`/admin/chains/${route.params.id}/approve`)
    router.push('/admin')
  } catch (e) {
    alert(e.response?.data?.detail || 'Failed to approve')
  }
}

async function reject() {
  const reason = prompt('Rejection reason (optional):')
  if (reason === null) return
  try {
    await api.post(`/admin/chains/${route.params.id}/reject`, { reason: reason || undefined })
    router.push('/admin')
  } catch (e) {
    alert(e.response?.data?.detail || 'Failed to reject')
  }
}

onMounted(load)
</script>

<style scoped>
.review-chain { max-width: 900px; }
.back { color: #94a3b8; text-decoration: none; display: inline-block; margin-bottom: 1rem; }
.back:hover { color: #7c3aed; }
.loading, .error { color: #94a3b8; }
.meta { display: flex; gap: 1rem; flex-wrap: wrap; margin: 1rem 0; font-size: 0.875rem; color: #64748b; }
.definition-section { margin: 1.5rem 0; }
.definition-pre {
  background: #0f172a;
  padding: 1rem;
  border-radius: 8px;
  overflow-x: auto;
  font-size: 0.8rem;
  max-height: 420px;
  overflow-y: auto;
}
.hint { font-size: 0.875rem; color: #64748b; margin: 1rem 0; }
.actions { display: flex; gap: 0.5rem; margin-top: 1rem; }
.btn { padding: 0.5rem 1rem; border-radius: 6px; border: none; cursor: pointer; }
.btn.primary { background: #7c3aed; color: white; }
.btn.danger { background: #dc2626; color: white; }
</style>

<template>
  <div class="review-chain mx-auto pa-4" style="max-width: 900px;">
    <router-link to="/admin" class="text-medium-emphasis text-decoration-none d-inline-block mb-4">← Back to Admin</router-link>
    <div v-if="loading" class="text-medium-emphasis py-4">Loading...</div>
    <div v-else-if="chain" class="review-content">
      <h1 class="text-h4 mb-2">{{ chain.name }}</h1>
      <p v-if="chain.description" class="text-body-2 text-medium-emphasis mb-3">{{ chain.description }}</p>
      <div class="d-flex flex-wrap gap-3 text-body-2 text-medium-emphasis mb-4">
        <span>Status: {{ chain.status }}</span>
        <span>Approval: {{ chain.approval_status }}</span>
        <span>Expert ID: {{ chain.expert_id }}</span>
        <span>Category: {{ chain.category || '—' }}</span>
      </div>
      <v-card variant="tonal" class="pa-4 mb-4">
        <h3 class="text-subtitle-1 text-medium-emphasis mb-2">Chain Definition</h3>
        <pre class="definition-pre pa-3 ma-0 text-body-2" style="background: rgba(0,0,0,0.2); border-radius: 8px; overflow: auto; max-height: 400px;">{{ JSON.stringify(chain.definition, null, 2) }}</pre>
      </v-card>
      <p class="text-body-2 text-medium-emphasis mb-4">Check for duplicates and verify included APIs/MCP usage is safe.</p>
      <div class="d-flex gap-2">
        <v-btn color="primary" @click="approve">Approve</v-btn>
        <v-btn color="error" @click="reject">Reject</v-btn>
      </div>
    </div>
    <p v-else class="text-error py-4">Chain not found.</p>
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

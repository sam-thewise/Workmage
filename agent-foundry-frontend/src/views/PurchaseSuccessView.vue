<template>
  <div class="purchase-success text-center pa-6">
    <h1 class="text-h4 mb-4">Purchase Successful</h1>
    <p v-if="loading" class="text-medium-emphasis mb-4">Confirming your purchase...</p>
    <template v-else-if="error">
      <p class="text-error mb-4">{{ error }}</p>
      <v-btn variant="outlined" color="primary" to="/marketplace">Back to Marketplace</v-btn>
    </template>
    <template v-else>
      <p class="mb-4">Thank you! You now have access to this {{ chainId ? 'chain' : 'agent' }}.</p>
      <div class="d-flex gap-2 justify-center flex-wrap">
        <v-btn v-if="agentId" color="primary" :to="`/agents/${agentId}`">View AI Role</v-btn>
        <v-btn v-else-if="chainId" color="primary" :to="`/marketplace/chains/${chainId}`">View AI Team</v-btn>
        <v-btn variant="outlined" color="primary" :to="chainId ? '/marketplace/chains' : '/marketplace'">Browse More</v-btn>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import api from '@/services/api'

const route = useRoute()
const authStore = useAuthStore()
const loading = ref(true)
const error = ref('')
const agentId = ref(route.query.agent_id || '')
const chainId = ref(route.query.chain_id || '')

onMounted(async () => {
  const sid = route.query.session_id
  const aid = route.query.agent_id
  const cid = route.query.chain_id
  if (!sid || (!aid && !cid) || !authStore.isAuthenticated) {
    loading.value = false
    if (!authStore.isAuthenticated) {
      error.value = 'Please log in to confirm your purchase.'
    } else {
      error.value = 'Invalid redirect. If you completed payment, your purchase may still have been recorded.'
    }
    return
  }
  try {
    await api.post('/purchases/confirm-stripe', {
      session_id: sid,
      agent_id: aid ? parseInt(aid, 10) : undefined,
      chain_id: cid ? parseInt(cid, 10) : undefined,
    })
  } catch (e) {
    error.value = e.response?.data?.detail || 'Could not confirm purchase. Contact support if payment was charged.'
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <div class="purchase-success">
    <h1>Purchase Successful</h1>
    <p v-if="loading">Confirming your purchase...</p>
    <template v-else-if="error">
      <p class="error">{{ error }}</p>
      <router-link to="/marketplace" class="btn">Back to Marketplace</router-link>
    </template>
    <template v-else>
      <p>Thank you! You now have access to this {{ chainId ? 'chain' : 'agent' }}.</p>
      <router-link v-if="agentId" :to="`/agents/${agentId}`" class="btn primary">View Agent</router-link>
      <router-link v-else-if="chainId" :to="`/marketplace/chains/${chainId}`" class="btn primary">View Chain</router-link>
      <router-link :to="chainId ? '/marketplace/chains' : '/marketplace'" class="btn">Browse More</router-link>
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

<style scoped>
.purchase-success { text-align: center; padding: 2rem; }
.purchase-success h1 { margin-bottom: 1rem; }
.btn { display: inline-block; padding: 0.75rem 1.5rem; margin: 0.5rem; border-radius: 8px; text-decoration: none; border: 1px solid var(--wm-border); color: var(--wm-text); }
.btn.primary { background: var(--wm-primary); border-color: var(--wm-primary); color: var(--wm-white); }
.error { color: var(--wm-danger); margin: 1rem 0; }
</style>

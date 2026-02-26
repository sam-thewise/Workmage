<template>
  <div class="chain-detail">
    <div v-if="loading" class="loading">Loading...</div>
    <div v-else-if="error" class="error">{{ error }}</div>
    <template v-else-if="chain">
      <router-link to="/marketplace/chains" class="back">← Back to Chain Marketplace</router-link>
      <h1>{{ chain.name }}</h1>
      <p class="description">{{ chain.description || 'No description' }}</p>
      <div class="meta">
        <span class="price">${{ (chain.price_cents / 100).toFixed(2) }}</span>
        <span v-if="chain.category" class="category">{{ chain.category }}</span>
        <span v-if="chain.tags?.length" class="tags">{{ chain.tags.join(', ') }}</span>
      </div>
      <div class="section">
        <h3>Included Agents ({{ chain.agents?.length || 0 }})</h3>
        <ul>
          <li v-for="a in chain.agents || []" :key="a.id">
            {{ a.name }}
          </li>
        </ul>
      </div>
      <div class="section">
        <h3>Definition</h3>
        <pre>{{ JSON.stringify(chain.definition || {}, null, 2) }}</pre>
      </div>
      <div class="actions">
        <template v-if="authStore.isAuthenticated">
          <button
            v-if="!purchased && !purchasing"
            @click="purchase"
            class="btn primary"
            :disabled="purchaseLoading"
          >
            {{ chain.price_cents === 0 ? 'Get Free' : `Purchase $${(chain.price_cents / 100).toFixed(2)}` }}
          </button>
          <template v-else-if="purchased">
            <span class="purchased">✓ Purchased</span>
            <router-link :to="`/chains/${chain.id}/edit`" class="btn primary">Open Chain</router-link>
          </template>
        </template>
        <router-link v-else to="/login" class="btn primary">Login to Purchase</router-link>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, onMounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import api from '@/services/api'

const route = useRoute()
const authStore = useAuthStore()
const chain = ref(null)
const loading = ref(true)
const error = ref('')
const purchased = ref(false)
const purchaseLoading = ref(false)
const purchasing = ref(false)

async function loadChain() {
  loading.value = true
  error.value = ''
  try {
    const { data } = await api.get(`/chains/${route.params.id}`)
    chain.value = data
  } catch (_e) {
    error.value = 'Chain not found'
  } finally {
    loading.value = false
  }
}

async function checkPurchase() {
  if (!authStore.isAuthenticated || !chain.value) return
  try {
    const { data } = await api.get('/purchases/check', { params: { chain_id: chain.value.id } })
    purchased.value = data.purchased
  } catch {
    purchased.value = false
  }
}

async function purchase() {
  if (!chain.value) return
  purchaseLoading.value = true
  try {
    const { data } = await api.post('/purchases', { chain_id: chain.value.id })
    if (data.checkout_url) {
      window.location.href = data.checkout_url
      purchasing.value = true
      return
    }
    purchased.value = true
  } catch (e) {
    error.value = e.response?.data?.detail || 'Purchase failed'
  } finally {
    purchaseLoading.value = false
  }
}

onMounted(() => loadChain())
watch([chain, () => authStore.isAuthenticated], () => checkPurchase(), { immediate: true })
</script>

<style scoped>
.chain-detail { max-width: 780px; }
.back { color: #94a3b8; text-decoration: none; display: inline-block; margin-bottom: 1rem; }
.back:hover { color: #7c3aed; }
.description { color: #94a3b8; margin: 1rem 0; }
.meta { display: flex; gap: 1rem; flex-wrap: wrap; margin-bottom: 1.5rem; }
.price { color: #7c3aed; font-weight: 600; font-size: 1.25rem; }
.category, .tags { color: #64748b; font-size: 0.9rem; }
.section { margin: 1.5rem 0; }
.section h3 { font-size: 0.875rem; color: #64748b; margin-bottom: 0.5rem; }
.section ul { list-style: none; padding: 0; }
.section li { padding: 0.25rem 0; color: #94a3b8; }
pre { white-space: pre-wrap; background: #0f172a; padding: 1rem; border-radius: 8px; overflow-x: auto; }
.btn { display: inline-block; padding: 0.75rem 1.5rem; border-radius: 8px; text-decoration: none; border: none; cursor: pointer; font-size: 1rem; }
.btn.primary { background: #7c3aed; color: white; }
.btn:disabled { opacity: 0.6; cursor: not-allowed; }
.purchased { color: #10b981; font-weight: 500; }
.actions { margin-top: 2rem; display: flex; gap: 0.75rem; align-items: center; }
.error { color: #f87171; }
</style>

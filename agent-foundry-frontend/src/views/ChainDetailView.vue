<template>
  <div class="chain-detail mx-auto" style="max-width: 780px;">
    <div v-if="loading" class="text-medium-emphasis py-4">Loading...</div>
    <div v-else-if="error" class="text-error py-4">{{ error }}</div>
    <template v-else-if="chain">
      <router-link to="/marketplace/chains" class="text-medium-emphasis text-decoration-none d-inline-block mb-4">← Back to Chain Marketplace</router-link>
      <h1 class="text-h4 mb-2">{{ chain.name }}</h1>
      <p class="text-body-1 text-medium-emphasis my-3">{{ chain.description || 'No description' }}</p>
      <div class="d-flex flex-wrap gap-3 mb-6">
        <span class="text-accent font-weight-bold text-h6">${{ (chain.price_cents / 100).toFixed(2) }}</span>
        <span v-if="chain.category" class="text-body-2 text-medium-emphasis">{{ chain.category }}</span>
        <span v-if="chain.tags?.length" class="text-body-2 text-medium-emphasis">{{ chain.tags.join(', ') }}</span>
      </div>
      <v-card variant="tonal" class="pa-4 mb-4">
        <h3 class="text-subtitle-1 text-medium-emphasis mb-2">Included Agents ({{ chain.agents?.length || 0 }})</h3>
        <ul class="pa-0 ma-0" style="list-style: none;">
          <li v-for="a in chain.agents || []" :key="a.id" class="py-1">{{ a.name }}</li>
        </ul>
      </v-card>
      <v-card variant="tonal" class="pa-4 mb-6">
        <h3 class="text-subtitle-1 text-medium-emphasis mb-2">Definition</h3>
        <pre class="pa-3 ma-0 text-body-2" style="white-space: pre-wrap; background: rgba(0,0,0,0.2); border-radius: 8px; overflow-x: auto;">{{ JSON.stringify(chain.definition || {}, null, 2) }}</pre>
      </v-card>
      <div class="d-flex flex-wrap gap-3 mt-8">
        <template v-if="authStore.isAuthenticated">
          <v-btn
            v-if="!purchased && !purchasing"
            color="primary"
            :loading="purchaseLoading"
            @click="purchase"
          >
            {{ chain.price_cents === 0 ? 'Get Free' : `Purchase $${(chain.price_cents / 100).toFixed(2)}` }}
          </v-btn>
          <template v-else-if="purchased">
            <span class="text-success font-weight-medium align-self-center">✓ Purchased</span>
            <v-btn color="primary" :to="`/chains/${chain.id}/edit`">Open Chain</v-btn>
          </template>
        </template>
        <v-btn v-else color="primary" to="/login">Login to Purchase</v-btn>
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

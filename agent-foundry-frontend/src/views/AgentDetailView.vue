<template>
  <div class="agent-detail">
    <div v-if="loading" class="loading">Loading...</div>
    <div v-else-if="error" class="error">{{ error }}</div>
    <template v-else-if="agent">
      <router-link to="/marketplace" class="back">← Back to Marketplace</router-link>
      <h1>{{ agent.name }}</h1>
      <p class="description">{{ agent.description || 'No description' }}</p>
      <div class="meta">
        <span class="price">${{ (agent.price_cents / 100).toFixed(2) }}</span>
        <span v-if="agent.category" class="category">{{ agent.category }}</span>
        <span v-if="agent.tags?.length" class="tags">{{ agent.tags.join(', ') }}</span>
      </div>
      <div v-if="agent.manifest?.skills?.length" class="section">
        <h3>Skills</h3>
        <ul>
          <li v-for="(s, i) in agent.manifest.skills" :key="i">
            {{ typeof s === 'object' ? s.name : s }}
          </li>
        </ul>
      </div>
      <div v-if="agent.manifest?.domains?.length" class="section">
        <h3>Domains</h3>
        <ul>
          <li v-for="(d, i) in agent.manifest.domains" :key="i">
            {{ typeof d === 'object' ? d.name : d }}
          </li>
        </ul>
      </div>
      <div class="actions">
        <template v-if="authStore.isAuthenticated">
          <button
            v-if="!purchased && !purchasing"
            @click="purchase"
            class="btn primary"
            :disabled="purchaseLoading"
          >
            {{ agent.price_cents === 0 ? 'Get Free' : `Purchase $${(agent.price_cents / 100).toFixed(2)}` }}
          </button>
          <template v-else-if="purchased">
            <span class="purchased">✓ Purchased</span>
            <router-link :to="`/run/${agent?.id}`" class="btn primary">Run Agent</router-link>
          </template>
        </template>
        <router-link v-else to="/login" class="btn primary">Login to Purchase</router-link>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import api from '@/services/api'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
const agent = ref(null)
const loading = ref(true)
const error = ref('')
const purchased = ref(false)
const purchaseLoading = ref(false)
const purchasing = ref(false)

async function loadAgent() {
  loading.value = true
  error.value = ''
  try {
    const { data } = await api.get(`/agents/${route.params.id}`)
    agent.value = data
  } catch (e) {
    error.value = 'Agent not found'
  } finally {
    loading.value = false
  }
}

async function checkPurchase() {
  if (!authStore.isAuthenticated || !agent.value) return
  try {
    const { data } = await api.get(`/purchases/check/${agent.value.id}`)
    purchased.value = data.purchased
  } catch {
    purchased.value = false
  }
}

async function purchase() {
  if (!agent.value) return
  purchaseLoading.value = true
  try {
    const { data } = await api.post('/purchases', { agent_id: agent.value.id })
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

onMounted(() => loadAgent())
watch([agent, () => authStore.isAuthenticated], () => checkPurchase(), { immediate: true })
</script>

<style scoped>
.agent-detail { max-width: 720px; }
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
.btn { display: inline-block; padding: 0.75rem 1.5rem; border-radius: 8px; text-decoration: none; border: none; cursor: pointer; font-size: 1rem; }
.btn.primary { background: #7c3aed; color: white; }
.btn:disabled { opacity: 0.6; cursor: not-allowed; }
.purchased { color: #10b981; font-weight: 500; }
.actions { margin-top: 2rem; }
.error { color: #f87171; }
</style>

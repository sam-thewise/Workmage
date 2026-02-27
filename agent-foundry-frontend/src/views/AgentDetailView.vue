<template>
  <div class="agent-detail mx-auto" style="max-width: 720px;">
    <div v-if="loading" class="text-medium-emphasis py-4">Loading...</div>
    <div v-else-if="error" class="text-error py-4">{{ error }}</div>
    <template v-else-if="agent">
      <router-link to="/marketplace" class="text-medium-emphasis text-decoration-none d-inline-block mb-4">← Back to Marketplace</router-link>
      <h1 class="text-h4 mb-2">{{ agent.name }}</h1>
      <p class="text-body-1 text-medium-emphasis my-3">{{ agent.description || 'No description' }}</p>
      <div class="d-flex flex-wrap gap-3 mb-6">
        <span class="text-accent font-weight-bold text-h6">${{ (agent.price_cents / 100).toFixed(2) }}</span>
        <span v-if="agent.category" class="text-body-2 text-medium-emphasis">{{ agent.category }}</span>
        <span v-if="agent.tags?.length" class="text-body-2 text-medium-emphasis">{{ agent.tags.join(', ') }}</span>
      </div>
      <v-card v-if="agent.manifest?.skills?.length" variant="tonal" class="pa-4 mb-4">
        <h3 class="text-subtitle-1 text-medium-emphasis mb-2">Skills</h3>
        <ul class="pa-0 ma-0" style="list-style: none;">
          <li v-for="(s, i) in agent.manifest.skills" :key="i" class="py-1">
            {{ typeof s === 'object' ? s.name : s }}
          </li>
        </ul>
      </v-card>
      <v-card v-if="agent.manifest?.domains?.length" variant="tonal" class="pa-4 mb-6">
        <h3 class="text-subtitle-1 text-medium-emphasis mb-2">Domains</h3>
        <ul class="pa-0 ma-0" style="list-style: none;">
          <li v-for="(d, i) in agent.manifest.domains" :key="i" class="py-1">
            {{ typeof d === 'object' ? d.name : d }}
          </li>
        </ul>
      </v-card>
      <div class="d-flex flex-wrap gap-3 mt-8">
        <template v-if="authStore.isAuthenticated">
          <v-btn
            v-if="!purchased && !purchasing"
            color="primary"
            :loading="purchaseLoading"
            @click="purchase"
          >
            {{ agent.price_cents === 0 ? 'Get Free' : `Purchase $${(agent.price_cents / 100).toFixed(2)}` }}
          </v-btn>
          <template v-else-if="purchased">
            <span class="text-success font-weight-medium align-self-center">✓ Purchased</span>
            <v-btn color="primary" :to="`/run/${agent?.id}`">Run Agent</v-btn>
          </template>
        </template>
        <v-btn v-else color="primary" to="/login">Login to Purchase</v-btn>
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
    const { data } = await api.get('/purchases/check', { params: { agent_id: agent.value.id } })
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

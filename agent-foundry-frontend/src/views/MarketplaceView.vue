<template>
  <div class="marketplace">
    <h1 class="text-h4 mb-2">Marketplace</h1>
    <p class="mb-4">
      <router-link to="/marketplace/chains" class="text-accent text-decoration-none">Browse Chain Marketplace</router-link>
    </p>
    <div class="d-flex align-center gap-2 mb-6">
      <label class="text-body-2">Category</label>
      <v-select
        v-model="category"
        :items="categories"
        item-title="title"
        item-value="value"
        density="compact"
        hide-details
        class="flex-grow-0"
        style="max-width: 200px;"
        @update:model-value="loadAgents"
      />
    </div>
    <p v-if="loading" class="text-medium-emphasis mb-4">Loading agents...</p>
    <v-row v-else>
      <v-col
        v-for="agent in agents"
        :key="agent.id"
        cols="12"
        sm="6"
        md="4"
      >
        <router-link :to="`/agents/${agent.id}`" class="text-decoration-none">
          <v-card variant="tonal" class="pa-4 fill-height" hover>
            <h3 class="text-h6 mb-2">{{ agent.name }}</h3>
            <p class="text-body-2 text-medium-emphasis mb-2">{{ agent.description || 'No description' }}</p>
            <span class="text-subtitle-1 text-accent font-weight-bold">${{ (agent.price_cents / 100).toFixed(2) }}</span>
          </v-card>
        </router-link>
      </v-col>
    </v-row>
    <p v-if="!loading && agents.length === 0" class="text-medium-emphasis mt-8">No agents listed yet.</p>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import api from '@/services/api'

const agents = ref([])
const loading = ref(true)
const category = ref('')
const allAgents = ref([])

const categories = computed(() => {
  const s = new Set()
  allAgents.value.forEach((a) => { if (a.category) s.add(a.category) })
  return [{ title: 'All', value: '' }, ...[...s].sort().map(c => ({ title: c, value: c }))]
})

async function loadAgents() {
  loading.value = true
  try {
    const params = category.value ? { category: category.value } : {}
    const { data } = await api.get('/agents/', { params })
    agents.value = data
    if (!category.value) allAgents.value = data
  } catch {
    agents.value = []
  } finally {
    loading.value = false
  }
}

onMounted(loadAgents)
</script>

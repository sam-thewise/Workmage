<template>
  <div class="marketplace">
    <h1 class="text-h4 mb-4">AI Team Marketplace</h1>
    <div class="d-flex align-center gap-2 mb-6">
      <label class="text-body-2">Category</label>
      <v-select
        v-model="category"
        :items="categoryItems"
        item-title="title"
        item-value="value"
        density="compact"
        hide-details
        class="flex-grow-0"
        style="max-width: 200px;"
        @update:model-value="loadChains"
      />
    </div>
    <p v-if="loading" class="text-medium-emphasis mb-4">Loading chains...</p>
    <v-row v-else>
      <v-col v-for="chain in chains" :key="chain.id" cols="12" sm="6" md="4">
        <router-link :to="`/marketplace/chains/${chain.id}`" class="text-decoration-none">
          <v-card variant="tonal" class="pa-4 fill-height" hover>
            <h3 class="text-h6 mb-2">{{ chain.name }}</h3>
            <p class="text-body-2 text-medium-emphasis mb-2">{{ chain.description || 'No description' }}</p>
            <span class="text-subtitle-1 text-accent font-weight-bold">${{ (chain.price_cents / 100).toFixed(2) }}</span>
          </v-card>
        </router-link>
      </v-col>
    </v-row>
    <p v-if="!loading && chains.length === 0" class="text-medium-emphasis mt-8">No chains listed yet.</p>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import api from '@/services/api'

const chains = ref([])
const loading = ref(true)
const category = ref('')
const allChains = ref([])

const categories = computed(() => {
  const s = new Set()
  allChains.value.forEach((c) => { if (c.category) s.add(c.category) })
  return [...s].sort()
})

const categoryItems = computed(() => [
  { title: 'All', value: '' },
  ...categories.value.map(c => ({ title: c, value: c }))
])

async function loadChains() {
  loading.value = true
  try {
    const params = category.value ? { category: category.value } : {}
    const { data } = await api.get('/chains/marketplace', { params })
    chains.value = data || []
    if (!category.value) allChains.value = data || []
  } catch {
    chains.value = []
  } finally {
    loading.value = false
  }
}

onMounted(loadChains)
</script>

<template>
  <div class="marketplace">
    <h1>Chain Marketplace</h1>
    <div class="filters">
      <label>Category</label>
      <select v-model="category" @change="loadChains">
        <option value="">All</option>
        <option v-for="c in categories" :key="c" :value="c">{{ c }}</option>
      </select>
    </div>
    <p v-if="loading">Loading chains...</p>
    <div v-else class="chains-grid">
      <router-link
        v-for="chain in chains"
        :key="chain.id"
        :to="`/marketplace/chains/${chain.id}`"
        class="chain-card"
      >
        <h3>{{ chain.name }}</h3>
        <p>{{ chain.description || 'No description' }}</p>
        <span class="price">${{ (chain.price_cents / 100).toFixed(2) }}</span>
      </router-link>
    </div>
    <p v-if="!loading && chains.length === 0" class="empty">No chains listed yet.</p>
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

<style scoped>
.chains-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 1.5rem;
}
.filters { margin-bottom: 1.5rem; }
.filters label { margin-right: 0.5rem; }
.filters select { padding: 0.5rem; border-radius: 6px; border: 1px solid var(--wm-border); background: var(--wm-bg-soft); color: var(--wm-text); }
.chain-card {
  background: var(--wm-bg-soft);
  padding: 1.5rem;
  border-radius: 8px;
  border: 1px solid var(--wm-border);
  text-decoration: none;
  color: inherit;
  display: block;
}
.chain-card:hover { border-color: var(--wm-accent); }
.chain-card p {
  color: var(--wm-text-muted);
  font-size: 0.9rem;
  margin-bottom: 0.5rem;
}
.price {
  color: var(--wm-accent);
  font-weight: 600;
}
.empty {
  color: var(--wm-text-muted);
  margin-top: 2rem;
}
</style>

<template>
  <div class="marketplace">
    <h1>Marketplace</h1>
    <p class="switch-link"><router-link to="/marketplace/chains">Browse Chain Marketplace</router-link></p>
    <div class="filters">
      <label>Category</label>
      <select v-model="category" @change="loadAgents">
        <option value="">All</option>
        <option v-for="c in categories" :key="c" :value="c">{{ c }}</option>
      </select>
    </div>
    <p v-if="loading">Loading agents...</p>
    <div v-else class="agents-grid">
      <router-link
        v-for="agent in agents"
        :key="agent.id"
        :to="`/agents/${agent.id}`"
        class="agent-card"
      >
        <h3>{{ agent.name }}</h3>
        <p>{{ agent.description || 'No description' }}</p>
        <span class="price">${{ (agent.price_cents / 100).toFixed(2) }}</span>
      </router-link>
    </div>
    <p v-if="!loading && agents.length === 0" class="empty">No agents listed yet.</p>
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
  return [...s].sort()
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

<style scoped>
.agents-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 1.5rem;
}
.filters { margin-bottom: 1.5rem; }
.filters label { margin-right: 0.5rem; }
.filters select { padding: 0.5rem; border-radius: 6px; border: 1px solid var(--wm-border); background: var(--wm-bg-soft); color: var(--wm-text); }
.agent-card {
  background: var(--wm-bg-soft);
  padding: 1.5rem;
  border-radius: 8px;
  border: 1px solid var(--wm-border);
  text-decoration: none;
  color: inherit;
  display: block;
}
.agent-card:hover { border-color: var(--wm-accent); }
.agent-card h3 {
  margin-bottom: 0.5rem;
}
.agent-card p {
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
.switch-link { margin-bottom: 0.75rem; }
.switch-link a { color: var(--wm-accent); text-decoration: none; }
</style>

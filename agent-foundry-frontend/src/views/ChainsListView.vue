<template>
  <div class="chains-list">
    <h1>Chains</h1>
    <p class="subtitle">Build and publish chain listings with moderation.</p>
    <router-link to="/chains/new" class="btn primary">Create Chain</router-link>
    <div v-if="loading" class="loading">Loading...</div>
    <ul v-else-if="chains.length === 0" class="empty">
      <li>No chains yet. <router-link to="/chains/new">Create one</router-link>.</li>
    </ul>
    <ul v-else class="chain-list">
      <li v-for="c in chains" :key="c.id">
        <router-link :to="`/chains/${c.id}/edit`" class="chain-card">
          <span class="name">{{ c.name }}</span>
          <span class="meta">Status: {{ c.status }} · Updated {{ formatDate(c.updated_at || c.created_at) }}</span>
        </router-link>
      </li>
    </ul>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import api from '@/services/api'

const chains = ref([])
const loading = ref(true)

async function loadChains() {
  loading.value = true
  try {
    const { data } = await api.get('/chains/my')
    chains.value = data || []
  } catch {
    chains.value = []
  } finally {
    loading.value = false
  }
}

function formatDate(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  return d.toLocaleDateString()
}

onMounted(loadChains)
</script>

<style scoped>
.chains-list { max-width: 640px; }
.subtitle { color: #94a3b8; margin: 0.5rem 0 1rem; font-size: 0.95rem; }
.btn { display: inline-block; padding: 0.5rem 1rem; border-radius: 8px; text-decoration: none; margin-bottom: 1rem; }
.btn.primary { background: #7c3aed; color: white; }
.loading { color: #94a3b8; }
.empty { list-style: none; padding: 0; color: #94a3b8; }
.empty a { color: #7c3aed; }
.chain-list { list-style: none; padding: 0; }
.chain-list li { margin-bottom: 0.5rem; }
.chain-card { display: flex; flex-direction: column; padding: 1rem; background: #1e293b; border-radius: 8px; border: 1px solid #334155; text-decoration: none; color: inherit; }
.chain-card:hover { border-color: #7c3aed; }
.chain-card .name { font-weight: 500; }
.chain-card .meta { font-size: 0.8rem; color: #64748b; margin-top: 0.25rem; }
</style>

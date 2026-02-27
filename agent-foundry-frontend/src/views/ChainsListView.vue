<template>
  <div class="chains-list mx-auto" style="max-width: 640px;">
    <h1 class="text-h4 mb-2">Chains</h1>
    <p class="text-body-2 text-medium-emphasis mb-4">Build and publish chain listings with moderation.</p>
    <v-btn color="primary" to="/chains/new" class="mb-4">Create Chain</v-btn>
    <div v-if="loading" class="text-medium-emphasis mb-4">Loading...</div>
    <ul v-else-if="chains.length === 0" class="pa-0 ma-0 text-medium-emphasis" style="list-style: none;">
      <li>No chains yet. <router-link to="/chains/new" class="text-accent text-decoration-none">Create one</router-link>.</li>
    </ul>
    <ul v-else class="pa-0 ma-0" style="list-style: none;">
      <li v-for="c in chains" :key="c.id" class="mb-2">
        <router-link :to="`/chains/${c.id}/edit`" class="text-decoration-none">
          <v-card variant="tonal" class="pa-4" hover>
            <span class="font-weight-medium d-block">{{ c.name }}</span>
            <span class="text-caption text-medium-emphasis">Status: {{ c.status }} · Updated {{ formatDate(c.updated_at || c.created_at) }}</span>
          </v-card>
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

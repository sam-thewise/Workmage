<template>
  <div class="api-keys mx-auto pa-4" style="max-width: 480px;">
    <h1 class="text-h4 mb-2">API Keys (BYOK)</h1>
    <p class="text-body-2 text-medium-emphasis mb-4">Save your LLM API keys to use your own credits when running agents.</p>
    <div class="d-flex gap-2 align-center flex-wrap mb-4">
      <v-select
        v-model="provider"
        :items="[{ title: 'OpenAI', value: 'openai' }, { title: 'Anthropic', value: 'anthropic' }]"
        item-title="title"
        item-value="value"
        density="compact"
        hide-details
        style="max-width: 140px;"
      />
      <v-text-field v-model="apiKey" type="password" placeholder="sk-..." density="compact" hide-details class="flex-grow-1" style="min-width: 200px;" />
      <v-btn color="primary" @click="saveKey">Save</v-btn>
    </div>
    <p v-if="saved" class="text-success text-body-2 mb-2">Key saved.</p>
    <p v-if="error" class="text-error text-body-2 mb-2">{{ error }}</p>
    <div v-if="providers.length" class="mt-6">
      <h3 class="text-h6 mb-3">Saved providers</h3>
      <ul class="pa-0 ma-0" style="list-style: none;">
        <li v-for="p in providers" :key="p" class="d-flex align-center py-2">
          <span class="flex-grow-1">{{ p }}</span>
          <v-btn size="small" variant="text" @click="removeKey(p)">Remove</v-btn>
        </li>
      </ul>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import api from '@/services/api'

const provider = ref('openai')
const apiKey = ref('')
const saved = ref(false)
const error = ref('')
const providers = ref([])

async function loadProviders() {
  try {
    const { data } = await api.get('/llm/keys')
    providers.value = data.providers || []
  } catch {
    providers.value = []
  }
}

async function saveKey() {
  if (!apiKey.value.trim()) return
  saved.value = false
  error.value = ''
  try {
    await api.post('/llm/keys', { provider: provider.value, api_key: apiKey.value })
    saved.value = true
    apiKey.value = ''
    loadProviders()
  } catch (e) {
    error.value = e.response?.data?.detail || 'Failed to save'
  }
}

async function removeKey(p) {
  try {
    await api.delete(`/llm/keys/${p}`)
    loadProviders()
  } catch (e) {
    error.value = e.response?.data?.detail || 'Failed to remove'
  }
}

onMounted(loadProviders)
</script>

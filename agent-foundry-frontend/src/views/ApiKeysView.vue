<template>
  <div class="api-keys">
    <h1>API Keys (BYOK)</h1>
    <p>Save your LLM API keys to use your own credits when running agents.</p>
    <div class="key-form">
      <select v-model="provider">
        <option value="openai">OpenAI</option>
        <option value="anthropic">Anthropic</option>
      </select>
      <input v-model="apiKey" type="password" placeholder="sk-..." />
      <button @click="saveKey" class="btn primary">Save</button>
    </div>
    <p v-if="saved" class="success">Key saved.</p>
    <p v-if="error" class="error">{{ error }}</p>
    <div class="saved" v-if="providers.length">
      <h3>Saved providers</h3>
      <ul>
        <li v-for="p in providers" :key="p">
          {{ p }}
          <button @click="removeKey(p)" class="btn small">Remove</button>
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

<style scoped>
.api-keys { max-width: 480px; }
.key-form { display: flex; gap: 0.5rem; margin: 1rem 0; }
.key-form select, .key-form input { padding: 0.5rem; border-radius: 6px; border: 1px solid #444; background: #1a1a2e; color: #fff; }
.key-form input { flex: 1; }
.btn { padding: 0.5rem 1rem; border-radius: 6px; border: none; cursor: pointer; }
.btn.primary { background: #7c3aed; color: white; }
.btn.small { padding: 0.25rem 0.5rem; font-size: 0.8rem; margin-left: 0.5rem; }
.success { color: #10b981; }
.error { color: #f87171; }
.saved { margin-top: 1.5rem; }
.saved ul { list-style: none; padding: 0; }
.saved li { display: flex; align-items: center; margin: 0.5rem 0; }
</style>

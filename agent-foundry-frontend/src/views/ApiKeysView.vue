<template>
  <div class="api-keys mx-auto pa-4" style="max-width: 560px;">
    <h1 class="text-h4 mb-2">API Keys &amp; GitHub</h1>
    <p class="text-body-2 text-medium-emphasis mb-4">Save your LLM API keys (BYOK) and GitHub token for agents that use repo data.</p>

    <v-card variant="tonal" class="mb-6 pa-4">
      <h2 class="text-h6 mb-2">LLM keys (BYOK)</h2>
      <p class="text-body-2 text-medium-emphasis mb-3">Use your own credits when running agents.</p>
      <div class="d-flex gap-2 align-center flex-wrap mb-3">
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
      <div v-if="providers.length">
        <h3 class="text-subtitle-1 mb-2">Saved LLM providers</h3>
        <ul class="pa-0 ma-0" style="list-style: none;">
          <li v-for="p in providers" :key="p" class="d-flex align-center py-2">
            <span class="flex-grow-1">{{ p }}</span>
            <v-btn size="small" variant="text" @click="removeKey(p)">Remove</v-btn>
          </li>
        </ul>
      </div>
    </v-card>

    <v-card variant="tonal" class="pa-4">
      <h2 class="text-h6 mb-2">GitHub token</h2>
      <p class="text-body-2 text-medium-emphasis mb-3">Required for agents that use GitHub (e.g. X GitHub Activity). Stored encrypted and only sent at runtime.</p>
      <div class="d-flex gap-2 align-center flex-wrap mb-3">
        <v-text-field
          v-model="githubToken"
          type="password"
          placeholder="ghp_... or github_pat_..."
          density="compact"
          hide-details
          class="flex-grow-1"
          style="min-width: 200px;"
        />
        <v-btn color="primary" :disabled="!githubToken.trim()" @click="saveGitHubToken">Save</v-btn>
        <v-btn v-if="hasGitHubToken" size="small" variant="text" @click="removeGitHubToken">Remove</v-btn>
      </div>
      <p v-if="githubSaved" class="text-success text-body-2 mb-2">GitHub token saved.</p>
      <p v-if="githubError" class="text-error text-body-2 mb-2">{{ githubError }}</p>
      <p v-if="hasGitHubToken && !githubSaved" class="text-body-2 text-medium-emphasis">GitHub token is stored. Use Remove to clear it.</p>
    </v-card>
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

const githubToken = ref('')
const hasGitHubToken = ref(false)
const githubSaved = ref(false)
const githubError = ref('')

async function loadProviders() {
  try {
    const { data } = await api.get('/llm/keys')
    providers.value = data.providers || []
  } catch {
    providers.value = []
  }
}

async function loadGitHubStatus() {
  try {
    const { data } = await api.get('/users/me/github-token')
    hasGitHubToken.value = data.has_token === true
  } catch {
    hasGitHubToken.value = false
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

async function saveGitHubToken() {
  if (!githubToken.value.trim()) return
  githubSaved.value = false
  githubError.value = ''
  try {
    await api.post('/users/me/github-token', { token: githubToken.value })
    githubSaved.value = true
    githubToken.value = ''
    loadGitHubStatus()
  } catch (e) {
    githubError.value = e.response?.data?.detail || 'Failed to save'
  }
}

async function removeGitHubToken() {
  githubError.value = ''
  try {
    await api.delete('/users/me/github-token')
    hasGitHubToken.value = false
    loadGitHubStatus()
  } catch (e) {
    githubError.value = e.response?.data?.detail || 'Failed to remove'
  }
}

onMounted(() => {
  loadProviders()
  loadGitHubStatus()
})
</script>

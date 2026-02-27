<template>
  <div class="run-agent">
    <h1>Run Agent</h1>
    <div v-if="!agent && agentId" class="loading">Loading agent...</div>
    <div v-else-if="!agent && !agentId" class="pick-agent">
      <h2>Choose an agent to run</h2>
      <p class="chain-hint"><router-link to="/chains">Or build a chain</router-link> of agents.</p>
      <div v-if="purchasesLoading">Loading...</div>
      <ul v-else class="purchase-list">
        <li v-for="p in purchases" :key="p.agent_id">
          <router-link :to="`/run/${p.agent_id}`">{{ p.agent_name || `Agent #${p.agent_id}` }}</router-link>
        </li>
      </ul>
      <p v-if="!purchasesLoading && purchases.length === 0">No agents purchased. <router-link to="/marketplace">Browse marketplace</router-link>.</p>
    </div>
    <div v-else-if="!agent" class="error">Agent not found.</div>
    <form v-else @submit.prevent="run" class="run-form">
      <div class="agent-info">
        <h2>{{ agent.name }}</h2>
        <p>{{ agent.description }}</p>
      </div>
      <div class="field">
        <label>Input</label>
        <textarea v-model="userInput" rows="5" placeholder="Enter your prompt or question..." required></textarea>
      </div>
      <div class="field">
        <label>Model</label>
        <select v-model="model">
          <option value="openai/gpt-4">OpenAI GPT-4</option>
          <option value="openai/gpt-3.5-turbo">OpenAI GPT-3.5</option>
          <option value="anthropic/claude-3-sonnet-20240229">Anthropic Claude 3 Sonnet</option>
          <option value="ollama/llama2">Ollama Llama 2 (local)</option>
        </select>
      </div>
      <div class="field">
        <label>
          <input type="checkbox" v-model="useByok" />
          Use my API key (BYOK)
        </label>
        <p v-if="useByok" class="hint">
          Make sure you've saved your API key for {{ model.split('/')[0] }}.
          <router-link to="/settings/keys">Manage keys</router-link>
        </p>
        <template v-else>
          <p v-if="estimate" class="estimate">Platform estimate: ~${{ estimate.estimated_cost_usd != null ? estimate.estimated_cost_usd.toFixed(4) : 'N/A' }}</p>
          <p v-else-if="subscription" class="quota">Runs remaining: {{ subscription.runs_remaining }}/{{ subscription.runs_per_period }} ({{ subscription.tier }} tier)</p>
        </template>
      </div>
      <div class="actions">
        <button type="submit" class="btn primary" :disabled="running">
          {{ running ? 'Running...' : 'Run' }}
        </button>
      </div>
    </form>
    <div v-if="result" class="result">
      <h3>Result</h3>
      <pre class="output">{{ result.content || result.error || 'No output' }}</pre>
      <div v-if="result.usage" class="usage">
        Tokens: {{ result.usage.prompt_tokens }} prompt, {{ result.usage.completion_tokens }} completion
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import api from '@/services/api'

const route = useRoute()
const authStore = useAuthStore()
const agentId = ref(route.params.id ? parseInt(route.params.id, 10) : null)
const agent = ref(null)
const userInput = ref('')
const model = ref('openai/gpt-4')
const useByok = ref(false)
const running = ref(false)
const result = ref(null)
const purchases = ref([])
const purchasesLoading = ref(false)
const estimate = ref(null)
const subscription = ref(null)
let pollInterval = null

async function loadPurchases() {
  purchasesLoading.value = true
  try {
    const { data } = await api.get('/purchases/my')
    purchases.value = data
  } catch {
    purchases.value = []
  } finally {
    purchasesLoading.value = false
  }
}

async function loadAgent() {
  if (!agentId.value) return
  try {
    const { data } = await api.get(`/agents/${agentId.value}`)
    agent.value = data
  } catch {
    agent.value = null
  }
}

async function fetchSubscription() {
  try {
    const { data } = await api.get('/runs/subscription')
    subscription.value = data
  } catch {
    subscription.value = null
  }
}

async function fetchEstimate() {
  if (useByok.value || !userInput.value.trim()) {
    estimate.value = null
    return
  }
  try {
    const { data } = await api.post('/llm/estimate', {
      model: model.value,
      messages: [{ role: 'user', content: userInput.value }],
      estimated_completion_tokens: 500
    })
    estimate.value = data
  } catch {
    estimate.value = null
  }
}

async function run() {
  if (!agentId.value || !userInput.value.trim()) return
  running.value = true
  result.value = null
  try {
    const { data } = await api.post('/runs/', {
      agent_id: agentId.value,
      user_input: userInput.value,
      model: model.value,
      use_byok: useByok.value
    })
    if (data.job_id) {
      pollInterval = setInterval(() => pollRun(data.job_id), 1500)
    }
  } catch (e) {
    result.value = { error: e.response?.data?.detail || 'Run failed' }
    running.value = false
  }
}

async function pollRun(jobId) {
  try {
    const { data } = await api.get(`/runs/${jobId}`)
    if (data.status === 'completed') {
      fetchSubscription()
      clearInterval(pollInterval)
      pollInterval = null
      result.value = { content: data.content, usage: data.usage }
      running.value = false
    } else if (data.status === 'error') {
      clearInterval(pollInterval)
      pollInterval = null
      result.value = { error: data.error || 'Run failed' }
      running.value = false
    }
  } catch (e) {
    clearInterval(pollInterval)
    pollInterval = null
    result.value = { error: 'Failed to get result' }
    running.value = false
  }
}

watch([model, useByok, userInput], () => {
  if (agentId.value && !useByok.value && userInput.value) fetchEstimate()
  else estimate.value = null
})

onMounted(() => {
  if (agentId.value) {
    loadAgent()
    fetchSubscription()
  } else {
    loadPurchases()
  }
})
watch(() => route.params.id, (id) => {
  agentId.value = id ? parseInt(id, 10) : null
  loadAgent()
  result.value = null
})
</script>

<style scoped>
.run-agent { max-width: 720px; }
.loading, .error { color: var(--wm-text-muted); margin: 1rem 0; }
.error { color: var(--wm-danger); }
.run-form { display: flex; flex-direction: column; gap: 1rem; margin-top: 1rem; }
.agent-info h2 { font-size: 1.25rem; margin-bottom: 0.25rem; }
.agent-info p { color: var(--wm-text-muted); font-size: 0.9rem; }
.field label { display: block; margin-bottom: 0.25rem; }
.field textarea, .field select { width: 100%; padding: 0.5rem; border-radius: 6px; border: 1px solid var(--wm-border); background: var(--wm-bg-soft); color: var(--wm-text); }
.hint { font-size: 0.8rem; color: var(--wm-text-muted); margin-top: 0.25rem; }
.btn { padding: 0.75rem 1.5rem; border-radius: 8px; border: none; cursor: pointer; }
.btn.primary { background: var(--wm-primary); color: var(--wm-white); }
.btn:disabled { opacity: 0.6; cursor: not-allowed; }
.result { margin-top: 2rem; padding: 1rem; background: var(--wm-bg-soft); border-radius: 8px; border: 1px solid var(--wm-border); }
.result h3 { margin-bottom: 0.5rem; }
.output { white-space: pre-wrap; word-break: break-word; color: var(--wm-text); font-size: 0.9rem; }
.usage { margin-top: 0.5rem; font-size: 0.8rem; color: var(--wm-text-muted); }
.estimate { font-size: 0.85rem; color: var(--wm-accent); margin-top: 0.25rem; }
.quota { font-size: 0.85rem; color: var(--wm-text-muted); margin-top: 0.25rem; }
.pick-agent h2 { font-size: 1rem; margin-bottom: 0.5rem; }
.chain-hint { font-size: 0.9rem; color: var(--wm-text-muted); margin-bottom: 1rem; }
.chain-hint a { color: var(--wm-accent); text-decoration: none; }
.chain-hint a:hover { text-decoration: underline; }
.purchase-list { list-style: none; padding: 0; }
.purchase-list li { margin: 0.5rem 0; }
.purchase-list a { color: var(--wm-accent); text-decoration: none; }
.purchase-list a:hover { text-decoration: underline; }
</style>

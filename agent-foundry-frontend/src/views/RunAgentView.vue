<template>
  <div class="run-agent mx-auto" style="max-width: 720px;">
    <h1 class="text-h4 mb-4">Run AI Role</h1>
    <div v-if="!agent && agentId" class="text-medium-emphasis my-4">Loading AI role...</div>
    <div v-else-if="!agent && !agentId" class="pick-agent">
      <h2 class="text-h6 mb-2">Choose an AI role to run</h2>
      <p class="text-body-2 text-medium-emphasis mb-4">
        <router-link to="/chains" class="text-accent text-decoration-none">Or build an AI team</router-link> of AI roles.
      </p>
      <template v-if="myAgents.length">
        <h3 class="text-subtitle-1 mb-2">Your AI roles</h3>
        <ul class="pa-0 ma-0 mb-4" style="list-style: none;">
          <li v-for="a in myAgents" :key="a.id" class="py-2">
            <router-link :to="`/run/${a.id}`" class="text-accent text-decoration-none">{{ a.name }}</router-link>
            <span v-if="a.status !== 'listed'" class="text-caption text-medium-emphasis ml-2">({{ a.status }})</span>
          </li>
        </ul>
      </template>
      <h3 class="text-subtitle-1 mb-2">Purchased AI roles</h3>
      <div v-if="purchasesLoading" class="mb-4">Loading...</div>
      <ul v-else class="purchase-list pa-0 ma-0 mb-4" style="list-style: none;">
        <li v-for="p in purchases" :key="p.agent_id" class="py-2">
          <router-link :to="`/run/${p.agent_id}`" class="text-accent text-decoration-none">{{ p.agent_name || `AI Role #${p.agent_id}` }}</router-link>
        </li>
      </ul>
      <p v-if="!purchasesLoading && purchases.length === 0 && !myAgents.length" class="text-medium-emphasis">No AI roles to run. <router-link to="/marketplace" class="text-accent text-decoration-none">Browse marketplace</router-link> or <router-link to="/dashboard/agents" class="text-accent text-decoration-none">create an AI role</router-link>.</p>
    </div>
    <div v-else-if="!agent" class="text-error my-4">AI Role not found.</div>
    <v-form v-else @submit.prevent="run" class="d-flex flex-column gap-4 mt-4">
      <div class="agent-info">
        <h2 class="text-h6 mb-1">{{ agent.name }}</h2>
        <p class="text-body-2 text-medium-emphasis">{{ agent.description }}</p>
      </div>
      <v-textarea v-model="userInput" label="Input" rows="5" placeholder="Enter your prompt or question..." required density="comfortable" />
      <v-select v-model="model" :items="modelOptions" item-title="title" item-value="value" label="Model" density="comfortable" />
      <div>
        <v-switch v-model="useByok" label="Use my API key (BYOK)" color="primary" hide-details class="byok-switch-high-contrast" />
        <p v-if="useByok" class="text-caption text-medium-emphasis mt-1">
          Make sure you've saved your API key for {{ model.split('/')[0] }}.
          <router-link to="/settings/keys" class="text-accent text-decoration-none">Manage keys</router-link>
        </p>
        <template v-else>
          <p v-if="estimate" class="text-caption text-accent mt-1">Platform estimate: ~${{ estimate.estimated_cost_usd != null ? estimate.estimated_cost_usd.toFixed(4) : 'N/A' }}</p>
          <p v-else-if="subscription" class="text-caption text-medium-emphasis mt-1">Runs remaining: {{ subscription.runs_remaining }}/{{ subscription.runs_per_period }} ({{ subscription.tier }} tier)</p>
        </template>
      </div>
      <v-btn type="submit" color="primary" :loading="running">{{ running ? 'Running...' : 'Run' }}</v-btn>
    </v-form>
    <v-card v-if="result" variant="tonal" class="pa-4 mt-8">
      <h3 class="text-h6 mb-2">Result</h3>
      <pre class="output text-body-2 pa-0 ma-0" style="white-space: pre-wrap; word-break: break-word;">{{ result.content || result.error || 'No output' }}</pre>
      <div v-if="result.usage" class="text-caption text-medium-emphasis mt-2">
        Tokens: {{ result.usage.prompt_tokens }} prompt, {{ result.usage.completion_tokens }} completion
      </div>
    </v-card>
  </div>
</template>

<script setup>
import { ref, onMounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import api from '@/services/api'

const modelOptions = [
  { title: 'OpenAI GPT-5.2', value: 'openai/gpt-5.2' },
  { title: 'OpenAI GPT-5 mini', value: 'openai/gpt-5-mini' },
  { title: 'OpenAI GPT-4.1', value: 'openai/gpt-4.1' },
  { title: 'OpenAI GPT-3.5', value: 'openai/gpt-3.5-turbo' },
  { title: 'Anthropic Claude 3 Sonnet', value: 'anthropic/claude-3-sonnet-20240229' },
  { title: 'Ollama Llama 2 (local)', value: 'ollama/llama2' },
]

const route = useRoute()
const authStore = useAuthStore()
const agentId = ref(route.params.id ? parseInt(route.params.id, 10) : null)
const agent = ref(null)
const userInput = ref('')
const model = ref('openai/gpt-5.2')
const useByok = ref(false)
const running = ref(false)
const result = ref(null)
const purchases = ref([])
const purchasesLoading = ref(false)
const myAgents = ref([])
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

async function loadMyAgents() {
  if (authStore.user?.role !== 'expert' && authStore.user?.role !== 'admin') return
  try {
    const { data } = await api.get('/agents/my')
    myAgents.value = data || []
  } catch {
    myAgents.value = []
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
    loadMyAgents()
  }
})
watch(() => route.params.id, (id) => {
  agentId.value = id ? parseInt(id, 10) : null
  loadAgent()
  result.value = null
  if (!agentId.value) {
    loadPurchases()
    loadMyAgents()
  }
})
</script>

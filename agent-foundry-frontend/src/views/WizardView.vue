<template>
  <div class="wizard-view mx-auto" style="max-width: 720px;">
    <h1 class="text-h4 mb-2">Set up your AI Team</h1>
    <p class="text-body-2 text-medium-emphasis mb-4">
      Choose what you want to achieve, fill in the details, and get results right away.
    </p>

    <v-stepper v-model="step" flat class="wizard-stepper" :items="['What do you want to achieve?', 'Enter parameters', 'Run and view result']">
      <template v-slot:item.1>
          <div v-if="useCasesLoading" class="text-medium-emphasis py-6">Loading use cases...</div>
          <div v-else-if="!useCases.length" class="text-medium-emphasis py-6">
            No use cases configured. Contact your admin to set up the wizard.
          </div>
          <div v-else class="use-case-grid py-4">
            <v-card
              v-for="uc in useCases"
              :key="uc.id"
              variant="tonal"
              :class="{ 'selected-use-case': selectedUseCase?.id === uc.id }"
              class="use-case-card pa-4 cursor-pointer"
              @click="selectUseCase(uc)"
            >
              <h3 class="text-h6 mb-2">{{ uc.label }}</h3>
              <p v-if="uc.description" class="text-body-2 text-medium-emphasis mb-0">{{ uc.description }}</p>
              <v-chip v-if="!uc.chain_id" size="x-small" color="warning" class="mt-2">Chain not found (slug: {{ uc.chain_slug }})</v-chip>
            </v-card>
          </div>
          <v-btn v-if="selectedUseCase?.chain_id" color="primary" class="mt-2" @click="step = 2">Next</v-btn>
      </template>

      <template v-slot:item.2>
          <div v-if="selectedUseCase?.inject_as === 'run_history'" class="py-6">
            <p class="text-body-2">This use case requires selecting prior runs. Use <router-link to="/runs" class="text-accent text-decoration-none">Run history</router-link> and click "Create report" to compare runs.</p>
          </div>
          <v-form v-else ref="paramsFormRef" @submit.prevent="submitAndRun" class="py-4">
            <div v-if="selectedUseCase?.required_config?.length" class="mb-4 pa-4" style="border-radius: 8px; background: rgba(var(--v-theme-surface-variant), 0.3); border: 1px solid rgba(var(--v-border-color), 0.5);">
              <h4 class="text-subtitle-1 mb-2">Required setup</h4>
              <p class="text-caption text-medium-emphasis mb-3">This use case needs the following configured before you can run it.</p>
              <div class="d-flex flex-column gap-2">
                <div v-for="key in selectedUseCase.required_config" :key="key" class="d-flex align-center gap-2">
                  <v-icon v-if="configStatus[key]" color="success" size="small">mdi-check-circle</v-icon>
                  <v-icon v-else color="warning" size="small">mdi-alert-circle</v-icon>
                  <span class="text-body-2">{{ configLabel(key) }}</span>
                  <template v-if="!configStatus[key]">
                    <v-btn size="small" variant="tonal" :to="configLink(key)" target="_blank" rel="noopener">Configure</v-btn>
                  </template>
                </div>
              </div>
              <p v-if="!hasRequiredConfig" class="text-caption text-warning mt-2 mb-0 d-flex align-center gap-2">
                Add the required config above, then
                <v-btn size="x-small" variant="text" @click="fetchConfigStatus(selectedUseCase.required_config)">Re-check</v-btn>
                to update status.
              </p>
            </div>
            <div v-if="selectedUseCase?.params?.length" class="d-flex flex-column gap-3 mb-4">
              <template v-for="(p, idx) in selectedUseCase.params" :key="p.slug">
                <v-text-field
                  v-if="p.type === 'text'"
                  v-model="paramValues[p.slug]"
                  :label="p.label"
                  :placeholder="p.placeholder"
                  :required="p.required"
                  density="comfortable"
                  :rules="paramRules(p)"
                />
                <v-text-field
                  v-else-if="p.type === 'date'"
                  v-model="paramValues[p.slug]"
                  :label="p.label"
                  type="date"
                  :required="p.required"
                  density="comfortable"
                  :rules="paramRules(p)"
                />
                <v-select
                  v-else-if="p.type === 'select'"
                  v-model="paramValues[p.slug]"
                  :label="p.label"
                  :items="p.options || []"
                  :required="p.required"
                  density="comfortable"
                  :rules="paramRules(p)"
                />
                <v-text-field
                  v-else
                  v-model="paramValues[p.slug]"
                  :label="p.label"
                  :required="p.required"
                  density="comfortable"
                  :rules="paramRules(p)"
                />
              </template>
            </div>
            <div v-else class="text-body-2 text-medium-emphasis py-4">No parameters required for this use case.</div>
            <v-select v-model="runModel" :items="modelOptions" item-title="title" item-value="value" label="Model" density="comfortable" class="mb-3" />
            <v-switch v-model="runByok" label="Use my API key (BYOK)" color="primary" hide-details class="mb-3" />
            <div class="d-flex gap-2">
              <v-btn variant="outlined" @click="step = 1">Back</v-btn>
              <v-btn type="submit" color="primary" :loading="running" :disabled="!canRun" :title="!hasRequiredConfig ? 'Configure required setup first' : ''">
                {{ running ? 'Running...' : 'Run' }}
              </v-btn>
            </div>
          </v-form>
      </template>

      <template v-slot:item.3>
          <div v-if="running" class="py-6 text-center">
            <v-progress-circular indeterminate color="primary" size="48" class="mb-3" />
            <p class="text-body-2">Your AI Team is running...</p>
          </div>
          <div v-else-if="runResult" class="py-4">
            <v-alert v-if="runResult.error" type="error" variant="tonal" class="mb-4">{{ runResult.error }}</v-alert>
            <v-card v-else variant="tonal" class="pa-4 mb-4">
              <h3 class="text-h6 mb-2">Result</h3>
              <FormattedOutput :content="runResult.content" fallback="No output" class="output" />
              <div v-if="runResult.usage" class="text-caption text-medium-emphasis mt-2">
                Tokens: {{ runResult.usage.prompt_tokens }} prompt, {{ runResult.usage.completion_tokens }} completion
              </div>
            </v-card>
            <div class="d-flex gap-2">
              <v-btn variant="outlined" @click="step = 1; selectedUseCase = null; runResult = null">Start over</v-btn>
              <v-btn color="primary" :to="{ path: '/runs', query: runResult.run_id ? { open: runResult.run_id } : {} }">View in Run history</v-btn>
            </div>
          </div>
      </template>
    </v-stepper>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import api from '@/services/api'
import FormattedOutput from '@/components/FormattedOutput.vue'

const router = useRouter()
const step = ref(1)
const useCases = ref([])
const useCasesLoading = ref(true)
const selectedUseCase = ref(null)
const paramValues = ref({})
const paramsFormRef = ref(null)
const runModel = ref('openai/gpt-5.2')
const runByok = ref(false)
const running = ref(false)
const runResult = ref(null)
const configStatus = ref({})
let pollInterval = null

const CONFIG_LABELS = { github_token: 'GitHub token' }
const CONFIG_LINKS = { github_token: '/settings/keys' }

const modelOptions = [
  { title: 'OpenAI GPT-5.2', value: 'openai/gpt-5.2' },
  { title: 'OpenAI GPT-5 mini', value: 'openai/gpt-5-mini' },
  { title: 'OpenAI GPT-4.1', value: 'openai/gpt-4.1' },
  { title: 'Anthropic Claude 3 Sonnet', value: 'anthropic/claude-3-sonnet-20240229' },
]

const hasRequiredConfig = computed(() => {
  const uc = selectedUseCase.value
  const req = uc?.required_config || []
  return req.every((k) => configStatus.value[k])
})

const canRun = computed(() => {
  const uc = selectedUseCase.value
  if (!uc?.chain_id) return false
  if (uc.inject_as === 'run_history') return false
  if (!hasRequiredConfig.value) return false
  const params = uc.params || []
  for (const p of params) {
    if (p.required && !(paramValues.value[p.slug] || '').trim()) return false
  }
  return true
})

function configLabel(key) {
  return CONFIG_LABELS[key] || key
}

function configLink(key) {
  return CONFIG_LINKS[key] || '/settings/keys'
}

function paramRules(p) {
  const rules = []
  if (p.required) {
    rules.push((v) => !!v || `${p.label} is required`)
  }
  if (p.validation === 'ethereum_address') {
    rules.push((v) => {
      if (!v) return true
      return /^0x[a-fA-F0-9]{40}$/.test(v.trim()) || 'Must be a valid 0x-prefixed 40-char hex address'
    })
  }
  return rules
}

function selectUseCase(uc) {
  selectedUseCase.value = uc
  paramValues.value = {}
  const params = uc.params || []
  for (const p of params) {
    paramValues.value[p.slug] = p.default ?? ''
  }
  fetchConfigStatus(uc.required_config || [])
}

async function fetchConfigStatus(keys) {
  if (!keys.length) {
    configStatus.value = {}
    return
  }
  try {
    const { data } = await api.get('/wizard/config-status', { params: { keys: keys.join(',') } })
    configStatus.value = data || {}
  } catch {
    configStatus.value = Object.fromEntries(keys.map((k) => [k, false]))
  }
}

async function loadUseCases() {
  useCasesLoading.value = true
  try {
    const { data } = await api.get('/wizard/use-cases')
    useCases.value = data || []
  } catch (e) {
    console.error(e)
    useCases.value = []
  } finally {
    useCasesLoading.value = false
  }
}

function buildUserInput() {
  const uc = selectedUseCase.value
  const params = uc.params || []
  const parts = params.map((p) => `${p.label}: ${paramValues.value[p.slug] || ''}`).filter(Boolean)
  return parts.join(' | ') + '\n\nPlease analyse and report based on the parameters above.'
}

async function submitAndRun() {
  const uc = selectedUseCase.value
  if (!uc?.chain_id || uc.inject_as === 'run_history') return
  const { valid } = await paramsFormRef.value?.validate()
  if (!valid) return

  running.value = true
  runResult.value = null
  step.value = 3

  try {
    if (uc.inject_as === 'slugs') {
      for (const p of uc.params || []) {
        const val = paramValues.value[p.slug]
        if (val != null && String(val).trim()) {
          await api.put(`/saved-outputs/${p.slug}`, { content: String(val).trim() })
        }
      }
    }
    const userInput = uc.inject_as === 'user_input' ? buildUserInput() : ''
    const { data } = await api.post(`/chains/${uc.chain_id}/run`, {
      user_input: userInput,
      model: runModel.value,
      use_byok: runByok.value,
    })
    if (data.job_id) {
      pollInterval = setInterval(() => pollRun(data.job_id, data.run_id), 1500)
    } else {
      runResult.value = { error: 'No job_id returned' }
      running.value = false
    }
  } catch (e) {
    runResult.value = { error: e.response?.data?.detail || e.message || 'Run failed' }
    running.value = false
  }
}

async function pollRun(jobId, runId) {
  try {
    const { data } = await api.get(`/chains/runs/${jobId}`)
    if (data.status === 'completed') {
      clearInterval(pollInterval)
      pollInterval = null
      runResult.value = { content: data.content, usage: data.usage, run_id: runId }
      running.value = false
    } else if (data.status === 'error') {
      clearInterval(pollInterval)
      pollInterval = null
      runResult.value = { error: data.error || 'Run failed', run_id: runId }
      running.value = false
    } else if (data.status === 'awaiting_approval') {
      clearInterval(pollInterval)
      pollInterval = null
      runResult.value = {
        error: 'This run requires approval. Use Run history to approve and continue.',
        run_id: runId,
      }
      running.value = false
    }
  } catch (e) {
    clearInterval(pollInterval)
    pollInterval = null
    runResult.value = { error: 'Failed to get result' }
    running.value = false
  }
}

watch(selectedUseCase, (uc) => {
  runResult.value = null
  if (uc?.required_config?.length) fetchConfigStatus(uc.required_config)
})
watch(step, (s) => {
  if (s === 2 && selectedUseCase.value?.required_config?.length) {
    fetchConfigStatus(selectedUseCase.value.required_config)
  }
})

onMounted(loadUseCases)
</script>

<style scoped>
.use-case-grid {
  display: grid;
  gap: 1rem;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
}
.use-case-card {
  transition: box-shadow 0.2s, border-color 0.2s;
}
.use-case-card:hover {
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
}
.use-case-card.selected-use-case {
  border: 2px solid rgb(var(--v-theme-primary));
}
.cursor-pointer {
  cursor: pointer;
}
.output {
  max-height: 360px;
  overflow-y: auto;
  font-size: 0.875rem;
}
</style>

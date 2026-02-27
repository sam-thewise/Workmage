<template>
  <div class="chain-builder pa-4">
    <div class="toolbar d-flex flex-wrap align-center gap-2 mb-3">
      <v-text-field v-model="chainName" placeholder="Chain name" density="compact" hide-details style="max-width: 200px;" />
      <v-text-field v-model="chainCategory" placeholder="Category" density="compact" hide-details style="max-width: 140px;" />
      <v-text-field v-model.number="chainPriceCents" type="number" min="0" placeholder="Price (cents)" density="compact" hide-details style="max-width: 120px;" />
      <v-btn color="primary" size="small" :loading="saving" :disabled="!chainName.trim()" @click="saveChain">
        {{ saving ? 'Saving...' : 'Save' }}
      </v-btn>
      <v-btn v-if="chainId && chainStatus !== 'pending_review' && chainStatus !== 'listed'" size="small" color="success" @click="publishChain">Publish</v-btn>
      <v-btn v-if="chainId && (chainStatus === 'pending_review' || chainStatus === 'listed')" size="small" variant="outlined" @click="unpublishChain">Unpublish</v-btn>
      <v-btn v-if="chainId" size="small" variant="tonal" @click="showRunModal = true">Run</v-btn>
      <v-chip v-if="chainStatus" size="x-small" :color="chainStatus === 'listed' ? 'success' : 'secondary'">{{ chainStatus }}</v-chip>
      <span v-if="rejectionReason" class="text-error text-caption">{{ rejectionReason }}</span>
      <span v-if="saveError" class="text-error text-caption">{{ saveError }}</span>
    </div>
    <v-textarea v-model="chainDescription" rows="2" placeholder="Chain description" density="compact" hide-details class="mb-2" />
    <v-text-field v-model="chainTagsText" placeholder="Tags comma-separated (e.g. sales, research)" density="compact" hide-details class="mb-3" />
    <div class="builder-layout">
      <div class="palette">
        <h3>Agents</h3>
        <p class="hint">Drag to canvas or click to add</p>
        <details class="help" open>
          <summary>How to use</summary>
          <ul>
            <li><strong>First input:</strong> Save the chain, then click <em>Run</em>. Enter your prompt in the modal. Entry agents (with "Start" badge) receive it.</li>
            <li><strong>Connect:</strong> Click the right dot (output) of one node, then click the left dot (input) of another. Or drag from right to left.</li>
            <li><strong>Move:</strong> Drag the node body (not the circles).</li>
            <li><strong>Bottom buttons:</strong> + Zoom in, − Zoom out, ⊡ Fit view, ⊙/⊘ Lock pan.</li>
          </ul>
        </details>
        <ul class="agent-palette">
          <li
            v-for="a in availableAgents"
            :key="a.id"
            class="palette-item"
            draggable="true"
            @dragstart="onDragStart($event, a)"
            @click="addAgentNode(a)"
          >
            {{ a.name || `Agent #${a.id}` }}
          </li>
        </ul>
        <p v-if="!availableAgents.length" class="empty">No listed agents available.</p>
      </div>
      <div class="canvas-wrap" @dragover.prevent @drop="onDrop">
        <VueFlow
          v-model:nodes="nodes"
          v-model:edges="edges"
          :default-viewport="{ x: 0, y: 0, zoom: 1 }"
          :node-types="nodeTypes"
          :nodes-connectable="true"
          :connect-on-click="true"
          :connection-mode="ConnectionMode.Strict"
          :is-valid-connection="isValidConnection"
          @connect="onConnect"
          @connect-start="onConnectStart"
          fit-view-on-init
          class="vue-flow-canvas"
        >
          <Background />
          <FlowControls />
        </VueFlow>
      </div>
    </div>

    <v-dialog v-model="showRunModal" max-width="500" persistent>
      <v-card class="pa-4">
        <h3 class="text-h6 mb-4">Run Chain</h3>
        <v-textarea v-model="runInput" rows="4" placeholder="Enter your prompt..." label="Input (for entry agents)" density="comfortable" class="mb-3" />
        <v-select v-model="runModel" :items="runModelOptions" item-title="title" item-value="value" label="Model" density="comfortable" class="mb-3" />
        <v-checkbox v-model="runByok" label="Use my API key (BYOK)" density="compact" hide-details class="mb-4" />
        <div class="d-flex gap-2">
          <v-btn variant="outlined" @click="showRunModal = false">Cancel</v-btn>
          <v-btn color="primary" :loading="running" :disabled="running" @click="runChain">Run</v-btn>
        </div>
        <v-card v-if="runResult" variant="tonal" class="pa-3 mt-4">
          <pre class="text-body-2 ma-0" style="white-space: pre-wrap;">{{ runResult.content || runResult.error || 'No output' }}</pre>
        </v-card>
      </v-card>
    </v-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { VueFlow, Handle, ConnectionMode } from '@vue-flow/core'
import { Background } from '@vue-flow/background'
import FlowControls from '@/components/FlowControls.vue'
import AgentNode from '@/components/AgentNode.vue'
import { useAuthStore } from '@/stores/auth'
import '@vue-flow/core/dist/style.css'
import '@vue-flow/core/dist/theme-default.css'
import api from '@/services/api'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
const chainId = ref(route.params.id && route.params.id !== 'new' ? parseInt(route.params.id, 10) : null)
const chainName = ref('')
const chainDescription = ref('')
const chainPriceCents = ref(0)
const chainCategory = ref('')
const chainTagsText = ref('')
const chainStatus = ref('draft')
const rejectionReason = ref('')
const availableAgents = ref([])
const nodes = ref([])
const edges = ref([])
const saving = ref(false)
const saveError = ref('')
const showRunModal = ref(false)
const runInput = ref('')
const runModel = ref('openai/gpt-4')
const runByok = ref(false)
const running = ref(false)
const runResult = ref(null)
const runModelOptions = [
  { title: 'OpenAI GPT-4', value: 'openai/gpt-4' },
  { title: 'OpenAI GPT-3.5', value: 'openai/gpt-3.5-turbo' },
  { title: 'Anthropic Claude 3 Sonnet', value: 'anthropic/claude-3-sonnet-20240229' },
]
let nodeIdCounter = 0
let pollInterval = null
const compatibilityCache = ref({})
const connectStartSource = ref(null)

const nodeTypes = { agent: AgentNode }


async function loadAvailableAgents() {
  try {
    const { data } = await api.get('/agents')
    availableAgents.value = data || []
  } catch {
    availableAgents.value = []
  }
}

async function loadChain() {
  if (!chainId.value) return
  try {
    const { data } = await api.get(`/chains/${chainId.value}`)
    chainName.value = data.name
    chainDescription.value = data.description || ''
    chainPriceCents.value = data.price_cents || 0
    chainCategory.value = data.category || ''
    chainTagsText.value = (data.tags || []).join(', ')
    chainStatus.value = data.status || 'draft'
    rejectionReason.value = data.rejection_reason || ''
    const defn = data.definition || {}
    const loadedEdges = defn.edges || []
    const targetIds = new Set(loadedEdges.map(e => e.target))
    nodes.value = (defn.nodes || []).map(n => ({
      id: n.id,
      type: 'agent',
      position: n.position || { x: 0, y: 0 },
      data: {
        label: getAgentLabel(n.agent_id, data.agents),
        agent_id: n.agent_id,
        isEntry: !targetIds.has(n.id),
      },
      dragHandle: '.agent-node-content',
    }))
    edges.value = loadedEdges.map(e => ({
      id: `e-${e.source}-${e.target}`,
      source: e.source,
      target: e.target,
    }))
  } catch {
    nodes.value = []
    edges.value = []
  }
}

function getAgentLabel(agentId, agents) {
  const a = (agents || []).find(x => x.id === agentId)
  return a ? a.name : `Agent #${agentId}`
}

function addAgentNode(a, position) {
  const id = `n${++nodeIdCounter}`
  const defaultPos = position || { x: 100 + nodes.value.length * 200, y: 150 }
  const targetIds = new Set(edges.value.map(e => e.target))
  const isEntry = !targetIds.has(id)
  nodes.value = [...nodes.value, {
    id,
    type: 'agent',
    position: defaultPos,
    data: { label: a.name || `Agent #${a.id}`, agent_id: a.id, isEntry },
    dragHandle: '.agent-node-content',
  }]
}

function refreshEntryBadges() {
  const targetIds = new Set(edges.value.map(e => e.target))
  nodes.value = nodes.value.map(n => ({
    ...n,
    data: { ...n.data, isEntry: !targetIds.has(n.id) },
  }))
}

function onDragStart(ev, a) {
  ev.dataTransfer.setData('application/json', JSON.stringify({ agent_id: a.id, agent_name: a.name }))
}

function onDrop(ev) {
  ev.preventDefault()
  try {
    const raw = ev.dataTransfer.getData('application/json')
    if (!raw) return
    const p = JSON.parse(raw)
    const rect = ev.currentTarget.getBoundingClientRect()
    addAgentNode({
      agent_id: p.agent_id,
      agent_name: p.agent_name || `Agent #${p.agent_id}`,
    }, { x: ev.clientX - rect.left - 100, y: ev.clientY - rect.top - 30 })
  } catch (_) {}
}

async function onConnectStart({ nodeId }) {
  connectStartSource.value = nodeId
  const srcNode = nodes.value.find(n => n.id === nodeId)
  if (!srcNode) return
  const srcAgentId = srcNode.data?.agent_id
  for (const n of nodes.value) {
    if (n.id !== nodeId && n.data?.agent_id) {
      const key = `${srcAgentId}-${n.data.agent_id}`
      if (compatibilityCache.value[key] === undefined) {
        try {
          const { data } = await api.get('/chains/compatibility', {
            params: { agent_a: srcAgentId, agent_b: n.data.agent_id },
          })
          compatibilityCache.value[key] = data.compatible
        } catch {
          /* On API error, allow connection so users aren't blocked */
          compatibilityCache.value[key] = true
        }
      }
    }
  }
}

function isValidConnection(params) {
  const srcNode = nodes.value.find(n => n.id === params.source)
  const tgtNode = nodes.value.find(n => n.id === params.target)
  if (!srcNode?.data?.agent_id || !tgtNode?.data?.agent_id) return false
  const key = `${srcNode.data.agent_id}-${tgtNode.data.agent_id}`
  const compat = compatibilityCache.value[key]
  if (compat === false) return false
  if (compat === undefined) return true
  return compat
}

function onConnect(params) {
  const srcNode = nodes.value.find(n => n.id === params.source)
  const tgtNode = nodes.value.find(n => n.id === params.target)
  if (!srcNode || !tgtNode) return
  const key = `${srcNode.data?.agent_id}-${tgtNode.data?.agent_id}`
  if (compatibilityCache.value[key] === false) {
    setTimeout(() => {
      edges.value = edges.value.filter(e => !(e.source === params.source && e.target === params.target))
      alert('These agents are not compatible (output/input format mismatch)')
    }, 0)
    return
  }
  /* Vue Flow emits @connect but does not add the edge when using v-model - we must add it */
  const edgeId = `e-${params.source}-${params.target}`
  if (!edges.value.some(e => e.source === params.source && e.target === params.target)) {
    edges.value = [...edges.value, {
      id: edgeId,
      source: params.source,
      target: params.target,
      sourceHandle: params.sourceHandle ?? undefined,
      targetHandle: params.targetHandle ?? undefined,
    }]
  }
  refreshEntryBadges()
}

function buildDefinition() {
  const targetIds = new Set(edges.value.map(e => e.target))
  return {
    nodes: nodes.value.map(n => ({
      id: n.id,
      agent_id: n.data.agent_id,
      position: n.position,
      role: !targetIds.has(n.id) ? 'entry' : undefined,
    })),
    edges: edges.value.map(e => ({
      source: e.source,
      target: e.target,
      source_port: 'output',
      target_port: 'input',
    })),
  }
}

async function saveChain() {
  if (!chainName.value.trim()) return
  saving.value = true
  saveError.value = ''
  const defn = buildDefinition()
  try {
    if (chainId.value) {
      await api.put(`/chains/${chainId.value}`, {
        name: chainName.value,
        description: chainDescription.value || null,
        price_cents: Math.max(0, Number(chainPriceCents.value) || 0),
        category: chainCategory.value || null,
        tags: chainTagsText.value ? chainTagsText.value.split(',').map((t) => t.trim()).filter(Boolean) : [],
        definition: defn,
      })
    } else {
      const { data } = await api.post('/chains', {
        name: chainName.value,
        description: chainDescription.value || null,
        price_cents: Math.max(0, Number(chainPriceCents.value) || 0),
        category: chainCategory.value || null,
        tags: chainTagsText.value ? chainTagsText.value.split(',').map((t) => t.trim()).filter(Boolean) : [],
        definition: defn,
      })
      chainId.value = data.id
      chainStatus.value = data.status || 'draft'
      router.replace({ name: 'chain-edit', params: { id: String(data.id) } })
    }
  } catch (e) {
    saveError.value = e.response?.data?.detail?.message || e.response?.data?.detail || 'Save failed'
  } finally {
    saving.value = false
  }
}

async function publishChain() {
  if (!chainId.value) return
  try {
    await saveChain()
    await api.patch(`/chains/${chainId.value}/publish`)
    await loadChain()
  } catch (e) {
    saveError.value = e.response?.data?.detail || 'Failed to publish'
  }
}

async function unpublishChain() {
  if (!chainId.value) return
  try {
    await api.patch(`/chains/${chainId.value}/unpublish`)
    await loadChain()
  } catch (e) {
    saveError.value = e.response?.data?.detail || 'Failed to unpublish'
  }
}

async function runChain() {
  if (!chainId.value || !runInput.value.trim()) return
  running.value = true
  runResult.value = null
  try {
    const { data } = await api.post(`/chains/${chainId.value}/run`, {
      user_input: runInput.value,
      model: runModel.value,
      use_byok: runByok.value,
    })
    if (data.job_id) {
      pollInterval = setInterval(() => pollRun(data.job_id), 1500)
    }
  } catch (e) {
    runResult.value = { error: e.response?.data?.detail || 'Run failed' }
    running.value = false
  }
}

async function pollRun(jobId) {
  try {
    const { data } = await api.get(`/chains/runs/${jobId}`)
    if (data.status === 'completed') {
      clearInterval(pollInterval)
      pollInterval = null
      runResult.value = { content: data.content, usage: data.usage }
      running.value = false
    } else if (data.status === 'error') {
      clearInterval(pollInterval)
      pollInterval = null
      runResult.value = { error: data.error || 'Run failed' }
      running.value = false
    }
  } catch (e) {
    clearInterval(pollInterval)
    pollInterval = null
    runResult.value = { error: 'Failed to get result' }
    running.value = false
  }
}

onMounted(async () => {
  if (!authStore.user) await authStore.fetchUser()
  if (authStore.user?.role !== 'expert') {
    router.replace('/dashboard')
    return
  }
  loadAvailableAgents()
  loadChain()
})
watch(() => route.params.id, (id) => {
  chainId.value = id && id !== 'new' ? parseInt(id, 10) : null
  loadChain()
})
</script>

<style scoped>
.chain-builder { display: flex; flex-direction: column; height: calc(100vh - 140px); min-height: 400px; }
.builder-layout { display: flex; flex: 1; min-height: 0; gap: 1rem; }
.palette { width: 200px; flex-shrink: 0; background: var(--wm-bg-soft); border-radius: 8px; padding: 1rem; border: 1px solid var(--wm-border); }
.palette h3 { margin: 0 0 0.5rem; font-size: 1rem; }
.hint { font-size: 0.8rem; color: var(--wm-text-muted); margin-bottom: 0.5rem; }
.help { font-size: 0.8rem; color: var(--wm-text-muted); margin: 0.5rem 0; }
.help summary { cursor: pointer; color: var(--wm-accent); }
.help ul { margin: 0.5rem 0; padding-left: 1.2rem; }
.help li { margin: 0.25rem 0; }
.agent-palette { list-style: none; padding: 0; }
.palette-item { padding: 0.5rem; cursor: grab; border-radius: 6px; margin-bottom: 0.25rem; background: var(--wm-bg); }
.palette-item:hover { background: var(--wm-border); }
.palette-item:active { cursor: grabbing; }
.empty { font-size: 0.85rem; color: var(--wm-text-muted); }
.empty a { color: var(--wm-accent); }
.canvas-wrap { flex: 1; background: var(--wm-bg); border-radius: 8px; border: 1px solid var(--wm-border); }
.vue-flow-canvas { width: 100%; height: 100%; }
.agent-node { padding: 0.5rem 1rem; background: var(--wm-bg-soft); border: 1px solid var(--wm-border); border-radius: 8px; min-width: 120px; position: relative; }
.agent-node-content { display: flex; align-items: center; gap: 0.5rem; }
.badge { font-size: 0.7rem; background: var(--wm-primary); color: var(--wm-white); padding: 0.15rem 0.4rem; border-radius: 4px; }
</style>

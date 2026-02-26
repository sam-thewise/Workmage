<template>
  <div class="chain-builder">
    <div class="toolbar">
      <input v-model="chainName" type="text" placeholder="Chain name" class="name-input" />
      <button @click="saveChain" class="btn primary" :disabled="saving || !chainName.trim()">
        {{ saving ? 'Saving...' : 'Save' }}
      </button>
      <button v-if="chainId" @click="showRunModal = true" class="btn run">Run</button>
      <span v-if="saveError" class="error">{{ saveError }}</span>
    </div>
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
            v-for="p in purchases"
            :key="p.agent_id"
            class="palette-item"
            draggable="true"
            @dragstart="onDragStart($event, p)"
            @click="addAgentNode(p)"
          >
            {{ p.agent_name || `Agent #${p.agent_id}` }}
          </li>
        </ul>
        <p v-if="!purchases.length" class="empty">No agents. <router-link to="/marketplace">Purchase agents</router-link>.</p>
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

    <div v-if="showRunModal" class="modal-overlay" @click.self="showRunModal = false">
      <div class="modal">
        <h3>Run Chain</h3>
        <div class="field">
          <label>Input (for entry agents)</label>
          <textarea v-model="runInput" rows="4" placeholder="Enter your prompt..."></textarea>
        </div>
        <div class="field">
          <label>Model</label>
          <select v-model="runModel">
            <option value="openai/gpt-4">OpenAI GPT-4</option>
            <option value="openai/gpt-3.5-turbo">OpenAI GPT-3.5</option>
            <option value="anthropic/claude-3-sonnet-20240229">Anthropic Claude 3 Sonnet</option>
          </select>
        </div>
        <div class="field">
          <label><input type="checkbox" v-model="runByok" /> Use my API key (BYOK)</label>
        </div>
        <div class="modal-actions">
          <button @click="showRunModal = false" class="btn">Cancel</button>
          <button @click="runChain" class="btn primary" :disabled="running">
            {{ running ? 'Running...' : 'Run' }}
          </button>
        </div>
        <div v-if="runResult" class="run-result">
          <pre>{{ runResult.content || runResult.error || 'No output' }}</pre>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { VueFlow, Handle, ConnectionMode } from '@vue-flow/core'
import { Background } from '@vue-flow/background'
import FlowControls from '@/components/FlowControls.vue'
import AgentNode from '@/components/AgentNode.vue'
import '@vue-flow/core/dist/style.css'
import '@vue-flow/core/dist/theme-default.css'
import api from '@/services/api'

const route = useRoute()
const router = useRouter()
const chainId = ref(route.params.id && route.params.id !== 'new' ? parseInt(route.params.id, 10) : null)
const chainName = ref('')
const purchases = ref([])
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
let nodeIdCounter = 0
let pollInterval = null
const compatibilityCache = ref({})
const connectStartSource = ref(null)

const nodeTypes = { agent: AgentNode }


async function loadPurchases() {
  try {
    const { data } = await api.get('/purchases/my')
    purchases.value = data || []
  } catch {
    purchases.value = []
  }
}

async function loadChain() {
  if (!chainId.value) return
  try {
    const { data } = await api.get(`/chains/${chainId.value}`)
    chainName.value = data.name
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

function addAgentNode(p, position) {
  const id = `n${++nodeIdCounter}`
  const defaultPos = position || { x: 100 + nodes.value.length * 200, y: 150 }
  const targetIds = new Set(edges.value.map(e => e.target))
  const isEntry = !targetIds.has(id)
  nodes.value = [...nodes.value, {
    id,
    type: 'agent',
    position: defaultPos,
    data: { label: p.agent_name || `Agent #${p.agent_id}`, agent_id: p.agent_id, isEntry },
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

function onDragStart(ev, p) {
  ev.dataTransfer.setData('application/json', JSON.stringify({ agent_id: p.agent_id, agent_name: p.agent_name }))
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
      await api.put(`/chains/${chainId.value}`, { name: chainName.value, definition: defn })
    } else {
      const { data } = await api.post('/chains', { name: chainName.value, definition: defn })
      chainId.value = data.id
      router.replace({ name: 'chain-edit', params: { id: String(data.id) } })
    }
  } catch (e) {
    saveError.value = e.response?.data?.detail?.message || e.response?.data?.detail || 'Save failed'
  } finally {
    saving.value = false
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

onMounted(() => {
  loadPurchases()
  loadChain()
})
watch(() => route.params.id, (id) => {
  chainId.value = id && id !== 'new' ? parseInt(id, 10) : null
  loadChain()
})
</script>

<style scoped>
.chain-builder { display: flex; flex-direction: column; height: calc(100vh - 120px); min-height: 400px; }
.toolbar { display: flex; gap: 0.5rem; align-items: center; margin-bottom: 1rem; flex-wrap: wrap; }
.name-input { padding: 0.5rem; border-radius: 6px; border: 1px solid #444; background: #1a1a2e; color: #fff; width: 200px; }
.btn { padding: 0.5rem 1rem; border-radius: 6px; border: none; cursor: pointer; }
.btn.primary { background: #7c3aed; color: white; }
.btn.run { background: #10b981; color: white; }
.btn:disabled { opacity: 0.6; cursor: not-allowed; }
.error { color: #f87171; font-size: 0.9rem; }
.builder-layout { display: flex; flex: 1; min-height: 0; gap: 1rem; }
.palette { width: 200px; flex-shrink: 0; background: #1e293b; border-radius: 8px; padding: 1rem; border: 1px solid #334155; }
.palette h3 { margin: 0 0 0.5rem; font-size: 1rem; }
.hint { font-size: 0.8rem; color: #64748b; margin-bottom: 0.5rem; }
.help { font-size: 0.8rem; color: #94a3b8; margin: 0.5rem 0; }
.help summary { cursor: pointer; color: #7c3aed; }
.help ul { margin: 0.5rem 0; padding-left: 1.2rem; }
.help li { margin: 0.25rem 0; }
.agent-palette { list-style: none; padding: 0; }
.palette-item { padding: 0.5rem; cursor: grab; border-radius: 6px; margin-bottom: 0.25rem; background: #0f172a; }
.palette-item:hover { background: #334155; }
.palette-item:active { cursor: grabbing; }
.empty { font-size: 0.85rem; color: #64748b; }
.empty a { color: #7c3aed; }
.canvas-wrap { flex: 1; background: #0f172a; border-radius: 8px; border: 1px solid #334155; }
.vue-flow-canvas { width: 100%; height: 100%; }
.agent-node { padding: 0.5rem 1rem; background: #1e293b; border: 1px solid #334155; border-radius: 8px; min-width: 120px; position: relative; }
.agent-node-content { display: flex; align-items: center; gap: 0.5rem; }
.badge { font-size: 0.7rem; background: #7c3aed; padding: 0.15rem 0.4rem; border-radius: 4px; }
.modal-overlay { position: fixed; inset: 0; background: rgba(0,0,0,0.6); display: flex; align-items: center; justify-content: center; z-index: 100; }
.modal { background: #1e293b; padding: 1.5rem; border-radius: 12px; max-width: 500px; width: 90%; max-height: 90vh; overflow-y: auto; }
.modal h3 { margin: 0 0 1rem; }
.field { margin-bottom: 1rem; }
.field label { display: block; margin-bottom: 0.25rem; }
.field textarea, .field select { width: 100%; padding: 0.5rem; border-radius: 6px; border: 1px solid #444; background: #1a1a2e; color: #fff; }
.modal-actions { display: flex; gap: 0.5rem; margin-top: 1rem; }
.run-result { margin-top: 1rem; padding: 1rem; background: #0f172a; border-radius: 6px; max-height: 200px; overflow-y: auto; }
.run-result pre { white-space: pre-wrap; font-size: 0.85rem; margin: 0; }
</style>

<template>
  <div class="chain-builder">
    <div class="chain-builder-header">
      <div class="toolbar d-flex flex-wrap align-center gap-2">
        <v-text-field v-model="chainName" placeholder="Chain name" density="compact" hide-details class="chain-name-input" />
        <v-text-field v-model="chainCategory" placeholder="Category" density="compact" hide-details class="chain-meta-input" />
        <v-text-field v-model.number="chainPriceCents" type="number" min="0" placeholder="Price (cents)" density="compact" hide-details class="chain-meta-input" />
        <v-btn color="primary" size="small" :loading="saving" :disabled="!chainName.trim()" @click="saveChain">Save</v-btn>
        <v-btn v-if="chainId && chainStatus !== 'pending_review' && chainStatus !== 'listed'" size="small" color="success" @click="publishChain">Publish</v-btn>
        <v-btn v-if="chainId && (chainStatus === 'pending_review' || chainStatus === 'listed')" size="small" variant="outlined" @click="unpublishChain">Unpublish</v-btn>
        <v-btn v-if="chainId" size="small" variant="tonal" @click="showRunModal = true">Run</v-btn>
        <v-chip v-if="chainStatus" size="x-small" :color="chainStatus === 'listed' ? 'success' : 'secondary'">{{ chainStatus }}</v-chip>
        <span v-if="rejectionReason" class="text-error text-caption">{{ rejectionReason }}</span>
        <span v-if="saveError" class="text-error text-caption">{{ saveError }}</span>
      </div>
      <div class="chain-meta-row">
        <v-text-field v-model="chainDescription" placeholder="Chain description" density="compact" hide-details class="chain-desc-input" />
        <v-text-field v-model="chainTagsText" placeholder="Tags (e.g. sales, research)" density="compact" hide-details class="chain-tags-input" />
      </div>
    </div>
    <div class="builder-layout">
      <div class="palette">
        <h3>Agents</h3>
        <p class="hint">Drag to canvas or click to add</p>
        <details class="help">
          <summary>How to use</summary>
          <ul>
            <li><strong>Setup lane:</strong> Set an agent's lane to "Setup (first run)" and "Save output to slug" (e.g. personality). Click <em>Run setup</em> to run those agents and save to slugs.</li>
            <li><strong>Main lane:</strong> Add <em>Slug</em> nodes from the palette, connect a slug's output to an agent's input. Click <em>Run main</em> to run the workflow using saved outputs.</li>
            <li><strong>Connect:</strong> Right dot (output) to left dot (input). Slug nodes have only an output.</li>
            <li><strong>Move:</strong> Drag the node body (not the circles).</li>
            <li><strong>Delete:</strong> Select a node and press <kbd>Del</kbd> or <kbd>Backspace</kbd> to remove it.</li>
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
        <p v-if="!availableAgents.length" class="empty">No agents available. Add agents in Dashboard or use listed agents.</p>
        <h3 class="mt-3">Slugs</h3>
        <p class="hint">Add a slug node; connect it to an agent's input to use saved output.</p>
        <div class="d-flex gap-1 mb-2">
          <v-text-field v-model="newSlugName" placeholder="slug name" density="compact" hide-details class="slug-input" />
          <v-btn size="small" variant="tonal" :disabled="!newSlugName.trim()" @click="addSlugNode">Add</v-btn>
        </div>
        <ul v-if="savedSlugs.length" class="slug-palette">
          <li
            v-for="s in savedSlugs"
            :key="s.slug"
            class="palette-item"
            @click="addSlugNodeByName(s.slug)"
          >
            {{ s.slug }}
          </li>
        </ul>
      </div>
      <div v-if="selectedNode" class="node-options pa-3" style="background: var(--wm-bg-soft); border-radius: 8px; border: 1px solid var(--wm-border);">
        <h4 class="text-subtitle-2 mb-2">Node options</h4>
        <template v-if="selectedNode.data?.slug !== undefined">
          <v-text-field v-model="selectedNode.data.slug" label="Slug name" density="compact" hide-details @update:model-value="touchNodes" />
          <v-textarea v-model="selectedNode.data.content" label="Set content (optional)" density="compact" hide-details placeholder="Fixed text for this slug; leave empty to use saved output" rows="3" class="mt-2" @update:model-value="touchNodes" />
          <p class="text-caption text-medium-emphasis mt-1">If set, this slug uses this text instead of saved output when the chain runs.</p>
        </template>
        <template v-else>
          <v-select v-model="selectedNode.data.lane" :items="laneOptions" item-title="title" item-value="value" label="Lane" density="compact" hide-details class="mb-2" @update:model-value="touchNodes" />
          <v-text-field v-if="selectedNode.data.lane === 'setup'" v-model="selectedNode.data.save_to_slug" label="Save output to slug" density="compact" hide-details placeholder="e.g. personality" @update:model-value="touchNodes" />
          <v-text-field v-model="selectedNode.data.input_from_slug" label="Input from slug (optional)" density="compact" hide-details placeholder="e.g. personality" class="mt-2" @update:model-value="touchNodes" />
          <p class="text-caption text-medium-emphasis mt-1">Prefill this agent's input from saved output (same as connecting a slug node).</p>
        </template>
      </div>
      <div
        class="canvas-wrap"
        tabindex="0"
        @dragover.prevent
        @drop="onDrop"
        @keydown="onCanvasKeydown"
      >
        <VueFlow
          v-model:nodes="nodes"
          v-model:edges="edges"
          :default-viewport="{ x: 0, y: 0, zoom: 1 }"
          :node-types="nodeTypes"
          :nodes-connectable="true"
          :connect-on-click="true"
          :connection-mode="ConnectionMode.Strict"
          :is-valid-connection="isValidConnection"
          :nodes-selectable="true"
          @connect="onConnect"
          @connect-start="onConnectStart"
          @node-click="onNodeClick"
          fit-view-on-init
          class="vue-flow-canvas"
        >
          <Background />
          <FlowControls />
        </VueFlow>
      </div>
    </div>

    <v-dialog v-model="showRunModal" max-width="500" persistent class="run-chain-dialog" content-class="run-chain-dialog-content">
      <v-card class="pa-4 run-chain-modal-card">
        <h3 class="text-h6 mb-4">Run Chain</h3>
        <v-textarea v-model="runInput" rows="4" placeholder="Optional: prompt for entry nodes. Leave empty if chain uses only slugs." label="Input" density="comfortable" class="mb-3" />
        <v-select v-model="runModel" :items="runModelOptions" item-title="title" item-value="value" label="Model" density="comfortable" class="mb-3" />
        <v-switch v-model="runByok" label="Use my API key (BYOK)" color="primary" hide-details class="mb-4 byok-switch-high-contrast" />
        <div class="d-flex gap-2 flex-wrap">
          <v-btn variant="outlined" @click="showRunModal = false">Cancel</v-btn>
          <v-btn color="primary" variant="tonal" :loading="running" :disabled="running" @click="runChain(null)">Run main</v-btn>
          <v-btn color="primary" variant="flat" :loading="running" :disabled="running" @click="runChain('setup')">Run setup</v-btn>
        </div>
        <v-card v-if="runResult" variant="tonal" class="pa-3 mt-4">
          <pre class="text-body-2 ma-0" style="white-space: pre-wrap;">{{ runResult.content || runResult.error || 'No output' }}</pre>
        </v-card>
      </v-card>
    </v-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { VueFlow, Handle, ConnectionMode } from '@vue-flow/core'
import { Background } from '@vue-flow/background'
import FlowControls from '@/components/FlowControls.vue'
import AgentNode from '@/components/AgentNode.vue'
import SlugNode from '@/components/SlugNode.vue'
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
const runModel = ref('openai/gpt-5.2')
const runByok = ref(false)
const running = ref(false)
const runResult = ref(null)
const runModelOptions = [
  { title: 'OpenAI GPT-5.2', value: 'openai/gpt-5.2' },
  { title: 'OpenAI GPT-5 mini', value: 'openai/gpt-5-mini' },
  { title: 'OpenAI GPT-4.1', value: 'openai/gpt-4.1' },
  { title: 'OpenAI GPT-3.5', value: 'openai/gpt-3.5-turbo' },
  { title: 'Anthropic Claude 3 Sonnet', value: 'anthropic/claude-3-sonnet-20240229' },
]
let nodeIdCounter = 0
let pollInterval = null
const compatibilityCache = ref({})
const connectStartSource = ref(null)

const nodeTypes = { agent: AgentNode, slug: SlugNode }
const newSlugName = ref('')
const savedSlugs = ref([])
const laneOptions = [
  { title: 'Main', value: 'main' },
  { title: 'Setup (first run)', value: 'setup' },
]

const selectedNode = computed(() => nodes.value.find(n => n.selected) || null)
function touchNodes() {
  nodes.value = [...nodes.value]
}

function onNodeClick({ node }) {
  nodes.value = nodes.value.map(n => ({
    ...n,
    selected: n.id === node.id,
  }))
}

function deleteSelectedNodes() {
  const selectedIds = new Set(nodes.value.filter(n => n.selected).map(n => n.id))
  if (selectedIds.size === 0) return
  nodes.value = nodes.value.filter(n => !selectedIds.has(n.id))
  edges.value = edges.value.filter(e => !selectedIds.has(e.source) && !selectedIds.has(e.target))
  refreshEntryBadges()
}

function onCanvasKeydown(ev) {
  if (ev.key !== 'Delete' && ev.key !== 'Backspace') return
  const target = ev.target
  if (target && (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA' || target.tagName === 'SELECT' || target.isContentEditable)) return
  deleteSelectedNodes()
  ev.preventDefault()
}


async function loadAvailableAgents() {
  try {
    const [publicRes, myRes] = await Promise.all([
      api.get('/agents').then(r => r.data || []).catch(() => []),
      api.get('/agents/my').then(r => r.data || []).catch(() => []),
    ])
    const byId = new Map()
    publicRes.forEach(a => byId.set(a.id, a))
    myRes.forEach(a => byId.set(a.id, a))
    availableAgents.value = Array.from(byId.values())
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
    nodes.value = (defn.nodes || []).map(n => {
      if (n.type === 'slug') {
        return {
          id: n.id,
          type: 'slug',
          position: n.position || { x: 0, y: 0 },
          data: { slug: n.slug || 'slug', content: n.content || '' },
          dragHandle: '.slug-node-content',
        }
      }
      return {
        id: n.id,
        type: 'agent',
        position: n.position || { x: 0, y: 0 },
        data: {
          label: getAgentLabel(n.agent_id, data.agents),
          agent_id: n.agent_id,
          isEntry: !targetIds.has(n.id),
          lane: n.lane || 'main',
          save_to_slug: n.save_to_slug || '',
          input_from_slug: n.input_from_slug || '',
        },
        dragHandle: '.agent-node-content',
      }
    })
    edges.value = loadedEdges.map(e => ({
      id: `e-${e.source}-${e.target}`,
      source: e.source,
      target: e.target,
    }))
    const numIds = (defn.nodes || []).filter(n => n.id && String(n.id).startsWith('n')).map(n => parseInt(String(n.id).slice(1), 10)).filter(n => !isNaN(n))
    if (numIds.length) nodeIdCounter = Math.max(nodeIdCounter, ...numIds)
  } catch {
    nodes.value = []
    edges.value = []
  }
}

function getAgentLabel(agentId, agents) {
  if (agentId == null) return 'Agent #?'
  const a = (agents || []).find(x => x.id === agentId)
  return (a && a.name) ? a.name : `Agent #${agentId}`
}

function addAgentNode(a, position) {
  const agentId = a.id ?? a.agent_id
  const agentName = a.name ?? a.agent_name
  const id = `n${++nodeIdCounter}`
  const defaultPos = position || { x: 100 + nodes.value.length * 200, y: 150 }
  const targetIds = new Set(edges.value.map(e => e.target))
  const isEntry = !targetIds.has(id)
  nodes.value = [...nodes.value, {
    id,
    type: 'agent',
    position: defaultPos,
    data: {
      label: (agentName && String(agentName).trim()) ? agentName : `Agent #${agentId ?? '?'}`,
      agent_id: agentId,
      isEntry,
      lane: 'main',
      save_to_slug: '',
      input_from_slug: '',
    },
    dragHandle: '.agent-node-content',
  }]
}

async function loadSavedSlugs() {
  try {
    const { data } = await api.get('/saved-outputs')
    savedSlugs.value = data || []
  } catch {
    savedSlugs.value = []
  }
}

function addSlugNode() {
  const name = (newSlugName.value || '').trim()
  if (!name) return
  addSlugNodeByName(name)
  newSlugName.value = ''
}

function addSlugNodeByName(slugName) {
  const id = `n${++nodeIdCounter}`
  const defaultPos = { x: 100 + nodes.value.length * 200, y: 150 }
  nodes.value = [...nodes.value, {
    id,
    type: 'slug',
    position: defaultPos,
    data: { slug: slugName, content: '' },
    dragHandle: '.slug-node-content',
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
    addAgentNode(
      { id: p.agent_id, agent_id: p.agent_id, name: p.agent_name, agent_name: p.agent_name },
      { x: ev.clientX - rect.left - 100, y: ev.clientY - rect.top - 30 }
    )
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
  if (!srcNode || !tgtNode) return false
  if (tgtNode.type === 'slug') return false
  if (srcNode.type === 'slug') return true
  if (!srcNode.data?.agent_id || !tgtNode.data?.agent_id) return false
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
  if (srcNode.type !== 'slug' && tgtNode.type !== 'slug') {
  const key = `${srcNode.data?.agent_id}-${tgtNode.data?.agent_id}`
  if (compatibilityCache.value[key] === false) {
    setTimeout(() => {
      edges.value = edges.value.filter(e => !(e.source === params.source && e.target === params.target))
      alert('These agents are not compatible (output/input format mismatch)')
    }, 0)
    return
  }
  }
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
    nodes: nodes.value.map(n => {
      if (n.type === 'slug') {
        return {
          id: n.id,
          type: 'slug',
          slug: (n.data?.slug || '').trim() || 'slug',
          content: (n.data?.content || '').trim() || undefined,
          position: n.position,
          lane: 'main',
        }
      }
      return {
        id: n.id,
        agent_id: n.data?.agent_id,
        position: n.position,
        role: !targetIds.has(n.id) ? 'entry' : undefined,
        lane: n.data?.lane || 'main',
        save_to_slug: n.data?.lane === 'setup' ? (n.data?.save_to_slug || '').trim() || undefined : undefined,
        input_from_slug: (n.data?.input_from_slug || '').trim() || undefined,
      }
    }),
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

async function runChain(runType) {
  if (!chainId.value) return
  /* Allow run with empty input: main lane uses slug content / input_from_slug; setup can use empty prompt */
  running.value = true
  runResult.value = null
  try {
    const { data } = await api.post(`/chains/${chainId.value}/run`, {
      user_input: runInput.value.trim() || '',
      model: runModel.value,
      use_byok: runByok.value,
      run_type: runType || undefined,
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
  const role = authStore.user?.role
  if (role !== 'expert' && role !== 'admin') {
    router.replace('/dashboard')
    return
  }
  loadAvailableAgents()
  loadSavedSlugs()
  loadChain()
})
watch(() => route.params.id, (id) => {
  chainId.value = id && id !== 'new' ? parseInt(id, 10) : null
  loadChain()
})
</script>

<style scoped>
.chain-builder {
  display: flex;
  flex-direction: column;
  height: calc(100vh - 120px);
  min-height: 480px;
  padding: 0.75rem 1rem;
  overflow: hidden;
}
.chain-builder-header {
  flex-shrink: 0;
  margin-bottom: 0.5rem;
}
.toolbar { margin-bottom: 0.25rem; }
.chain-name-input { max-width: 200px; }
.chain-meta-input { max-width: 120px; }
.chain-meta-row {
  display: flex;
  gap: 0.75rem;
  align-items: center;
}
.chain-desc-input { flex: 1; min-width: 160px; max-width: 400px; }
.chain-tags-input { flex: 0 1 200px; min-width: 120px; }
.builder-layout {
  display: flex;
  flex: 1;
  min-height: 0;
  gap: 0.75rem;
  overflow: hidden;
}
.palette {
  width: 200px;
  min-width: 200px;
  flex-shrink: 0;
  background: var(--wm-bg-soft);
  border-radius: 8px;
  padding: 0.75rem;
  border: 1px solid var(--wm-border);
  overflow-y: auto;
  display: flex;
  flex-direction: column;
}
.palette h3 { margin: 0 0 0.35rem; font-size: 0.95rem; }
.hint { font-size: 0.75rem; color: var(--wm-text-muted); margin-bottom: 0.35rem; }
.help { font-size: 0.75rem; color: var(--wm-text-muted); margin: 0.35rem 0; }
.help summary { cursor: pointer; color: var(--wm-accent); }
.help ul { margin: 0.35rem 0; padding-left: 1rem; }
.help li { margin: 0.2rem 0; }
.agent-palette { list-style: none; padding: 0; flex: 0 1 auto; }
.palette-item { padding: 0.4rem 0.5rem; cursor: grab; border-radius: 6px; margin-bottom: 0.2rem; background: var(--wm-bg); font-size: 0.85rem; }
.palette-item:hover { background: var(--wm-border); }
.palette-item:active { cursor: grabbing; }
.empty { font-size: 0.8rem; color: var(--wm-text-muted); }
.empty a { color: var(--wm-accent); }
.slug-input { flex: 1; min-width: 0; }
.slug-palette { list-style: none; padding: 0; }
.node-options {
  flex-shrink: 0;
  width: 220px;
  min-height: 0;
  overflow-y: auto;
}
.canvas-wrap {
  flex: 1;
  min-width: 0;
  min-height: 0;
  background: var(--wm-bg);
  border-radius: 8px;
  border: 1px solid var(--wm-border);
  position: relative;
}
.vue-flow-canvas { width: 100%; height: 100%; position: absolute; inset: 0; }
.agent-node { padding: 0.5rem 1rem; background: var(--wm-bg-soft); border: 1px solid var(--wm-border); border-radius: 8px; min-width: 120px; position: relative; }
.agent-node-content { display: flex; align-items: center; gap: 0.5rem; }
.badge { font-size: 0.7rem; background: var(--wm-primary); color: var(--wm-white); padding: 0.15rem 0.4rem; border-radius: 4px; }

/* Run Chain modal: opaque overlay and card so canvas doesn't show through */
.run-chain-modal-card {
  background: rgb(var(--v-theme-surface)) !important;
  border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
}

/* BYOK switch: force visible track and thumb on dark background */
.run-chain-modal-card :deep(.byok-switch-high-contrast .v-switch__track) {
  background: rgba(255, 255, 255, 0.2) !important;
}
.run-chain-modal-card :deep(.byok-switch-high-contrast .v-selection-control--dirty .v-switch__track) {
  background: rgb(var(--v-theme-primary)) !important;
  opacity: 1 !important;
}
.run-chain-modal-card :deep(.byok-switch-high-contrast .v-switch__thumb) {
  background: #fff !important;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.4) !important;
}
</style>

<style>
/* Unscoped: dialog overlay is teleported so scoped can't reach it */
.run-chain-dialog.v-dialog .v-overlay__scrim {
  opacity: 1;
  background: rgba(0, 0, 0, 0.6) !important;
}
</style>

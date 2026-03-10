<template>
  <div class="admin-wizard mx-auto" style="max-width: 960px;">
    <h1 class="text-h4 mb-2">Wizard Use Cases</h1>
    <p class="text-body-2 text-medium-emphasis mb-4">
      Configure use cases for the setup wizard. Each use case appears as a card in "What do you want to achieve?" and collects parameters before running the linked chain.
    </p>

    <div class="d-flex justify-space-between align-center mb-6">
      <span class="text-body-2">Founders see these use cases when they open the Quick start wizard.</span>
      <v-btn color="primary" @click="openCreateModal">Add use case</v-btn>
    </div>

    <div v-if="loading" class="text-medium-emphasis py-6">Loading...</div>
    <div v-else-if="useCases.length === 0" class="text-medium-emphasis py-8 text-center">
      No use cases configured. Add one to get started.
    </div>
    <div v-else class="d-flex flex-column gap-3">
      <v-card v-for="uc in useCases" :key="uc.id" variant="tonal" class="pa-5">
        <div class="d-flex justify-space-between align-start flex-wrap gap-3">
          <div class="flex-grow-1">
            <strong class="text-h6">{{ uc.label }}</strong>
            <span class="text-caption text-medium-emphasis d-block mt-1">{{ uc.slug }} → chain: {{ uc.chain_slug }}</span>
            <p v-if="uc.description" class="text-body-2 mt-2 mb-0">{{ uc.description }}</p>
            <v-chip size="small" class="mt-2">{{ injectLabel(uc.inject_as) }}</v-chip>
          </div>
          <div class="d-flex gap-2">
            <v-btn size="small" variant="outlined" @click="openEditModal(uc)">Edit</v-btn>
            <v-btn size="small" variant="outlined" color="error" :loading="deleteLoading === uc.id" :disabled="deleteLoading === uc.id" @click="deleteUseCase(uc)">Delete</v-btn>
          </div>
        </div>
        <div v-if="uc.params?.length" class="mt-3 pt-3" style="border-top: 1px solid rgba(var(--v-border-color), 0.5);">
          <span class="text-caption text-medium-emphasis">Parameters collected in wizard:</span>
          <span class="text-body-2 ml-1">{{ uc.params.map((p) => p.label || p.slug).join(', ') }}</span>
        </div>
      </v-card>
    </div>

    <v-dialog v-model="editDialog" max-width="720" persistent scrollable>
      <v-card v-if="editDialog" class="d-flex flex-column" style="max-height: 90vh;">
        <v-card-title class="text-h6 pa-4 pb-2">
          {{ editingId ? 'Edit use case' : 'Add use case' }}
        </v-card-title>
        <v-card-text class="pa-4 pt-2 flex-grow-1 overflow-y-auto">
          <p class="text-body-2 text-medium-emphasis mb-4">
            This use case will appear as a selectable card in the wizard. Set the chain (by slug) and parameters that founders will fill in.
          </p>

          <v-divider class="my-4" />

          <div class="form-section mb-6">
            <h3 class="text-subtitle-1 font-weight-medium mb-3">Identity</h3>
            <v-text-field
              v-model="form.slug"
              label="Slug"
              placeholder="contract-investigation"
              :disabled="!!editingId"
              variant="outlined"
              density="comfortable"
              hint="Internal ID, e.g. contract-investigation. Used in URLs and config. Cannot change after create."
              persistent-hint
              class="mb-3"
            />
            <v-text-field
              v-model="form.label"
              label="Label"
              placeholder="Analyse and track blockchain contract"
              variant="outlined"
              density="comfortable"
              hint="Shown as the card title in the wizard: 'What do you want to achieve?'"
              persistent-hint
              class="mb-3"
            />
            <v-textarea
              v-model="form.description"
              label="Description"
              placeholder="Get transactions, caller analysis, and period metrics for a contract on Fuji or Avalanche."
              rows="2"
              variant="outlined"
              density="comfortable"
              hint="Shown below the label on the card. Helps founders understand what this use case does."
              persistent-hint
            />
          </div>

          <v-divider class="my-4" />

          <div class="form-section mb-6">
            <h3 class="text-subtitle-1 font-weight-medium mb-3">Chain</h3>
            <v-combobox
              v-model="form.chain_slug"
              :items="chainOptions"
              item-title="title"
              item-value="value"
              label="Chain slug"
              placeholder="Select or type (e.g. contract-investigation-fuji)"
              variant="outlined"
              density="comfortable"
              hint="Pick from your runnable chains (with slugs). When Inject as = Slugs, parameters auto-fill from the selected chain."
              persistent-hint
              clearable
              @update:model-value="onChainSlugChange"
            />
          </div>

          <v-divider class="my-4" />

          <div class="form-section mb-6">
            <h3 class="text-subtitle-1 font-weight-medium mb-3">Required config (prerequisites)</h3>
            <p class="text-caption text-medium-emphasis mb-3">
              Config the founder must have before running. If missing, the wizard will show a setup link (e.g. API Keys) and block Run until configured.
            </p>
            <v-select
              v-model="form.required_config"
              :items="requiredConfigOptions"
              item-title="title"
              item-value="value"
              label="Required config"
              multiple
              chips
              variant="outlined"
              density="comfortable"
              hint="Select config items founders must set up first (e.g. GitHub token for GitHub MCP chains)."
              persistent-hint
            />
          </div>

          <v-divider class="my-4" />

          <div class="form-section mb-6">
            <h3 class="text-subtitle-1 font-weight-medium mb-3">How parameters are used</h3>
            <v-select
              v-model="form.inject_as"
              :items="injectOptions"
              item-title="title"
              item-value="value"
              label="Inject as"
              variant="outlined"
              density="comfortable"
              hint="slugs = save each param to saved-outputs, then run chain (chain reads from slugs). user_input = build a prompt and pass to chain. run_history = use Run History Create report flow."
              persistent-hint
            />
          </div>

          <v-divider class="my-4" />

          <div class="form-section mb-6">
            <div class="d-flex justify-space-between align-center mb-3 flex-wrap gap-2">
              <div>
                <h3 class="text-subtitle-1 font-weight-medium mb-1">Parameters</h3>
                <p class="text-caption text-medium-emphasis mb-0">
                  Each parameter becomes a field in the wizard. Select a chain with Inject as = Slugs to auto-fill from the chain, or add/edit below.
                </p>
              </div>
              <v-btn color="primary" variant="flat" size="small" @click="addParamAndEdit">
                <v-icon start size="small">mdi-plus</v-icon>
                Add parameter
              </v-btn>
            </div>

            <div v-if="!form.params?.length" class="text-medium-emphasis py-6 text-center" style="border: 1px dashed rgba(var(--v-border-color), 0.8); border-radius: 8px;">
              No parameters. Select a chain (with Inject as = Slugs) to auto-fill, or click <strong>Add parameter</strong>.
            </div>

            <div v-else class="param-list">
              <div
                v-for="(p, idx) in form.params"
                :key="idx"
                class="param-list-item d-flex align-center justify-space-between flex-nowrap gap-2 py-2 px-3"
              >
                <div class="d-flex align-center flex-grow-1 min-width-0">
                  <span class="text-body-2 font-weight-medium">{{ p.label || p.slug || 'Unnamed' }}</span>
                  <v-chip v-if="p.slug" size="x-small" variant="outlined" class="ml-2">{{ p.slug }}</v-chip>
                </div>
                <div class="param-actions">
                  <v-btn icon size="small" variant="text" title="Edit" @click="openParamEdit(idx)">
                    <v-icon size="small">mdi-pencil</v-icon>
                  </v-btn>
                  <v-btn icon size="small" variant="text" color="error" title="Remove" @click="removeParam(idx)">
                    <v-icon size="small">mdi-delete</v-icon>
                  </v-btn>
                </div>
              </div>
            </div>
          </div>

          <!-- Parameter edit dialog -->
          <v-dialog v-model="paramEditDialog" max-width="520" persistent>
            <v-card v-if="paramEditDialog && paramEditPayload">
              <v-card-title class="text-subtitle-1">Edit parameter</v-card-title>
              <v-card-text class="pt-2">
                <v-text-field
                  v-model="paramEditPayload.slug"
                  label="Slug"
                  placeholder="contract_address"
                  variant="outlined"
                  density="comfortable"
                  hint="Key for saved-outputs. Use lowercase, underscores."
                  persistent-hint
                  class="mb-3"
                />
                <v-text-field
                  v-model="paramEditPayload.label"
                  label="Label"
                  placeholder="Contract address"
                  variant="outlined"
                  density="comfortable"
                  hint="Shown as the field label in the wizard."
                  persistent-hint
                  class="mb-3"
                />
                <v-select
                  v-model="paramEditPayload.type"
                  :items="paramTypeOptions"
                  item-title="title"
                  item-value="value"
                  label="Type"
                  variant="outlined"
                  density="comfortable"
                  class="mb-3"
                />
                <v-text-field
                  v-model="paramEditPayload.placeholder"
                  label="Placeholder"
                  placeholder="0x..."
                  variant="outlined"
                  density="comfortable"
                  class="mb-3"
                />
                <v-select
                  v-model="paramEditPayload.validation"
                  :items="validationOptions"
                  item-title="title"
                  item-value="value"
                  label="Validation"
                  variant="outlined"
                  density="comfortable"
                  clearable
                  class="mb-3"
                />
                <v-text-field
                  v-model="paramEditPayload.default"
                  label="Default value"
                  placeholder="(optional)"
                  variant="outlined"
                  density="comfortable"
                  class="mb-3"
                />
                <div v-if="paramEditPayload.type === 'select'" class="mb-3">
                  <v-text-field
                    :model-value="(paramEditPayload.options || []).join(', ')"
                    label="Options (comma-separated)"
                    placeholder="fuji, avalanche"
                    variant="outlined"
                    density="comfortable"
                    @update:model-value="(v) => { paramEditPayload.options = (v || '').split(',').map(s => s.trim()).filter(Boolean) }"
                  />
                </div>
                <v-checkbox v-model="paramEditPayload.required" label="Required" color="primary" hide-details />
              </v-card-text>
              <v-card-actions>
                <v-spacer />
                <v-btn variant="text" @click="paramEditDialog = false">Cancel</v-btn>
                <v-btn color="primary" @click="saveParamEdit">Done</v-btn>
              </v-card-actions>
            </v-card>
          </v-dialog>

          <v-divider class="my-4" />

          <div class="form-section">
            <v-text-field
              v-model.number="form.sort_order"
              type="number"
              label="Sort order"
              variant="outlined"
              density="comfortable"
              hint="Lower numbers appear first in the wizard. Use 0, 10, 20 for easy reordering."
              persistent-hint
              min="0"
            />
          </div>
        </v-card-text>
        <v-divider />
        <v-card-actions class="pa-4">
          <v-spacer />
          <v-btn variant="outlined" @click="editDialog = false">Cancel</v-btn>
          <v-btn color="primary" :loading="saveLoading" :disabled="!form.slug || !form.label || !form.chain_slug" @click="saveUseCase">Save</v-btn>
        </v-card-actions>
        <p v-if="saveError" class="text-error text-body-2 px-4 pb-2">{{ saveError }}</p>
      </v-card>
    </v-dialog>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import api from '@/services/api'

/** Humanize slug for label, e.g. contract_address -> Contract address */
function slugToLabel(s) {
  if (!s || typeof s !== 'string') return ''
  return s
    .replace(/_/g, ' ')
    .replace(/-/g, ' ')
    .replace(/\b\w/g, (c) => c.toUpperCase())
}

const useCases = ref([])
const chains = ref([])
const chainsLoading = ref(false)
const loading = ref(true)
const deleteLoading = ref(null)
const editDialog = ref(false)
const editingId = ref(null)
const saveLoading = ref(false)
const saveError = ref('')
const chainSlugInjectSnapshot = ref({ chain_slug: '', inject_as: '' })
const paramEditDialog = ref(false)
const paramEditIndex = ref(null)
const paramEditPayload = ref(null)

const chainOptions = computed(() => {
  const withSlug = (chains.value || []).filter((c) => c.slug)
  return withSlug.map((c) => ({
    title: `${c.name} (${c.slug})`,
    value: c.slug,
  }))
})


const injectOptions = [
  { title: 'Slugs — save each param to saved-outputs, chain reads from slugs', value: 'slugs' },
  { title: 'User input — build a prompt from params, pass to chain', value: 'user_input' },
  { title: 'Run history — founders select prior runs, use Create report flow', value: 'run_history' },
]

const paramTypeOptions = [
  { title: 'Text', value: 'text' },
  { title: 'Date', value: 'date' },
  { title: 'Select (dropdown)', value: 'select' },
]

const validationOptions = [
  { title: 'None', value: '' },
  { title: 'Ethereum address (0x + 40 hex)', value: 'ethereum_address' },
]

const requiredConfigOptions = [
  { title: 'GitHub token', value: 'github_token', subtitle: 'For chains that use GitHub MCP (commits, files)' },
  { title: 'Personality', value: 'personality', subtitle: 'For personality-driven workflows (voice / tone)' },
]

function injectLabel(v) {
  const o = injectOptions.find((x) => x.value === v)
  return o ? o.title.split(' — ')[0] : v
}

/** Normalize chain_slug from combobox (can be string or item object). */
function normalizedChainSlug() {
  const raw = form.value.chain_slug
  if (raw == null) return ''
  if (typeof raw === 'object' && raw !== null && 'value' in raw) return String(raw.value || '').trim()
  return String(raw).trim()
}

function onChainSlugChange() {
  const slug = normalizedChainSlug()
  if (typeof form.value.chain_slug === 'object' && form.value.chain_slug !== null) {
    form.value.chain_slug = slug
  }
  if (form.value.inject_as !== 'slugs') return
  chainSlugInjectSnapshot.value = { chain_slug: slug, inject_as: form.value.inject_as }
  syncParamsFromChain()
}

function addParam() {
  form.value.params = form.value.params || []
  form.value.params.push({
    slug: '',
    label: '',
    type: 'text',
    required: false,
    placeholder: '',
    validation: '',
    options: [],
    default: '',
  })
}

function addParamAndEdit() {
  addParam()
  openParamEdit(form.value.params.length - 1)
}

function openParamEdit(idx) {
  const p = form.value.params?.[idx]
  if (!p) return
  paramEditIndex.value = idx
  paramEditPayload.value = {
    slug: p.slug || '',
    label: p.label || '',
    type: p.type || 'text',
    required: !!p.required,
    placeholder: p.placeholder || '',
    validation: p.validation || '',
    options: [...(p.options || [])],
    default: p.default || '',
  }
  paramEditDialog.value = true
}

function saveParamEdit() {
  const idx = paramEditIndex.value
  const payload = paramEditPayload.value
  if (idx == null || idx < 0 || !form.value.params?.[idx] || !payload) {
    paramEditDialog.value = false
    return
  }
  form.value.params[idx] = {
    slug: payload.slug?.trim() || '',
    label: payload.label?.trim() || '',
    type: payload.type || 'text',
    required: !!payload.required,
    placeholder: payload.placeholder?.trim() || '',
    validation: (payload.validation && String(payload.validation).trim()) ? payload.validation : '',
    options: payload.type === 'select' ? (payload.options || []) : [],
    default: payload.default?.trim() || '',
  }
  paramEditDialog.value = false
  paramEditIndex.value = null
  paramEditPayload.value = null
}

function removeParam(idx) {
  form.value.params.splice(idx, 1)
}

function updateParamOptions(idx, text) {
  const p = form.value.params?.[idx]
  if (!p) return
  p.options = (text || '')
    .split(',')
    .map((s) => s.trim())
    .filter(Boolean)
}

const form = ref({
  slug: '',
  label: '',
  description: '',
  chain_slug: '',
  params: [],
  inject_as: 'slugs',
  required_config: [],
  sort_order: 0,
})

function openCreateModal() {
  editingId.value = null
  form.value = {
    slug: '',
    label: '',
    description: '',
    chain_slug: '',
    params: [],
    inject_as: 'slugs',
    required_config: [],
    sort_order: 0,
  }
  chainSlugInjectSnapshot.value = { chain_slug: '', inject_as: 'slugs' }
  saveError.value = ''
  editDialog.value = true
  loadChains()
}

function openEditModal(uc) {
  editingId.value = uc.id
  form.value = {
    slug: uc.slug,
    label: uc.label,
    description: uc.description || '',
    chain_slug: uc.chain_slug || '',
    required_config: uc.required_config || [],
    params: (uc.params || []).map((p) => ({
      slug: p.slug || '',
      label: p.label || '',
      type: p.type || 'text',
      required: !!p.required,
      placeholder: p.placeholder || '',
      validation: p.validation || '',
      options: p.options || [],
      default: p.default || '',
    })),
    inject_as: uc.inject_as || 'slugs',
    sort_order: uc.sort_order ?? 0,
  }
  chainSlugInjectSnapshot.value = { chain_slug: uc.chain_slug || '', inject_as: uc.inject_as || 'slugs' }
  saveError.value = ''
  editDialog.value = true
  loadChains()
}

/** Collect slug names from chain definition (slug nodes and setup save_to_slug). */
function getSlugsFromDefinition(definition) {
  const nodes = definition?.nodes || []
  const slugs = new Set()
  for (const n of nodes) {
    if (n.type === 'slug' && n.slug) slugs.add(String(n.slug).trim())
    if (n.save_to_slug) slugs.add(String(n.save_to_slug).trim())
  }
  return [...slugs].filter(Boolean)
}

async function syncParamsFromChain() {
  const injectAs = form.value.inject_as
  const chainSlug = normalizedChainSlug()
  if (injectAs !== 'slugs') {
    form.value.params = []
    return
  }
  if (!chainSlug) {
    form.value.params = []
    return
  }
  const chain = (chains.value || []).find((c) => c.slug === chainSlug)
  if (!chain?.id) {
    return
  }
  try {
    const { data } = await api.get(`/chains/${chain.id}`)
    const defn = data?.definition || {}
    const slugList = getSlugsFromDefinition(defn)
    form.value.params = slugList.map((slug) => ({
      slug,
      label: slugToLabel(slug),
      type: 'text',
      required: false,
      placeholder: '',
      validation: '',
      options: [],
      default: '',
    }))
  } catch {
    form.value.params = []
  }
}

async function loadChains() {
  chainsLoading.value = true
  try {
    const { data } = await api.get('/chains/runnable')
    chains.value = data || []
  } catch {
    chains.value = []
  } finally {
    chainsLoading.value = false
    // Only auto-fill params from chain when creating a new use case; when editing, keep existing params
    if (editDialog.value && editingId.value == null && form.value.inject_as === 'slugs' && normalizedChainSlug()) {
      syncParamsFromChain()
    }
  }
}

async function loadUseCases() {
  loading.value = true
  try {
    const { data } = await api.get('/wizard/admin/use-cases')
    useCases.value = data || []
  } catch (e) {
    console.error(e)
    useCases.value = []
  } finally {
    loading.value = false
  }
}

async function saveUseCase() {
  saveError.value = ''
  saveLoading.value = true
  try {
    const payload = {
      ...form.value,
      chain_slug: normalizedChainSlug() || form.value.chain_slug,
      required_config: form.value.required_config || [],
      params: (form.value.params || []).map((p) => ({
        slug: p.slug?.trim() || '',
        label: p.label?.trim() || '',
        type: p.type || 'text',
        required: !!p.required,
        placeholder: p.placeholder?.trim() || undefined,
        validation: (p.validation && String(p.validation).trim()) ? p.validation : undefined,
        options: p.type === 'select' ? (p.options || []) : undefined,
        default: p.default?.trim() || undefined,
      })).filter((p) => p.slug),
    }
    if (editingId.value) {
      await api.put(`/wizard/admin/use-cases/${editingId.value}`, payload)
    } else {
      await api.post('/wizard/admin/use-cases', payload)
    }
    editDialog.value = false
    await loadUseCases()
  } catch (e) {
    saveError.value = e.response?.data?.detail || e.message || 'Failed to save'
  } finally {
    saveLoading.value = false
  }
}

async function deleteUseCase(uc) {
  if (!confirm(`Delete use case "${uc.label}"?`)) return
  deleteLoading.value = uc.id
  try {
    await api.delete(`/wizard/admin/use-cases/${uc.id}`)
    await loadUseCases()
  } catch (e) {
    alert(e.response?.data?.detail || 'Failed to delete')
  } finally {
    deleteLoading.value = null
  }
}

watch(
  () => [normalizedChainSlug(), form.value.inject_as],
  ([chainSlug, injectAs]) => {
    if (!editDialog.value) return
    const prev = chainSlugInjectSnapshot.value
    const c = chainSlug || ''
    const i = injectAs || ''
    if (prev.chain_slug === c && prev.inject_as === i) return
    chainSlugInjectSnapshot.value = { chain_slug: c, inject_as: i }
    syncParamsFromChain()
  }
)

onMounted(loadUseCases)
</script>

<style scoped>
.form-section h3 {
  margin-bottom: 0.5rem;
}
.param-list {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}
.param-list-item {
  border: 1px solid rgba(var(--v-border-color), 0.5);
  border-radius: 8px;
}
.param-actions {
  flex-shrink: 0;
}
</style>

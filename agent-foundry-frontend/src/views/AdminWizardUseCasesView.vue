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
              hint="Pick from your runnable chains (with slugs) or type a slug manually. Set slug in Chain Builder meta row."
              persistent-hint
              clearable
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
                  Each parameter becomes a field in the wizard. Founders fill these in before the chain runs.
                </p>
              </div>
              <v-btn color="primary" variant="flat" size="small" @click="addParam">
                <v-icon start size="small">mdi-plus</v-icon>
                Add parameter
              </v-btn>
            </div>

            <div v-if="!form.params?.length" class="text-medium-emphasis py-6 text-center" style="border: 1px dashed rgba(var(--v-border-color), 0.8); border-radius: 8px;">
              No parameters. Click <strong>Add parameter</strong> above to add fields (e.g. contract address, start date).
            </div>

            <v-card
              v-for="(p, idx) in form.params"
              :key="idx"
              variant="outlined"
              class="pa-4 mb-3"
            >
              <div class="d-flex justify-space-between align-center mb-3">
                <span class="text-subtitle-2">Parameter {{ idx + 1 }}</span>
                <v-btn icon size="small" variant="text" color="error" @click="removeParam(idx)">
                  <v-icon size="small">mdi-delete</v-icon>
                </v-btn>
              </div>
              <div class="d-flex flex-column gap-3">
                <v-text-field
                  v-model="p.slug"
                  label="Slug"
                  placeholder="contract_address"
                  variant="outlined"
                  density="compact"
                  hint="Key for saved-outputs or user_input. Use lowercase, underscores."
                  persistent-hint
                  hide-details="auto"
                />
                <v-text-field
                  v-model="p.label"
                  label="Label"
                  placeholder="Contract address"
                  variant="outlined"
                  density="compact"
                  hint="Shown as the field label in the wizard form."
                  persistent-hint
                  hide-details="auto"
                />
                <v-select
                  v-model="p.type"
                  :items="paramTypeOptions"
                  item-title="title"
                  item-value="value"
                  label="Type"
                  variant="outlined"
                  density="compact"
                  hint="text = free text. date = date picker. select = dropdown."
                  persistent-hint
                  hide-details="auto"
                />
                <v-text-field
                  v-model="p.placeholder"
                  label="Placeholder"
                  placeholder="0x..."
                  variant="outlined"
                  density="compact"
                  hint="Placeholder text in the input (optional)."
                  persistent-hint
                  hide-details="auto"
                />
                <v-select
                  v-model="p.validation"
                  :items="validationOptions"
                  item-title="title"
                  item-value="value"
                  label="Validation"
                  variant="outlined"
                  density="compact"
                  clearable
                  hint="Extra validation, e.g. ethereum_address for 0x... hex."
                  persistent-hint
                  hide-details="auto"
                />
                <v-text-field
                  v-model="p.default"
                  label="Default value"
                  placeholder="fuji"
                  variant="outlined"
                  density="compact"
                  hint="Pre-filled value (optional). For select, use one of the options."
                  persistent-hint
                  hide-details="auto"
                />
                <div v-if="p.type === 'select'">
                  <v-text-field
                    :model-value="(p.options || []).join(', ')"
                    label="Options"
                    placeholder="fuji, avalanche"
                    variant="outlined"
                    density="compact"
                    hint="Comma-separated list of choices for the dropdown."
                    persistent-hint
                    hide-details="auto"
                    @update:model-value="(v) => updateParamOptions(idx, v)"
                  />
                </div>
                <v-checkbox v-model="p.required" label="Required" density="compact" hide-details color="primary" />
              </div>
            </v-card>
          </div>

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

const useCases = ref([])
const chains = ref([])
const chainsLoading = ref(false)
const loading = ref(true)
const deleteLoading = ref(null)
const editDialog = ref(false)
const editingId = ref(null)
const saveLoading = ref(false)
const saveError = ref('')

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
]

function injectLabel(v) {
  const o = injectOptions.find((x) => x.value === v)
  return o ? o.title.split(' — ')[0] : v
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
  saveError.value = ''
  editDialog.value = true
  loadChains()
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

onMounted(loadUseCases)
</script>

<style scoped>
.form-section h3 {
  margin-bottom: 0.5rem;
}
</style>

<template>
  <div class="admin-wizard mx-auto" style="max-width: 900px;">
    <h1 class="text-h4 mb-2">Wizard Use Cases</h1>
    <p class="text-body-2 text-medium-emphasis mb-4">
      Configure use cases for the setup wizard. Each use case maps to a chain (by slug) and defines parameters to collect.
    </p>

    <div class="d-flex justify-space-between align-center mb-4">
      <span class="text-body-2">Use cases appear in the setup wizard for founders.</span>
      <v-btn color="primary" size="small" @click="openCreateModal">Add use case</v-btn>
    </div>

    <div v-if="loading" class="text-medium-emphasis py-4">Loading...</div>
    <div v-else-if="useCases.length === 0" class="text-medium-emphasis py-4">
      No use cases configured. Add one to get started.
    </div>
    <div v-else class="d-flex flex-column gap-2">
      <v-card v-for="uc in useCases" :key="uc.id" variant="tonal" class="pa-4">
        <div class="d-flex justify-space-between align-start flex-wrap gap-2">
          <div>
            <strong>{{ uc.label }}</strong>
            <span class="text-caption text-medium-emphasis d-block">{{ uc.slug }} → chain: {{ uc.chain_slug }}</span>
            <span v-if="uc.description" class="text-body-2 d-block mt-1">{{ uc.description }}</span>
            <v-chip size="x-small" class="mt-1">{{ uc.inject_as }}</v-chip>
          </div>
          <div class="d-flex gap-2">
            <v-btn size="small" variant="outlined" @click="openEditModal(uc)">Edit</v-btn>
            <v-btn size="small" variant="outlined" color="error" :loading="deleteLoading === uc.id" :disabled="deleteLoading === uc.id" @click="deleteUseCase(uc)">Delete</v-btn>
          </div>
        </div>
        <div v-if="uc.params?.length" class="mt-2">
          <span class="text-caption text-medium-emphasis">Params: </span>
          <span class="text-caption">{{ uc.params.map((p) => p.label || p.slug).join(', ') }}</span>
        </div>
      </v-card>
    </div>

    <v-dialog v-model="editDialog" max-width="560" persistent>
      <v-card v-if="editDialog" class="pa-4">
        <h4 class="text-h6 mb-3">{{ editingId ? 'Edit use case' : 'Add use case' }}</h4>
        <div class="d-flex flex-column gap-2 mb-3">
          <v-text-field v-model="form.slug" label="Slug" placeholder="contract-investigation" density="compact" hide-details :disabled="!!editingId" />
          <v-text-field v-model="form.label" label="Label" placeholder="Analyse and track blockchain contract" density="compact" hide-details />
          <v-textarea v-model="form.description" label="Description (optional)" rows="2" density="compact" hide-details />
          <v-text-field v-model="form.chain_slug" label="Chain slug" placeholder="contract-investigation-fuji" density="compact" hide-details />
          <v-select v-model="form.inject_as" :items="injectOptions" label="Inject as" density="compact" hide-details />
          <v-text-field v-model.number="form.sort_order" type="number" label="Sort order" density="compact" hide-details />
          <div>
            <label class="text-caption d-block mb-1">Params (JSON array)</label>
            <v-textarea v-model="paramsJson" placeholder='[{"slug":"contract_address","label":"Contract address","type":"text","required":true}]' rows="6" density="compact" class="font-monospace" />
            <p class="text-caption text-medium-emphasis mt-1">Each item: slug, label, type (text|date|select), required, placeholder, validation, options (for select)</p>
          </div>
        </div>
        <div class="d-flex gap-2">
          <v-btn variant="outlined" @click="editDialog = false">Cancel</v-btn>
          <v-btn color="primary" :loading="saveLoading" :disabled="!form.slug || !form.label || !form.chain_slug" @click="saveUseCase">Save</v-btn>
        </div>
        <p v-if="saveError" class="text-error text-body-2 mt-3 mb-0">{{ saveError }}</p>
      </v-card>
    </v-dialog>
  </div>
</template>

<script setup>
import { ref, watch, onMounted } from 'vue'
import api from '@/services/api'

const useCases = ref([])
const loading = ref(true)
const deleteLoading = ref(null)
const editDialog = ref(false)
const editingId = ref(null)
const saveLoading = ref(false)
const saveError = ref('')

const injectOptions = [
  { title: 'Slugs (save to saved-outputs before run)', value: 'slugs' },
  { title: 'User input (build prompt)', value: 'user_input' },
  { title: 'Run history (select prior runs)', value: 'run_history' },
]

const form = ref({
  slug: '',
  label: '',
  description: '',
  chain_slug: '',
  params: [],
  inject_as: 'slugs',
  sort_order: 0,
})
const paramsJson = ref('[]')

function openCreateModal() {
  editingId.value = null
  form.value = { slug: '', label: '', description: '', chain_slug: '', params: [], inject_as: 'slugs', sort_order: 0 }
  paramsJson.value = '[]'
  saveError.value = ''
  editDialog.value = true
}

function openEditModal(uc) {
  editingId.value = uc.id
  form.value = {
    slug: uc.slug,
    label: uc.label,
    description: uc.description || '',
    chain_slug: uc.chain_slug,
    params: uc.params || [],
    inject_as: uc.inject_as || 'slugs',
    sort_order: uc.sort_order ?? 0,
  }
  paramsJson.value = JSON.stringify(uc.params || [], null, 2)
  saveError.value = ''
  editDialog.value = true
}

watch(paramsJson, (val) => {
  try {
    form.value.params = JSON.parse(val || '[]')
  } catch (_) {
    // ignore parse errors while typing
  }
}, { immediate: true })

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
  let parsed
  try {
    parsed = JSON.parse(paramsJson.value || '[]')
  } catch (_) {
    saveError.value = 'Invalid params JSON'
    return
  }
  form.value.params = parsed
  saveLoading.value = true
  try {
    if (editingId.value) {
      await api.put(`/wizard/admin/use-cases/${editingId.value}`, form.value)
    } else {
      await api.post('/wizard/admin/use-cases', form.value)
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

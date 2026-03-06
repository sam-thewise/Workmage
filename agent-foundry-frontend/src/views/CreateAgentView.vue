<template>
  <div class="create-agent mx-auto" style="max-width: 720px;">
    <h1 class="text-h4 mb-4">{{ isEdit ? 'Edit AI Role' : 'Create AI Role' }}</h1>
    <v-form @submit.prevent="submit" class="d-flex flex-column gap-4">
      <v-card variant="tonal" class="pa-4">
        <v-label class="text-body-2 font-weight-medium mb-2 d-block">OASF Manifest (JSON or YAML)</v-label>
        <v-textarea v-model="manifestRaw" rows="12" placeholder='{"name":"My AI Role","version":"1.0.0",...}' density="comfortable" class="mb-2" />
        <v-btn type="button" variant="outlined" size="small" @click="validateManifest" class="mb-2">Validate</v-btn>
        <div v-if="validationResult" :class="['pa-3 rounded', validationResult.valid ? 'bg-success' : 'bg-error']">
          <span v-if="validationResult.valid">✓ Manifest is valid</span>
          <div v-else>
            <span>Validation errors:</span>
            <ul class="ma-0 mt-1 pl-4">
              <li v-for="(err, i) in validationResult.errors" :key="i">{{ err }}</li>
            </ul>
          </div>
        </div>
      </v-card>
      <v-text-field v-model="name" label="Name (override manifest)" placeholder="AI Role name from manifest" density="comfortable" />
      <v-textarea v-model="description" label="Description (override manifest)" placeholder="AI Role description" rows="3" density="comfortable" />
      <v-text-field v-model.number="priceDollars" type="number" min="0" step="0.01" label="Price (USD)" placeholder="0 = free" density="comfortable" />
      <v-card v-if="priceDollars > 0" variant="tonal" class="pa-3">
        <p class="text-body-2 mb-1"><strong>Buyer pays:</strong> ${{ priceDisplay }}</p>
        <p class="text-body-2 mb-1"><strong>You receive (80%):</strong> ${{ creatorDisplay }}</p>
        <p class="text-body-2 text-medium-emphasis mb-0"><strong>Platform fee (20%):</strong> ${{ platformFeeDisplay }}</p>
      </v-card>
      <v-text-field v-model="category" label="Category" placeholder="e.g. productivity" density="comfortable" />
      <v-text-field v-model="tagsStr" label="Tags (comma-separated)" placeholder="tag1, tag2" density="comfortable" />
      <div class="d-flex gap-2">
        <v-btn type="submit" color="primary" :loading="submitting">{{ isEdit ? 'Save' : 'Create' }}</v-btn>
        <v-btn variant="outlined" color="primary" to="/dashboard/agents">Cancel</v-btn>
      </div>
    </v-form>
    <p v-if="error" class="text-error mt-4">{{ error }}</p>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import api from '@/services/api'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
const isEdit = computed(() => !!route.params.id)

const manifestRaw = ref('')
const name = ref('')
const description = ref('')
const priceDollars = ref(0)
const category = ref('')
const tagsStr = ref('')
const validationResult = ref(null)
const submitting = ref(false)
const error = ref('')

const tags = computed(() =>
  tagsStr.value ? tagsStr.value.split(',').map((t) => t.trim()).filter(Boolean) : []
)
const priceCents = computed(() => Math.max(0, Math.round((priceDollars.value || 0) * 100)))
const priceDisplay = computed(() => (priceDollars.value || 0).toFixed(2))
const creatorDisplay = computed(() => ((priceCents.value * 0.8) / 100).toFixed(2))
const platformFeeDisplay = computed(() => ((priceCents.value * 0.2) / 100).toFixed(2))

async function validateManifest() {
  if (!manifestRaw.value.trim()) {
    validationResult.value = { valid: false, errors: ['Manifest is required'] }
    return
  }
  try {
    const { data } = await api.post('/agents/validate', { raw: manifestRaw.value })
    validationResult.value = data
    if (data.valid && data.metadata?.name && !name.value) name.value = data.metadata.name
    if (data.valid && data.metadata?.description && !description.value) description.value = data.metadata.description || ''
  } catch (e) {
    validationResult.value = { valid: false, errors: [e.response?.data?.detail || 'Validation failed'] }
  }
}

async function submit() {
  error.value = ''
  if (!manifestRaw.value.trim()) {
    error.value = 'Manifest is required'
    return
  }
  try {
    await validateManifest()
    if (!validationResult.value?.valid) {
      error.value = 'Fix manifest validation errors first'
      return
    }
  } catch {
    error.value = 'Validation failed'
    return
  }
  submitting.value = true
  try {
    if (isEdit.value) {
      await api.put(`/agents/${route.params.id}`, {
        manifest_raw: manifestRaw.value,
        name: name.value || undefined,
        description: description.value || undefined,
        price_cents: priceCents.value,
        category: category.value || undefined,
        tags: tags.value
      })
      router.push('/dashboard/agents')
    } else {
      await api.post('/agents', {
        manifest_raw: manifestRaw.value,
        name: name.value || undefined,
        description: description.value || undefined,
        price_cents: priceCents.value,
        category: category.value || undefined,
        tags: tags.value
      })
      router.push('/dashboard/agents')
    }
  } catch (e) {
    const d = e.response?.data?.detail
    error.value = Array.isArray(d?.errors) ? d.errors.join(', ') : (d?.message || 'Failed to save')
  } finally {
    submitting.value = false
  }
}

async function loadAgent() {
  if (!isEdit.value) return
  try {
    const { data } = await api.get(`/agents/${route.params.id}`)
    manifestRaw.value = JSON.stringify(data.manifest, null, 2)
    name.value = data.name || ''
    description.value = data.description || ''
    priceDollars.value = (data.price_cents ?? 0) / 100
    category.value = data.category || ''
    tagsStr.value = Array.isArray(data.tags) ? data.tags.join(', ') : ''
  } catch (e) {
    error.value = 'Failed to load agent'
  }
}

onMounted(() => {
  if (isEdit.value) loadAgent()
})
</script>

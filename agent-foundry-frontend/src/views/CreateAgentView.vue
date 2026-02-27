<template>
  <div class="create-agent">
    <h1>{{ isEdit ? 'Edit Agent' : 'Create Agent' }}</h1>
    <form @submit.prevent="submit" class="agent-form">
      <div class="field">
        <label>OASF Manifest (JSON or YAML)</label>
        <textarea v-model="manifestRaw" rows="12" placeholder='{"name":"My Agent","version":"1.0.0",...}'></textarea>
        <button type="button" @click="validateManifest" class="btn secondary">Validate</button>
        <div v-if="validationResult" :class="['validation', validationResult.valid ? 'valid' : 'invalid']">
          <span v-if="validationResult.valid">✓ Manifest is valid</span>
          <div v-else>
            <span>Validation errors:</span>
            <ul>
              <li v-for="(err, i) in validationResult.errors" :key="i">{{ err }}</li>
            </ul>
          </div>
        </div>
      </div>
      <div class="field">
        <label>Name (override manifest)</label>
        <input v-model="name" type="text" placeholder="Agent name from manifest" />
      </div>
      <div class="field">
        <label>Description (override manifest)</label>
        <textarea v-model="description" rows="3" placeholder="Agent description"></textarea>
      </div>
      <div class="field">
        <label>Price (USD)</label>
        <input v-model.number="priceDollars" type="number" min="0" step="0.01" placeholder="0 = free" />
        <div v-if="priceDollars > 0" class="commission-breakdown">
          <p><strong>Buyer pays:</strong> ${{ priceDisplay }}</p>
          <p><strong>You receive (80%):</strong> ${{ creatorDisplay }}</p>
          <p class="platform-fee"><strong>Platform fee (20%):</strong> ${{ platformFeeDisplay }}</p>
        </div>
      </div>
      <div class="field">
        <label>Category</label>
        <input v-model="category" type="text" placeholder="e.g. productivity" />
      </div>
      <div class="field">
        <label>Tags (comma-separated)</label>
        <input v-model="tagsStr" type="text" placeholder="tag1, tag2" />
      </div>
      <div class="actions">
        <button type="submit" class="btn primary" :disabled="submitting">
          {{ isEdit ? 'Save' : 'Create' }}
        </button>
        <router-link to="/dashboard/agents" class="btn secondary">Cancel</router-link>
      </div>
    </form>
    <div v-if="error" class="error">{{ error }}</div>
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

<style scoped>
.create-agent { max-width: 720px; }
.agent-form { display: flex; flex-direction: column; gap: 1rem; }
.field label { display: block; margin-bottom: 0.25rem; font-weight: 500; }
.field textarea, .field input { width: 100%; padding: 0.5rem; border-radius: 6px; border: 1px solid var(--wm-border); background: var(--wm-bg-soft); color: var(--wm-text); }
.validation { padding: 0.5rem; border-radius: 6px; margin-top: 0.25rem; }
.validation.valid { background: #065f46; color: #a7f3d0; }
.validation.invalid { background: #7f1d1d; color: #fecaca; }
.validation ul { margin: 0.25rem 0 0 1rem; }
.commission-breakdown { margin-top: 0.5rem; padding: 0.75rem; background: var(--wm-bg); border-radius: 6px; font-size: 0.9rem; }
.commission-breakdown p { margin: 0.25rem 0; }
.commission-breakdown .platform-fee { color: var(--wm-text-muted); }
.btn { display: inline-block; padding: 0.5rem 1rem; border-radius: 6px; text-decoration: none; border: none; cursor: pointer; }
.btn.primary { background: var(--wm-primary); color: var(--wm-white); }
.btn.secondary { background: var(--wm-bg-soft); color: var(--wm-white); margin-left: 0.5rem; border: 1px solid var(--wm-border); }
.btn:disabled { opacity: 0.6; cursor: not-allowed; }
.actions { display: flex; align-items: center; }
.error { color: var(--wm-danger); margin-top: 1rem; }
</style>

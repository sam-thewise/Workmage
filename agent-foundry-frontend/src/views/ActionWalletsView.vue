<template>
  <div class="action-wallets mx-auto mt-4" style="max-width: 720px;">
    <h2 class="text-h5 mb-2">My action wallets</h2>
    <p class="text-body-2 text-medium-emphasis mb-4">
      These wallets are used when <strong>you</strong> run agents on-chain. Each wallet is yours to own and fund; only your runs will use its funds.
    </p>

    <v-btn color="primary" class="mb-4" @click="showCreate = true">Create wallet</v-btn>

    <v-card v-if="wallets.length === 0 && !loading" variant="tonal" class="pa-4">
      <p class="text-body-2 mb-0">You don't have any action wallets yet. Create one to run agents on-chain.</p>
    </v-card>

    <v-table v-else-if="wallets.length" class="mb-4">
      <thead>
        <tr>
          <th>Agent</th>
          <th>Network</th>
          <th>Address</th>
          <th>Status</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="w in wallets" :key="w.id">
          <td>{{ w.agent_name || '—' }}</td>
          <td>{{ w.network }}</td>
          <td>
            <code class="text-body-2">{{ w.wallet_address }}</code>
            <v-btn size="x-small" variant="text" class="ml-1" @click="copyAddress(w.wallet_address)">Copy</v-btn>
          </td>
          <td>{{ w.status }}</td>
        </tr>
      </tbody>
    </v-table>

    <v-dialog v-model="showCreate" max-width="480" persistent>
      <v-card class="pa-4">
        <h3 class="text-h6 mb-3">Create action wallet</h3>
        <p class="text-body-2 text-medium-emphasis mb-3">
          This wallet will be used when you run the selected agent on the chosen chain. Fund it and only your runs will use these funds.
        </p>
        <v-select
          v-model="form.agent_id"
          :items="eligibleAgents"
          item-title="name"
          item-value="id"
          label="Agent"
          density="compact"
          class="mb-2"
          :disabled="loadingAgents"
        />
        <v-select
          v-model="form.chain_id"
          :items="networkOptions"
          item-title="label"
          item-value="value"
          label="Network"
          density="compact"
          class="mb-2"
        />
        <v-select
          v-model="form.managed"
          :items="[{ title: 'Platform-managed (recommended)', value: true }, { title: 'Use my address', value: false }]"
          item-title="title"
          item-value="value"
          label="Type"
          density="compact"
          class="mb-2"
        />
        <v-text-field
          v-if="!form.managed"
          v-model="form.wallet_address"
          label="Your wallet address"
          placeholder="0x..."
          density="compact"
          class="mb-2"
        />
        <p v-if="createError" class="text-error text-body-2 mb-2">{{ createError }}</p>
        <div class="d-flex gap-2 justify-end">
          <v-btn variant="text" @click="showCreate = false">Cancel</v-btn>
          <v-btn color="primary" :loading="creating" :disabled="!form.agent_id || (form.managed === false && !form.wallet_address?.trim())" @click="createWallet">Create</v-btn>
        </div>
      </v-card>
    </v-dialog>

    <v-snackbar v-model="snackbar" :timeout="3000" color="success">
      {{ snackbarText }}
    </v-snackbar>

    <v-dialog v-model="showSuccess" max-width="480" persistent>
      <v-card class="pa-4">
        <h3 class="text-h6 mb-2">Wallet created</h3>
        <p class="text-body-2 mb-2">Fund this wallet to pay for your on-chain runs; only you can trigger spends from it.</p>
        <v-text-field
          :model-value="createdAddress"
          readonly
          density="compact"
          hide-details
          class="mb-2"
        />
        <v-btn color="primary" @click="copyAddress(createdAddress)">Copy address</v-btn>
        <v-btn variant="text" class="ml-2" @click="showSuccess = false; showCreate = false">Close</v-btn>
      </v-card>
    </v-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted, watch } from 'vue'
import api from '@/services/api'

const loading = ref(true)
const wallets = ref([])
const showCreate = ref(false)
const creating = ref(false)
const createError = ref('')
const loadingAgents = ref(true)
const eligibleAgents = ref([])
const snackbar = ref(false)
const snackbarText = ref('')
const showSuccess = ref(false)
const createdAddress = ref('')

const networkOptions = [
  { label: 'Avalanche', value: 43114 },
  { label: 'Fuji (testnet)', value: 43113 }
]

const form = ref({
  agent_id: null,
  chain_id: 43114,
  managed: true,
  wallet_address: ''
})

async function loadWallets() {
  loading.value = true
  try {
    const { data } = await api.get('/action-infra/wallets')
    wallets.value = data || []
  } catch {
    wallets.value = []
  } finally {
    loading.value = false
  }
}

async function loadEligibleAgents() {
  loadingAgents.value = true
  try {
    const [agentsRes, purchasesRes] = await Promise.all([
      api.get('/agents/my').catch(() => ({ data: [] })),
      api.get('/purchases/my').catch(() => ({ data: [] }))
    ])
    const myAgents = agentsRes.data || []
    const purchases = purchasesRes.data || []
    const byId = new Map()
    myAgents.forEach(a => { byId.set(a.id, { id: a.id, name: a.name }) })
    purchases.filter(p => p.agent_id).forEach(p => {
      if (!byId.has(p.agent_id)) byId.set(p.agent_id, { id: p.agent_id, name: p.agent_name || `Agent ${p.agent_id}` })
    })
    eligibleAgents.value = Array.from(byId.values())
  } catch {
    eligibleAgents.value = []
  } finally {
    loadingAgents.value = false
  }
}

function copyAddress(addr) {
  if (!addr) return
  navigator.clipboard.writeText(addr).then(() => {
    snackbarText.value = 'Address copied'
    snackbar.value = true
  })
}

async function createWallet() {
  creating.value = true
  createError.value = ''
  try {
    const payload = {
      agent_id: form.value.agent_id,
      chain_id: form.value.chain_id,
      managed: form.value.managed
    }
    if (!form.value.managed && form.value.wallet_address?.trim()) {
      payload.wallet_address = form.value.wallet_address.trim()
    }
    const { data } = await api.post('/action-infra/wallets', payload)
    createdAddress.value = data.wallet_address || ''
    showSuccess.value = true
    await loadWallets()
  } catch (e) {
    createError.value = e.response?.data?.detail || e.response?.data?.message || 'Failed to create wallet'
  } finally {
    creating.value = false
  }
}

watch(showCreate, (v) => {
  if (v) {
    loadEligibleAgents()
    form.value = { agent_id: null, chain_id: 43114, managed: true, wallet_address: '' }
    createError.value = ''
  }
})

onMounted(loadWallets)
</script>

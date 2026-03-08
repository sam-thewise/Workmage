<template>
  <div class="admin-panel mx-auto" style="max-width: 900px;">
    <div class="d-flex justify-space-between align-center flex-wrap gap-2 mb-4">
      <div class="d-flex align-center gap-2">
        <h1 class="text-h4 mb-0">Admin Panel</h1>
        <v-chip :color="authStore.user?.role === 'admin' ? 'primary' : 'info'" size="small">{{ authStore.user?.role }}</v-chip>
      </div>
      <router-link v-if="authStore.user?.role === 'admin'" to="/admin/wizard" class="text-accent text-decoration-none">Wizard Use Cases</router-link>
    </div>

    <v-tabs v-model="tab" class="mb-4">
      <v-tab value="pending">Pending AI Roles ({{ pendingCount }})</v-tab>
      <v-tab value="pendingChains" @click="loadPendingChains()">Pending AI Teams ({{ pendingChainCount }})</v-tab>
      <v-tab v-if="authStore.user?.role === 'admin'" value="invites" @click="loadInvites()">Moderator Invites</v-tab>
      <v-tab v-if="authStore.user?.role === 'admin'" value="agentNft" @click="loadAgentNftContracts()">AI Role NFT Contracts</v-tab>
    </v-tabs>

    <v-window v-model="tab">
      <!-- Pending agents -->
      <v-window-item value="pending">
        <div v-if="pendingLoading" class="text-medium-emphasis py-4">Loading...</div>
        <div v-else-if="pendingAgents.length === 0" class="text-medium-emphasis py-4">No AI roles pending approval.</div>
        <div v-else class="d-flex flex-column gap-2">
          <v-card v-for="a in pendingAgents" :key="a.id" variant="tonal" class="pa-4">
            <div class="d-flex justify-space-between align-center flex-wrap gap-2">
              <div>
                <strong>{{ a.name }}</strong>
                <span class="text-caption text-medium-emphasis d-block">ID {{ a.id }} · Expert {{ a.expert_id }}</span>
              </div>
              <div class="d-flex gap-2">
                <v-btn size="small" variant="text" :to="`/admin/review/${a.id}`">Review</v-btn>
                <v-btn size="small" color="primary" @click="approve(a.id)">Approve</v-btn>
                <v-btn size="small" color="error" @click="reject(a.id)">Reject</v-btn>
              </div>
            </div>
          </v-card>
        </div>
      </v-window-item>

      <!-- Pending chains -->
      <v-window-item value="pendingChains">
        <div v-if="pendingChainsLoading" class="text-medium-emphasis py-4">Loading...</div>
        <div v-else-if="pendingChains.length === 0" class="text-medium-emphasis py-4">No AI teams pending approval.</div>
        <div v-else class="d-flex flex-column gap-2">
          <v-card v-for="c in pendingChains" :key="c.id" variant="tonal" class="pa-4">
            <div class="d-flex justify-space-between align-center flex-wrap gap-2">
              <div>
                <strong>{{ c.name }}</strong>
                <span class="text-caption text-medium-emphasis d-block">ID {{ c.id }} · Expert {{ c.expert_id }}</span>
              </div>
              <div class="d-flex gap-2">
                <v-btn size="small" variant="text" :to="`/admin/review-chain/${c.id}`">Review</v-btn>
                <v-btn size="small" color="primary" @click="approveChain(c.id)">Approve</v-btn>
                <v-btn size="small" color="error" @click="rejectChain(c.id)">Reject</v-btn>
              </div>
            </div>
          </v-card>
        </div>
      </v-window-item>

      <!-- AI Role NFT contracts -->
      <v-window-item value="agentNft">
        <h3 class="text-h6 mb-3">Registered shared agent NFT contracts</h3>
        <div v-if="agentNftLoading" class="text-medium-emphasis py-4">Loading...</div>
        <div v-else class="d-flex flex-column gap-2 mb-6">
          <v-card v-for="c in agentNftContracts" :key="c.id" variant="tonal" class="pa-4">
            <div class="d-flex justify-space-between align-start flex-wrap gap-2">
              <div class="flex-grow-1">
                <strong>{{ c.network }}</strong>
                <span class="text-caption text-medium-emphasis d-block">Chain {{ c.chain_id }} · {{ c.contract_address }}</span>
                <span v-if="c.deploy_tx_hash" class="text-caption text-medium-emphasis d-block">Tx: {{ c.deploy_tx_hash }}</span>
                <span v-if="c.verified_at" class="text-caption text-success d-block">Verified {{ formatDate(c.verified_at) }}</span>
              </div>
              <div class="d-flex gap-2 flex-wrap">
                <v-btn size="small" variant="outlined" @click="openEditModal(c)">Edit</v-btn>
                <v-btn size="small" variant="outlined" color="error" :loading="deleteLoading === c.id" :disabled="deleteLoading === c.id" @click="deleteAgentNftContract(c)">Delete</v-btn>
                <v-btn size="small" variant="outlined" @click="openVerifyModal(c)">Verify on Snowtrace</v-btn>
                <v-btn size="small" variant="outlined" :loading="verifyStatusLoading === c.network" :disabled="verifyStatusLoading === c.network" @click="checkVerifyStatus(c.network)">
                  {{ verifyStatusLoading === c.network ? 'Checking...' : 'Check verification status' }}
                </v-btn>
              </div>
            </div>
          </v-card>
        </div>
        <p v-if="agentNftContracts.length === 0" class="text-medium-emphasis mb-4">No contracts registered. Register one below.</p>
        <h3 class="text-h6 mb-3">Register contract</h3>
        <div class="d-flex flex-wrap gap-2 align-center mb-4">
          <v-text-field v-model="nftForm.network" placeholder="Network (fuji or avalanche)" density="compact" hide-details style="max-width: 160px;" />
          <v-text-field v-model.number="nftForm.chain_id" type="number" placeholder="Chain ID" density="compact" hide-details style="max-width: 120px;" />
          <v-text-field v-model="nftForm.contract_address" placeholder="Contract address (0x...)" density="compact" hide-details style="min-width: 200px;" />
          <v-text-field v-model="nftForm.deploy_tx_hash" placeholder="Deploy tx hash (optional)" density="compact" hide-details style="min-width: 180px;" />
          <v-btn color="primary" :loading="nftLoading" :disabled="!nftForm.contract_address" @click="registerAgentNftContract">Register</v-btn>
        </div>
        <p v-if="nftSuccess" class="text-success text-body-2">{{ nftSuccess }}</p>
        <p v-if="nftError" class="text-error text-body-2">{{ nftError }}</p>

        <v-dialog v-model="editModal" max-width="520" persistent>
          <v-card v-if="editModal" class="pa-4">
            <h4 class="text-h6 mb-3">Edit contract — {{ editModal.network }}</h4>
            <div class="d-flex flex-column gap-2 mb-3">
              <v-text-field v-model="editForm.network" label="Network" density="compact" hide-details />
              <v-text-field v-model.number="editForm.chain_id" type="number" label="Chain ID" density="compact" hide-details />
              <v-text-field v-model="editForm.contract_address" label="Contract address" density="compact" hide-details />
              <v-text-field v-model="editForm.deploy_tx_hash" label="Deploy tx hash (optional)" density="compact" hide-details />
            </div>
            <div class="d-flex gap-2">
              <v-btn variant="outlined" @click="editModal = null">Cancel</v-btn>
              <v-btn color="primary" :loading="editLoading" @click="submitEdit">Save</v-btn>
            </div>
            <p v-if="editError" class="text-error text-body-2 mt-3 mb-0">{{ editError }}</p>
          </v-card>
        </v-dialog>

        <v-dialog v-model="verifyModal" max-width="600" persistent>
          <v-card v-if="verifyModal" class="pa-4">
            <h4 class="text-h6 mb-2">Verify {{ verifyModal.network }} on Snowtrace</h4>
            <p class="text-caption text-medium-emphasis mb-3">Paste flattened Solidity source (single file). Or use: npx hardhat verify --network {{ verifyModal.network }} &lt;address&gt; "Workmage Agent Identity" "WMAI" "&lt;base_uri&gt;"</p>
            <v-textarea v-model="verifyForm.source_code" placeholder="// SPDX-License-Identifier: MIT..." rows="12" density="compact" class="mb-3 font-monospace" />
            <div class="d-flex gap-2 mb-3">
              <v-text-field v-model="verifyForm.contract_name" placeholder="Contract name" density="compact" hide-details />
              <v-text-field v-model="verifyForm.compiler_version" placeholder="Compiler version" density="compact" hide-details />
            </div>
            <div class="d-flex gap-2">
              <v-btn variant="outlined" @click="verifyModal = null">Cancel</v-btn>
              <v-btn color="primary" :loading="verifySubmitting" :disabled="!verifyForm.source_code" @click="submitVerify(verifyModal.network)">Submit verification</v-btn>
            </div>
            <p v-if="verifyResult" class="text-success text-body-2 mt-3 mb-0">{{ verifyResult }}</p>
            <p v-if="verifyError" class="text-error text-body-2 mt-3 mb-0">{{ verifyError }}</p>
          </v-card>
        </v-dialog>
      </v-window-item>

      <!-- Moderator invites -->
      <v-window-item value="invites">
        <div class="d-flex gap-2 mb-4">
          <v-text-field v-model="inviteEmail" type="email" placeholder="moderator@example.com" density="compact" hide-details class="flex-grow-1" style="max-width: 280px;" />
          <v-btn color="primary" :loading="inviteLoading" :disabled="!inviteEmail" @click="createInvite">Invite Moderator</v-btn>
        </div>
        <p v-if="inviteSuccess" class="text-success text-body-2">{{ inviteSuccess }}</p>
        <p v-if="inviteError" class="text-error text-body-2">{{ inviteError }}</p>
        <div v-if="invitesLoading" class="text-medium-emphasis py-4">Loading invites...</div>
        <ul v-else class="pa-0 ma-0" style="list-style: none;">
          <li v-for="i in invites" :key="i.id" class="py-2 border-b">{{ i.email }} — {{ i.accepted_at ? 'Accepted' : (i.expires_at ? `Expires ${formatDate(i.expires_at)}` : '') }}</li>
        </ul>
      </v-window-item>
    </v-window>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useAuthStore } from '@/stores/auth'
import api from '@/services/api'

const authStore = useAuthStore()
const tab = ref('pending')

const pendingAgents = ref([])
const pendingLoading = ref(true)
const pendingChains = ref([])
const pendingChainsLoading = ref(true)
const invites = ref([])
const invitesLoading = ref(false)
const inviteEmail = ref('')
const inviteLoading = ref(false)
const inviteSuccess = ref('')
const inviteError = ref('')

const agentNftContracts = ref([])
const agentNftLoading = ref(false)
const nftForm = ref({ network: 'fuji', chain_id: 43113, contract_address: '', deploy_tx_hash: '' })
const nftLoading = ref(false)
const nftSuccess = ref('')
const nftError = ref('')
const verifyModal = ref(null)
const verifyForm = ref({ source_code: '', contract_name: 'WorkmageAgentNFT', compiler_version: 'v0.8.20+commit.a1b79de6' })
const verifySubmitting = ref(false)
const verifyResult = ref('')
const verifyError = ref('')
const verifyStatusLoading = ref(null)
const editModal = ref(null)
const editForm = ref({ network: '', chain_id: 0, contract_address: '', deploy_tx_hash: '' })
const editLoading = ref(false)
const editError = ref('')
const deleteLoading = ref(null)

const pendingCount = computed(() => pendingAgents.value.length)
const pendingChainCount = computed(() => pendingChains.value.length)

function formatDate(s) {
  if (!s) return ''
  const d = new Date(s)
  return d.toLocaleDateString()
}

async function loadPending() {
  pendingLoading.value = true
  try {
    const { data } = await api.get('/admin/agents/pending')
    pendingAgents.value = data
  } catch (e) {
    console.error(e)
    pendingAgents.value = []
  } finally {
    pendingLoading.value = false
  }
}

async function loadPendingChains() {
  pendingChainsLoading.value = true
  try {
    const { data } = await api.get('/admin/chains/pending')
    pendingChains.value = data || []
  } catch (_e) {
    pendingChains.value = []
  } finally {
    pendingChainsLoading.value = false
  }
}

async function approve(id) {
  try {
    await api.post(`/admin/agents/${id}/approve`)
    await loadPending()
  } catch (e) {
    alert(e.response?.data?.detail || 'Failed to approve')
  }
}

async function reject(id) {
  const reason = prompt('Rejection reason (optional):')
  if (reason === null) return
  try {
    await api.post(`/admin/agents/${id}/reject`, { reason: reason || undefined })
    await loadPending()
  } catch (e) {
    alert(e.response?.data?.detail || 'Failed to reject')
  }
}

async function approveChain(id) {
  try {
    await api.post(`/admin/chains/${id}/approve`)
    await loadPendingChains()
  } catch (e) {
    alert(e.response?.data?.detail || 'Failed to approve')
  }
}

async function rejectChain(id) {
  const reason = prompt('Rejection reason (optional):')
  if (reason === null) return
  try {
    await api.post(`/admin/chains/${id}/reject`, { reason: reason || undefined })
    await loadPendingChains()
  } catch (e) {
    alert(e.response?.data?.detail || 'Failed to reject')
  }
}

async function loadInvites() {
  invitesLoading.value = true
  inviteSuccess.value = ''
  inviteError.value = ''
  try {
    const { data } = await api.get('/admin/invites')
    invites.value = data
  } catch (e) {
    invites.value = []
  } finally {
    invitesLoading.value = false
  }
}

async function createInvite() {
  inviteLoading.value = true
  inviteSuccess.value = ''
  inviteError.value = ''
  try {
    const { data } = await api.post('/admin/invites', { email: inviteEmail.value })
    inviteSuccess.value = `Invite sent! Share this link: ${window.location.origin}/admin/accept-invite?token=${data.token}`
    inviteEmail.value = ''
    await loadInvites()
  } catch (e) {
    inviteError.value = e.response?.data?.detail || 'Failed to create invite'
  } finally {
    inviteLoading.value = false
  }
}

async function loadAgentNftContracts() {
  agentNftLoading.value = true
  try {
    const { data } = await api.get('/admin/agent-nft-contracts')
    agentNftContracts.value = data || []
  } catch (e) {
    agentNftContracts.value = []
  } finally {
    agentNftLoading.value = false
  }
}

async function registerAgentNftContract() {
  nftLoading.value = true
  nftSuccess.value = ''
  nftError.value = ''
  try {
    await api.post('/admin/agent-nft-contracts', {
      network: nftForm.value.network,
      chain_id: nftForm.value.chain_id,
      contract_address: nftForm.value.contract_address.trim(),
      deploy_tx_hash: nftForm.value.deploy_tx_hash || undefined
    })
    nftSuccess.value = 'Contract registered.'
    nftForm.value.contract_address = ''
    nftForm.value.deploy_tx_hash = ''
    await loadAgentNftContracts()
  } catch (e) {
    nftError.value = e.response?.data?.detail?.message || e.response?.data?.detail || 'Failed to register'
  } finally {
    nftLoading.value = false
  }
}

function openEditModal(contract) {
  editModal.value = contract
  editForm.value = {
    network: contract.network,
    chain_id: contract.chain_id,
    contract_address: contract.contract_address,
    deploy_tx_hash: contract.deploy_tx_hash || ''
  }
  editError.value = ''
}

async function submitEdit() {
  if (!editModal.value) return
  editLoading.value = true
  editError.value = ''
  try {
    await api.put(`/admin/agent-nft-contracts/${editModal.value.id}`, {
      network: editForm.value.network,
      chain_id: editForm.value.chain_id,
      contract_address: editForm.value.contract_address?.trim(),
      deploy_tx_hash: editForm.value.deploy_tx_hash || null
    })
    editModal.value = null
    await loadAgentNftContracts()
  } catch (e) {
    editError.value = e.response?.data?.detail?.message || e.response?.data?.detail || 'Update failed'
  } finally {
    editLoading.value = false
  }
}

async function deleteAgentNftContract(contract) {
  if (!confirm(`Remove agent NFT contract for ${contract.network}? This cannot be undone.`)) return
  deleteLoading.value = contract.id
  try {
    await api.delete(`/admin/agent-nft-contracts/${contract.id}`)
    await loadAgentNftContracts()
  } catch (e) {
    alert(e.response?.data?.detail?.message || e.response?.data?.detail || 'Delete failed')
  } finally {
    deleteLoading.value = null
  }
}

function openVerifyModal(contract) {
  verifyModal.value = contract
  verifyForm.value = { source_code: '', contract_name: 'WorkmageAgentNFT', compiler_version: 'v0.8.20+commit.a1b79de6' }
  verifyResult.value = ''
  verifyError.value = ''
}

async function submitVerify(network) {
  verifySubmitting.value = true
  verifyResult.value = ''
  verifyError.value = ''
  try {
    const { data } = await api.post(`/admin/agent-nft-contracts/${network}/verify`, {
      source_code: verifyForm.value.source_code,
      contract_name: verifyForm.value.contract_name,
      compiler_version: verifyForm.value.compiler_version
    })
    if (data.ok && data.guid) {
      verifyResult.value = `Submitted. GUID: ${data.guid}. Click "Check verification status" in a few seconds.`
    } else {
      verifyError.value = data.error || JSON.stringify(data)
    }
  } catch (e) {
    verifyError.value = e.response?.data?.detail || e.response?.data?.error || 'Verification submit failed'
  } finally {
    verifySubmitting.value = false
  }
}

async function checkVerifyStatus(network) {
  verifyStatusLoading.value = network
  try {
    const { data } = await api.post(`/admin/agent-nft-contracts/${network}/verify-status`)
    if (data.verified) {
      await loadAgentNftContracts()
    }
    if (data.error) {
      alert(data.error)
    } else if (data.verified) {
      alert('Contract is now verified on Snowtrace.')
    } else if (data.pending) {
      alert('Verification still pending. Try again in a moment.')
    } else {
      alert(data.message || JSON.stringify(data))
    }
  } catch (e) {
    alert(e.response?.data?.detail || 'Failed to check status')
  } finally {
    verifyStatusLoading.value = null
  }
}

onMounted(() => {
  loadPending()
  loadPendingChains()
})
</script>

<style scoped>
.border-b { border-bottom: 1px solid rgba(255,255,255,0.12); }
</style>

<template>
  <div class="admin-panel">
    <h1>Admin Panel</h1>
    <p class="role-badge" :class="authStore.user?.role">{{ authStore.user?.role }}</p>

    <div class="tabs">
      <button
        :class="{ active: tab === 'pending' }"
        @click="tab = 'pending'"
      >
        Pending Agents ({{ pendingCount }})
      </button>
      <button
        :class="{ active: tab === 'pendingChains' }"
        @click="tab = 'pendingChains'; loadPendingChains()"
      >
        Pending Chains ({{ pendingChainCount }})
      </button>
      <button
        v-if="authStore.user?.role === 'admin'"
        :class="{ active: tab === 'invites' }"
        @click="tab = 'invites'; loadInvites()"
      >
        Moderator Invites
      </button>
      <button
        v-if="authStore.user?.role === 'admin'"
        :class="{ active: tab === 'agentNft' }"
        @click="tab = 'agentNft'; loadAgentNftContracts()"
      >
        Agent NFT Contracts
      </button>
    </div>

    <!-- Pending agents -->
    <div v-show="tab === 'pending'" class="section">
      <div v-if="pendingLoading" class="loading">Loading...</div>
      <div v-else-if="pendingAgents.length === 0" class="empty">No agents pending approval.</div>
      <div v-else class="pending-list">
        <div
          v-for="a in pendingAgents"
          :key="a.id"
          class="pending-card"
        >
          <div class="pending-info">
            <strong>{{ a.name }}</strong>
            <span class="meta">ID {{ a.id }} · Expert {{ a.expert_id }}</span>
          </div>
          <div class="pending-actions">
            <router-link :to="`/admin/review/${a.id}`" class="btn small">Review</router-link>
            <button @click="approve(a.id)" class="btn small primary">Approve</button>
            <button @click="reject(a.id)" class="btn small danger">Reject</button>
          </div>
        </div>
      </div>
    </div>

    <!-- Pending chains -->
    <div v-show="tab === 'pendingChains'" class="section">
      <div v-if="pendingChainsLoading" class="loading">Loading...</div>
      <div v-else-if="pendingChains.length === 0" class="empty">No chains pending approval.</div>
      <div v-else class="pending-list">
        <div
          v-for="c in pendingChains"
          :key="c.id"
          class="pending-card"
        >
          <div class="pending-info">
            <strong>{{ c.name }}</strong>
            <span class="meta">ID {{ c.id }} · Expert {{ c.expert_id }}</span>
          </div>
          <div class="pending-actions">
            <router-link :to="`/admin/review-chain/${c.id}`" class="btn small">Review</router-link>
            <button @click="approveChain(c.id)" class="btn small primary">Approve</button>
            <button @click="rejectChain(c.id)" class="btn small danger">Reject</button>
          </div>
        </div>
      </div>
    </div>

    <!-- Agent NFT contracts (admin only) -->
    <div v-show="tab === 'agentNft'" class="section">
      <h3>Registered shared agent NFT contracts</h3>
      <div v-if="agentNftLoading" class="loading">Loading...</div>
      <div v-else class="agent-nft-list">
        <div v-for="c in agentNftContracts" :key="c.network" class="nft-card">
          <div class="nft-info">
            <strong>{{ c.network }}</strong>
            <span class="meta">Chain {{ c.chain_id }} · {{ c.contract_address }}</span>
            <span class="meta" v-if="c.deploy_tx_hash">Tx: {{ c.deploy_tx_hash }}</span>
            <span class="meta verified" v-if="c.verified_at">Verified {{ formatDate(c.verified_at) }}</span>
          </div>
          <div class="nft-actions">
            <button @click="openVerifyModal(c)" class="btn small">Verify on Snowtrace</button>
            <button @click="checkVerifyStatus(c.network)" class="btn small" :disabled="verifyStatusLoading === c.network">
              {{ verifyStatusLoading === c.network ? 'Checking...' : 'Check verification status' }}
            </button>
          </div>
        </div>
        <p v-if="agentNftContracts.length === 0" class="empty">No contracts registered. Register one below.</p>
      </div>
      <h3 class="mt-2">Register contract</h3>
      <div class="nft-form">
        <input v-model="nftForm.network" placeholder="Network (fuji or avalanche)" />
        <input v-model.number="nftForm.chain_id" type="number" placeholder="Chain ID (43113 or 43114)" />
        <input v-model="nftForm.contract_address" placeholder="Contract address (0x...)" />
        <input v-model="nftForm.deploy_tx_hash" placeholder="Deploy tx hash (optional)" />
        <button @click="registerAgentNftContract" class="btn primary" :disabled="nftLoading || !nftForm.contract_address">
          {{ nftLoading ? 'Registering...' : 'Register' }}
        </button>
      </div>
      <p v-if="nftSuccess" class="success">{{ nftSuccess }}</p>
      <p v-if="nftError" class="error">{{ nftError }}</p>

      <!-- Verify modal -->
      <div v-if="verifyModal" class="modal-overlay" @click.self="verifyModal = null">
        <div class="modal">
          <h4>Verify {{ verifyModal.network }} on Snowtrace</h4>
          <p class="hint">Paste flattened Solidity source (single file). Or use: npx hardhat verify --network {{ verifyModal.network }} &lt;address&gt; "Workmage Agent Identity" "WMAI" "&lt;base_uri&gt;"</p>
          <textarea v-model="verifyForm.source_code" placeholder="// SPDX-License-Identifier: MIT&#10;pragma solidity ^0.8.20;&#10;..." rows="12" />
          <div class="form-row">
            <input v-model="verifyForm.contract_name" placeholder="Contract name (e.g. WorkmageAgentNFT)" />
            <input v-model="verifyForm.compiler_version" placeholder="Compiler (e.g. v0.8.20+commit.a1b79de6)" />
          </div>
          <div class="modal-actions">
            <button @click="verifyModal = null" class="btn">Cancel</button>
            <button @click="submitVerify(verifyModal.network)" class="btn primary" :disabled="verifySubmitting || !verifyForm.source_code">
              {{ verifySubmitting ? 'Submitting...' : 'Submit verification' }}
            </button>
          </div>
          <p v-if="verifyResult" class="success">{{ verifyResult }}</p>
          <p v-if="verifyError" class="error">{{ verifyError }}</p>
        </div>
      </div>
    </div>

    <!-- Moderator invites (admin only) -->
    <div v-show="tab === 'invites'" class="section">
      <div class="invite-form">
        <input v-model="inviteEmail" type="email" placeholder="moderator@example.com" />
        <button @click="createInvite" class="btn primary" :disabled="inviteLoading || !inviteEmail">
          Invite Moderator
        </button>
      </div>
      <p v-if="inviteSuccess" class="success">{{ inviteSuccess }}</p>
      <p v-if="inviteError" class="error">{{ inviteError }}</p>
      <div v-if="invitesLoading" class="loading">Loading invites...</div>
      <ul v-else class="invites-list">
        <li v-for="i in invites" :key="i.id">
          {{ i.email }} — {{ i.accepted_at ? 'Accepted' : (i.expires_at ? `Expires ${formatDate(i.expires_at)}` : '') }}
        </li>
      </ul>
    </div>
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
.admin-panel { max-width: 900px; }
.role-badge {
  font-size: 0.875rem;
  padding: 0.25rem 0.5rem;
  border-radius: 4px;
  display: inline-block;
  margin-bottom: 1rem;
}
.role-badge.admin { background: var(--wm-primary); color: var(--wm-white); }
.role-badge.moderator { background: #0ea5e9; color: white; }
.tabs { display: flex; gap: 0.5rem; margin-bottom: 1.5rem; }
.tabs button {
  padding: 0.5rem 1rem;
  border: 1px solid var(--wm-border);
  background: var(--wm-bg-soft);
  color: var(--wm-text);
  border-radius: 6px;
  cursor: pointer;
}
.tabs button.active { background: var(--wm-primary); border-color: var(--wm-primary); }
.section { margin-top: 1rem; }
.loading, .empty { color: var(--wm-text-muted); }
.success { color: #34d399; margin-top: 0.5rem; }
.error { color: var(--wm-danger); margin-top: 0.5rem; }
.pending-list { display: flex; flex-direction: column; gap: 0.5rem; }
.pending-card {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1rem;
  border: 1px solid var(--wm-border);
  border-radius: 8px;
  background: var(--wm-bg-soft);
}
.pending-info .meta { display: block; font-size: 0.8rem; color: var(--wm-text-muted); }
.pending-actions { display: flex; gap: 0.5rem; }
.btn { padding: 0.35rem 0.75rem; border-radius: 6px; border: none; cursor: pointer; text-decoration: none; font-size: 0.875rem; }
.btn.small { padding: 0.25rem 0.5rem; }
.btn.primary { background: var(--wm-primary); color: var(--wm-white); }
.btn.danger { background: #dc2626; color: white; }
.invite-form { display: flex; gap: 0.5rem; margin-bottom: 1rem; }
.invite-form input {
  flex: 1;
  padding: 0.5rem;
  border: 1px solid var(--wm-border);
  border-radius: 6px;
  background: var(--wm-bg-soft);
  color: var(--wm-text);
}
.invites-list { list-style: none; padding: 0; }
.invites-list li { padding: 0.5rem 0; border-bottom: 1px solid var(--wm-border); }

.mt-2 { margin-top: 1.5rem; }
.agent-nft-list { display: flex; flex-direction: column; gap: 0.5rem; margin-bottom: 1.5rem; }
.nft-card {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  flex-wrap: wrap;
  gap: 0.75rem;
  padding: 1rem;
  border: 1px solid var(--wm-border);
  border-radius: 8px;
  background: var(--wm-bg-soft);
}
.nft-info { display: flex; flex-direction: column; gap: 0.25rem; }
.nft-info .meta { font-size: 0.8rem; color: var(--wm-text-muted); word-break: break-all; }
.nft-info .meta.verified { color: #34d399; }
.nft-actions { display: flex; gap: 0.5rem; flex-shrink: 0; }
.nft-form {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  align-items: center;
}
.nft-form input {
  padding: 0.5rem;
  border: 1px solid var(--wm-border);
  border-radius: 6px;
  background: var(--wm-bg-soft);
  color: var(--wm-text);
  min-width: 140px;
}
.nft-form input[type="number"] { width: 120px; }
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0,0,0,0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 100;
}
.modal {
  background: var(--wm-bg-soft);
  border: 1px solid var(--wm-border);
  border-radius: 8px;
  padding: 1.5rem;
  max-width: 600px;
  width: 90%;
  max-height: 90vh;
  overflow: auto;
}
.modal h4 { margin-top: 0; }
.modal .hint { font-size: 0.8rem; color: var(--wm-text-muted); margin-bottom: 0.75rem; }
.modal textarea {
  width: 100%;
  font-family: monospace;
  font-size: 0.8rem;
  padding: 0.5rem;
  border: 1px solid var(--wm-border);
  border-radius: 6px;
  background: var(--wm-bg);
  color: var(--wm-text);
  margin-bottom: 0.75rem;
}
.modal .form-row { display: flex; gap: 0.5rem; margin-bottom: 0.75rem; }
.modal .form-row input { flex: 1; padding: 0.5rem; border: 1px solid var(--wm-border); border-radius: 6px; background: var(--wm-bg); color: var(--wm-text); }
.modal-actions { display: flex; gap: 0.5rem; margin-top: 1rem; }
</style>

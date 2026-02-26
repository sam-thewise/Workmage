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
.role-badge.admin { background: #7c3aed; color: white; }
.role-badge.moderator { background: #0ea5e9; color: white; }
.tabs { display: flex; gap: 0.5rem; margin-bottom: 1.5rem; }
.tabs button {
  padding: 0.5rem 1rem;
  border: 1px solid #334155;
  background: #1e293b;
  color: #e2e8f0;
  border-radius: 6px;
  cursor: pointer;
}
.tabs button.active { background: #7c3aed; border-color: #7c3aed; }
.section { margin-top: 1rem; }
.loading, .empty { color: #94a3b8; }
.success { color: #34d399; margin-top: 0.5rem; }
.error { color: #f87171; margin-top: 0.5rem; }
.pending-list { display: flex; flex-direction: column; gap: 0.5rem; }
.pending-card {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1rem;
  border: 1px solid #334155;
  border-radius: 8px;
  background: #1e293b;
}
.pending-info .meta { display: block; font-size: 0.8rem; color: #64748b; }
.pending-actions { display: flex; gap: 0.5rem; }
.btn { padding: 0.35rem 0.75rem; border-radius: 6px; border: none; cursor: pointer; text-decoration: none; font-size: 0.875rem; }
.btn.small { padding: 0.25rem 0.5rem; }
.btn.primary { background: #7c3aed; color: white; }
.btn.danger { background: #dc2626; color: white; }
.invite-form { display: flex; gap: 0.5rem; margin-bottom: 1rem; }
.invite-form input {
  flex: 1;
  padding: 0.5rem;
  border: 1px solid #334155;
  border-radius: 6px;
  background: #1e293b;
  color: #e2e8f0;
}
.invites-list { list-style: none; padding: 0; }
.invites-list li { padding: 0.5rem 0; border-bottom: 1px solid #334155; }
</style>

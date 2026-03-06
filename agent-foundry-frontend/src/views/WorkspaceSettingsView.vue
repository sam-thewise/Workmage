<template>
  <div class="workspace-settings">
    <h1 class="text-h4 mb-4">{{ workspace?.name || 'Workspace' }} – Settings</h1>
    <p v-if="!canManage" class="text-body-2 text-medium-emphasis">You can view this workspace. Only owners and admins can manage members and secrets.</p>

    <v-card class="pa-4 mb-4">
      <v-card-title>Members</v-card-title>
      <v-divider class="my-2" />
      <v-table v-if="members.length">
        <thead>
          <tr>
            <th>Email</th>
            <th>Role</th>
            <th v-if="canManage">Actions</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="m in members" :key="m.user_id">
            <td>{{ m.email }}</td>
            <td><v-chip size="small">{{ m.role }}</v-chip></td>
            <td v-if="canManage">
              <v-btn v-if="m.role !== 'owner'" size="small" variant="text" color="error" @click="removeMember(m.user_id)">Remove</v-btn>
            </td>
          </tr>
        </tbody>
      </v-table>
      <p v-else-if="!loadingMembers">No members.</p>
      <p v-else>Loading…</p>
      <template v-if="canManage">
        <v-divider class="my-3" />
        <div class="d-flex align-center gap-2 flex-wrap">
          <v-text-field v-model="inviteEmail" label="Invite by email" type="email" density="compact" hide-details style="max-width: 240px" />
          <v-select v-model="inviteRole" :items="['admin','member','viewer']" density="compact" hide-details style="max-width: 120px" />
          <v-btn color="primary" :loading="inviting" @click="inviteMember">Invite</v-btn>
        </div>
      </template>
    </v-card>

    <v-card v-if="canManage" class="pa-4">
      <v-card-title>Secrets</v-card-title>
      <v-divider class="my-2" />
      <p class="text-body-2 text-medium-emphasis mb-2">Secret key names (values are not shown). Used by AI team runs as environment variables.</p>
      <v-list v-if="secrets.length" density="compact">
        <v-list-item v-for="s in secrets" :key="s.key_name + (s.chain_id || '')">
          <template #prepend><v-icon>mdi-key</v-icon></template>
          <v-list-item-title>{{ s.key_name }}{{ s.chain_id ? ' (AI team #' + s.chain_id + ')' : '' }}</v-list-item-title>
          <template #append>
            <v-btn size="small" variant="text" color="error" @click="deleteSecret(s.key_name, s.chain_id)">Delete</v-btn>
          </template>
        </v-list-item>
      </v-list>
      <p v-else-if="!loadingSecrets">No secrets.</p>
      <p v-else>Loading…</p>
      <v-divider class="my-3" />
      <div class="d-flex align-center gap-2 flex-wrap">
        <v-text-field v-model="newSecretName" label="Key name" density="compact" hide-details style="max-width: 200px" placeholder="e.g. API_KEY" />
        <v-text-field v-model="newSecretValue" label="Value" type="password" density="compact" hide-details style="max-width: 240px" placeholder="••••••••" />
        <v-btn color="primary" :loading="addingSecret" :disabled="!newSecretName || !newSecretValue" @click="addSecret">Add secret</v-btn>
      </div>
    </v-card>
  </div>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'
import { useRoute } from 'vue-router'
import api from '@/services/api'
import { useWorkspaceStore } from '@/stores/workspace'

const route = useRoute()
const workspaceStore = useWorkspaceStore()
const workspaceId = computed(() => Number(route.params.id))
const workspace = ref(null)
const members = ref([])
const secrets = ref([])
const loadingMembers = ref(true)
const loadingSecrets = ref(true)
const inviteEmail = ref('')
const inviteRole = ref('member')
const inviting = ref(false)
const newSecretName = ref('')
const newSecretValue = ref('')
const addingSecret = ref(false)

const canManage = computed(() => {
  const w = workspace.value
  const role = w?.role ?? workspaceStore.workspaces.find((x) => x.id === workspaceId.value)?.role
  return role === 'owner' || role === 'admin'
})

async function loadWorkspace() {
  try {
    const { data } = await api.get(`/workspaces/${workspaceId.value}`)
    const fromList = workspaceStore.workspaces.find((w) => w.id === workspaceId.value)
    workspace.value = { ...data, role: fromList?.role }
  } catch {
    workspace.value = null
  }
}

async function loadMembers() {
  loadingMembers.value = true
  try {
    const { data } = await api.get(`/workspaces/${workspaceId.value}/members`)
    members.value = data || []
  } catch {
    members.value = []
  } finally {
    loadingMembers.value = false
  }
}

async function loadSecrets() {
  if (!canManage.value) return
  loadingSecrets.value = true
  try {
    const { data } = await api.get(`/workspaces/${workspaceId.value}/secrets`)
    secrets.value = data || []
  } catch {
    secrets.value = []
  } finally {
    loadingSecrets.value = false
  }
}

async function inviteMember() {
  if (!inviteEmail.value) return
  inviting.value = true
  try {
    await api.post(`/workspaces/${workspaceId.value}/members`, { email: inviteEmail.value, role: inviteRole.value })
    inviteEmail.value = ''
    await loadMembers()
  } finally {
    inviting.value = false
  }
}

async function removeMember(userId) {
  try {
    await api.delete(`/workspaces/${workspaceId.value}/members/${userId}`)
    await loadMembers()
  } catch {}
}

async function addSecret() {
  if (!newSecretName.value || !newSecretValue.value) return
  addingSecret.value = true
  try {
    await api.post(`/workspaces/${workspaceId.value}/secrets`, {
      key_name: newSecretName.value,
      value: newSecretValue.value
    })
    newSecretName.value = ''
    newSecretValue.value = ''
    await loadSecrets()
  } finally {
    addingSecret.value = false
  }
}

async function deleteSecret(keyName, chainId) {
  try {
    const params = chainId != null ? { chain_id: chainId } : {}
    await api.delete(`/workspaces/${workspaceId.value}/secrets/${encodeURIComponent(keyName)}`, { params })
    await loadSecrets()
  } catch {}
}

onMounted(async () => {
  await workspaceStore.fetchWorkspaces()
  await loadWorkspace()
  await loadMembers()
  await loadSecrets()
})
</script>

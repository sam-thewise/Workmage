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

    <v-card v-if="canEditTeams" class="pa-4 mb-4">
      <v-card-title>Personalities</v-card-title>
      <v-divider class="my-2" />
      <p class="text-body-2 text-medium-emphasis mb-2">Tone tools for AI team runs. Add personalities here, then use them in chain builder.</p>
      <v-list v-if="personalities.length" density="compact">
        <v-list-item v-for="p in personalities" :key="p.id">
          <template #prepend><v-icon>mdi-face-profile</v-icon></template>
          <v-list-item-title>{{ p.name }}{{ p.chain_id ? ' (AI team #' + p.chain_id + ')' : '' }}</v-list-item-title>
          <template #append>
            <v-btn size="small" variant="text" @click="editPersonality(p)">Edit</v-btn>
            <v-btn size="small" variant="text" color="error" @click="deletePersonality(p.id)">Delete</v-btn>
          </template>
        </v-list-item>
      </v-list>
      <p v-else-if="!loadingPersonalities">No personalities. Add one below.</p>
      <p v-else>Loading…</p>
      <v-divider class="my-3" />
      <div class="d-flex flex-column gap-2">
        <v-text-field v-model="newPersonalityName" label="Name" density="compact" hide-details style="max-width: 280px" placeholder="e.g. Marketing voice" />
        <v-textarea v-model="newPersonalityContent" label="Content" density="compact" hide-details rows="4" placeholder="Describe the tone and voice for content generation…" />
        <v-btn color="primary" :loading="addingPersonality" :disabled="!newPersonalityName?.trim()" @click="addPersonality">Add personality</v-btn>
      </div>
    </v-card>

    <v-dialog v-model="editPersonalityDialog" max-width="500" persistent>
      <v-card v-if="editingPersonality" class="pa-4">
        <v-card-title>Edit personality</v-card-title>
        <v-divider class="my-2" />
        <v-text-field v-model="editingPersonality.name" label="Name" density="compact" hide-details class="mb-2" />
        <v-textarea v-model="editingPersonality.content" label="Content" density="compact" hide-details rows="4" />
        <div class="d-flex gap-2 mt-3">
          <v-btn @click="editPersonalityDialog = false">Cancel</v-btn>
          <v-btn color="primary" :loading="savingPersonality" @click="savePersonality">Save</v-btn>
        </div>
      </v-card>
    </v-dialog>

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

const canEditTeams = computed(() => {
  const w = workspace.value
  const role = w?.role ?? workspaceStore.workspaces.find((x) => x.id === workspaceId.value)?.role
  return role === 'owner' || role === 'admin' || role === 'member'
})

const personalities = ref([])
const loadingPersonalities = ref(true)
const newPersonalityName = ref('')
const newPersonalityContent = ref('')
const addingPersonality = ref(false)
const editPersonalityDialog = ref(false)
const editingPersonality = ref(null)
const savingPersonality = ref(false)

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

async function loadPersonalities() {
  if (!canEditTeams.value) return
  loadingPersonalities.value = true
  try {
    const { data } = await api.get(`/workspaces/${workspaceId.value}/personalities`)
    personalities.value = data || []
  } catch {
    personalities.value = []
  } finally {
    loadingPersonalities.value = false
  }
}

async function addPersonality() {
  if (!newPersonalityName.value?.trim()) return
  addingPersonality.value = true
  try {
    await api.post(`/workspaces/${workspaceId.value}/personalities`, {
      name: newPersonalityName.value.trim(),
      content: newPersonalityContent.value?.trim() || ''
    })
    newPersonalityName.value = ''
    newPersonalityContent.value = ''
    await loadPersonalities()
  } finally {
    addingPersonality.value = false
  }
}

async function editPersonality(p) {
  try {
    const { data } = await api.get(`/workspaces/${workspaceId.value}/personalities/${p.id}`)
    editingPersonality.value = { ...data }
    editPersonalityDialog.value = true
  } catch {}
}

async function savePersonality() {
  if (!editingPersonality.value) return
  savingPersonality.value = true
  try {
    await api.put(`/workspaces/${workspaceId.value}/personalities/${editingPersonality.value.id}`, {
      name: editingPersonality.value.name,
      content: editingPersonality.value.content
    })
    editPersonalityDialog.value = false
    editingPersonality.value = null
    await loadPersonalities()
  } finally {
    savingPersonality.value = false
  }
}

async function deletePersonality(personalityId) {
  if (!confirm('Delete this personality?')) return
  try {
    await api.delete(`/workspaces/${workspaceId.value}/personalities/${personalityId}`)
    await loadPersonalities()
  } catch {}
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
  await loadPersonalities()
  await loadSecrets()
})
</script>

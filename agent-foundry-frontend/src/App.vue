<template>
  <v-app>
    <v-app-bar color="secondary" density="compact">
      <v-avatar :tile="true">
        <img class="logo-img" src="/branding/workmage-icon.png" alt="Workmage" />
      </v-avatar>
      <v-app-bar-title>
        <h1 class="app-title">Workmage</h1>
      </v-app-bar-title>
      <v-spacer />
      <v-btn variant="text" color="on-surface" to="/">Home</v-btn>
      <v-btn variant="text" color="on-surface" to="/marketplace">Marketplace</v-btn>
      <v-btn variant="text" color="on-surface" to="/marketplace/chains">AI Team Marketplace</v-btn>
      <template v-if="authStore.isAuthenticated">
        <v-menu v-if="workspaceStore.workspaces.length" location="bottom" max-width="280">
          <template #activator="{ props: menuProps }">
            <v-btn v-bind="menuProps" variant="text" color="on-surface" size="small">
              {{ workspaceStore.currentWorkspace?.name || 'Workspace' }}
              <v-icon end size="small">mdi-chevron-down</v-icon>
            </v-btn>
          </template>
          <v-list density="compact">
            <v-list-item
              v-for="w in workspaceStore.workspaces"
              :key="w.id"
              :title="w.name"
              :subtitle="w.role"
              :active="w.id === workspaceStore.currentWorkspaceId"
              @click="workspaceStore.setCurrentWorkspace(w.id)"
            />
            <v-divider />
            <v-list-item
              v-if="workspaceStore.currentWorkspaceId"
              title="Workspace settings"
              :to="'/workspaces/' + workspaceStore.currentWorkspaceId + '/settings'"
            />
          </v-list>
        </v-menu>
        <v-btn variant="text" color="on-surface" to="/chains">My AI Teams</v-btn>
        <v-btn v-if="!foundersViewOnly && (authStore.user?.role === 'expert' || authStore.user?.role === 'admin')" variant="text" color="on-surface" to="/dashboard/agents">My AI Roles</v-btn>
        <v-btn v-if="!foundersViewOnly && (authStore.user?.role === 'admin' || authStore.user?.role === 'moderator')" variant="text" color="on-surface" to="/admin">Admin</v-btn>
        <v-btn variant="text" color="on-surface" to="/dashboard">Dashboard</v-btn>
        <v-btn variant="text" color="on-surface" to="/wizard">Quick start wizard</v-btn>
        <v-btn variant="text" color="on-surface" to="/run">Run AI Role</v-btn>
        <v-btn variant="text" color="on-surface" to="/runs">Run history</v-btn>
        <v-btn variant="text" color="on-surface" to="/settings/keys">API Keys</v-btn>
        <v-menu location="bottom end" :close-on-content-click="false" max-width="360">
          <template #activator="{ props: menuProps }">
            <v-badge :content="notificationCount" :model-value="notificationCount > 0" color="error" overlap>
              <v-btn v-bind="menuProps" icon variant="text" color="on-surface" aria-label="Notifications">
                <v-icon>mdi-bell</v-icon>
              </v-btn>
            </v-badge>
          </template>
          <v-card min-width="320">
            <v-card-title class="d-flex align-center justify-space-between">
              <span>Notifications</span>
              <v-btn variant="text" size="small" to="/runs">View all</v-btn>
            </v-card-title>
            <v-divider />
            <v-list v-if="notificationItems.length" density="compact">
              <v-list-item
                v-for="item in notificationItems"
                :key="item.id"
                :to="'/runs?open=' + item.id"
                :subtitle="item.status === 'awaiting_approval' ? 'Needs your approval' : item.status === 'completed' ? 'Finished' : item.status === 'error' ? 'Failed' : item.status"
                @click="fetchNotifications"
              >
                <template #title>{{ item.chain_name || 'AI Team' }}</template>
                <template #prepend>
                  <v-icon :color="item.status === 'awaiting_approval' ? 'warning' : item.status === 'completed' ? 'success' : item.status === 'error' ? 'error' : 'default'">
                    {{ item.status === 'awaiting_approval' ? 'mdi-hand-back-right' : item.status === 'completed' ? 'mdi-check-circle' : item.status === 'error' ? 'mdi-alert-circle' : 'mdi-information' }}
                  </v-icon>
                </template>
              </v-list-item>
            </v-list>
            <v-list v-else>
              <v-list-item title="No new notifications" />
            </v-list>
          </v-card>
        </v-menu>
        <v-btn variant="flat" color="primary" @click="authStore.logout" class="ml-2">Logout</v-btn>
      </template>
      <template v-else>
        <v-btn variant="text" color="on-surface" to="/login">Login</v-btn>
        <v-btn variant="flat" color="primary" to="/register">Register</v-btn>
      </template>
    </v-app-bar>
    <v-main>
      <v-container class="py-6" max-width="1200">
        <router-view />
      </v-container>
    </v-main>
  </v-app>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { useWorkspaceStore } from '@/stores/workspace'
import api from '@/services/api'

const authStore = useAuthStore()
const workspaceStore = useWorkspaceStore()
const notificationCount = ref(0)

/** When true, only show menu items relevant to founders (hide My AI Roles, Admin). Set via VITE_FOUNDERS_VIEW_ONLY. */
const foundersViewOnly = import.meta.env.VITE_FOUNDERS_VIEW_ONLY === 'true' || import.meta.env.VITE_FOUNDERS_VIEW_ONLY === '1'
const notificationItems = ref([])
let notificationPollTimer = null

async function fetchNotifications() {
  if (!authStore.isAuthenticated) return
  try {
    const { data } = await api.get('/chains/runs', { params: { unread_only: true, limit: 20 } })
    notificationItems.value = data.items || []
    notificationCount.value = data.unread_count ?? notificationItems.value.length
  } catch {
    notificationItems.value = []
    notificationCount.value = 0
  }
}

onMounted(() => {
  if (authStore.isAuthenticated) {
    authStore.fetchUser()
    workspaceStore.fetchWorkspaces()
    fetchNotifications()
    notificationPollTimer = setInterval(fetchNotifications, 45000)
  }
})

onUnmounted(() => {
  if (notificationPollTimer) clearInterval(notificationPollTimer)
})
</script>

<style>
/* Keep legacy CSS vars for components that still reference them */
:root {
  --wm-font-body: 'Golos Text', system-ui, -apple-system, sans-serif;
  --wm-font-heading: 'Libre Caslon Text', Georgia, serif;
  --wm-white: #fefefe;
  --wm-primary: #190056;
  --wm-accent: #608bf7;
  --wm-surface: #fffdec;
  --wm-surface-alt: #fffbd7;
  --wm-bg: #120633;
  --wm-bg-soft: #1d0c5a;
  --wm-text: #fefefe;
  --wm-text-muted: #d7d3ee;
  --wm-border: #4f3b99;
  --wm-danger: #f87171;
}

.logo-img {
  max-width: 32px;
  max-height: 32px;
}

.app-title {
  margin: 0;
  font-family: var(--wm-font-heading);
  font-size: 1.25rem;
  font-weight: 700;
  line-height: 1.1;
}
</style>

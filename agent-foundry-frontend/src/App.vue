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
      <v-btn variant="text" color="on-surface" to="/marketplace/chains">Chain Marketplace</v-btn>
      <template v-if="authStore.isAuthenticated">
        <v-btn variant="text" color="on-surface" to="/chains">My Chains</v-btn>
        <v-btn v-if="authStore.user?.role === 'admin' || authStore.user?.role === 'moderator'" variant="text" color="on-surface" to="/admin">Admin</v-btn>
        <v-btn variant="text" color="on-surface" to="/dashboard">Dashboard</v-btn>
        <v-btn variant="text" color="on-surface" to="/run">Run Agent</v-btn>
        <v-btn variant="text" color="on-surface" to="/settings/keys">API Keys</v-btn>
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
import { onMounted } from 'vue'
import { useAuthStore } from '@/stores/auth'
const authStore = useAuthStore()
onMounted(() => {
  if (authStore.isAuthenticated) authStore.fetchUser()
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

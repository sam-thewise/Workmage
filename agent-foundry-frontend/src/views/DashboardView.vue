<template>
  <div class="dashboard">
    <img class="brand-logo mb-2" src="/branding/workmage-icon.png" alt="Workmage logo" />
    <h2 class="text-h5 mb-2">Workmage</h2>
    <h1 class="text-h4 mb-2">Dashboard</h1>
    <p class="mb-3">Welcome, {{ authStore.user?.email }}</p>
    <p v-if="authStore.user?.role === 'expert'" class="mb-4">
      <router-link to="/dashboard/agents" class="text-accent text-decoration-none">Manage your agents</router-link>
      &middot; <router-link to="/dashboard/wallets" class="text-accent text-decoration-none">Action wallets</router-link>
      &middot; <router-link to="/dashboard/settings" class="text-accent text-decoration-none">Settings</router-link>
      &middot; <router-link to="/run" class="text-accent text-decoration-none">Run Agent</router-link>
      &middot; <router-link to="/chains" class="text-accent text-decoration-none">Chains</router-link>
    </p>
    <p v-else class="mb-4">
      You can browse and run agents from the <router-link to="/marketplace" class="text-accent text-decoration-none">Marketplace</router-link>.
      <router-link to="/dashboard/wallets" class="text-accent text-decoration-none">Action wallets</router-link>
      &middot; <router-link to="/run" class="text-accent text-decoration-none">Run Agent</router-link>
      &middot; <router-link to="/chains" class="text-accent text-decoration-none">Chains</router-link>
    </p>
    <router-view />
  </div>
</template>

<script setup>
import { onMounted } from 'vue'
import { useAuthStore } from '@/stores/auth'

const authStore = useAuthStore()

onMounted(async () => {
  await authStore.fetchUser()
})
</script>

<style scoped>
.brand-logo {
  width: 88px;
  display: block;
}
</style>

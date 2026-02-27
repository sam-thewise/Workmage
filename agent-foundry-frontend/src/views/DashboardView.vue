<template>
  <div class="dashboard">
    <img class="brand-logo" src="/branding/workmage-icon.png" alt="Workmage logo" />
    <h2 class="brand-title">Workmage</h2>
    <h1>Dashboard</h1>
    <p>Welcome, {{ authStore.user?.email }}</p>
    <p v-if="authStore.user?.role === 'expert'">
      <router-link to="/dashboard/agents">Manage your agents</router-link>
      &middot; <router-link to="/dashboard/settings">Settings</router-link>
      &middot; <router-link to="/run">Run Agent</router-link>
      &middot; <router-link to="/chains">Chains</router-link>
    </p>
    <p v-else>
      You can browse and run agents from the <router-link to="/marketplace">Marketplace</router-link>.
      <router-link to="/run">Run Agent</router-link>
      &middot; <router-link to="/chains">Chains</router-link>
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
  margin-bottom: 0.5rem;
}
.brand-title {
  margin-bottom: 1rem;
}
</style>

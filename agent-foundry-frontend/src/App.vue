<template>
  <div id="app">
    <nav class="nav">
      <router-link to="/">Home</router-link>
      <router-link to="/marketplace">Marketplace</router-link>
      <router-link to="/chains">Chains</router-link>
      <template v-if="authStore.isAuthenticated">
        <router-link v-if="authStore.user?.role === 'admin' || authStore.user?.role === 'moderator'" to="/admin">Admin</router-link>
        <router-link to="/dashboard">Dashboard</router-link>
        <router-link to="/run">Run Agent</router-link>
        <router-link to="/settings/keys">API Keys</router-link>
        <button @click="authStore.logout">Logout</button>
      </template>
      <template v-else>
        <router-link to="/login">Login</router-link>
        <router-link to="/register">Register</router-link>
      </template>
    </nav>
    <main class="main">
      <router-view />
    </main>
  </div>
</template>

<script setup>
import { onMounted } from 'vue'
import { useAuthStore } from '@/stores/auth'
const authStore = useAuthStore()
onMounted(() => {
  if (authStore.isAuthenticated) authStore.fetchUser()
})
</script>

<style scoped>
.nav {
  display: flex;
  flex-wrap: wrap;
  gap: 1rem;
  padding: 1rem;
  background: #1a1a2e;
  color: white;
  align-items: center;
}
.nav a, .nav button {
  color: #eee;
  text-decoration: none;
}
.nav a:hover, .nav a.router-link-active {
  color: #7c3aed;
}
.main {
  padding: 2rem;
  max-width: 1200px;
  margin: 0 auto;
}
</style>

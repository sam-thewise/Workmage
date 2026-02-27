<template>
  <div id="app">
    <nav class="nav">
      <router-link to="/" class="brand">
        <img src="/branding/workmage-icon.png" alt="Workmage logo" />
        <span>Workmage</span>
      </router-link>
      <router-link to="/">Home</router-link>
      <router-link to="/marketplace">Marketplace</router-link>
      <router-link to="/marketplace/chains">Chain Marketplace</router-link>
      <template v-if="authStore.isAuthenticated">
        <router-link to="/chains">My Chains</router-link>
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
  background: var(--wm-bg-soft);
  color: var(--wm-white);
  align-items: center;
}
.brand {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  margin-right: 0.5rem;
  font-weight: 700;
}
.brand img {
  width: 28px;
  height: 28px;
  object-fit: contain;
}
.nav a, .nav button {
  color: var(--wm-white);
  text-decoration: none;
}
.nav a:hover, .nav a.router-link-active {
  color: var(--wm-accent);
}
.main {
  padding: 2rem;
  max-width: 1200px;
  margin: 0 auto;
}
</style>

<template>
  <div class="accept-invite">
    <h1>Moderator Invite</h1>
    <div v-if="!authStore.isAuthenticated" class="message">
      <p>Please log in to accept this invite.</p>
      <router-link :to="`/login?redirect=${encodeURIComponent(redirectTo)}`" class="btn primary">
        Log in
      </router-link>
    </div>
    <div v-else-if="loading" class="loading">Processing...</div>
    <div v-else-if="success" class="success">
      <p>You are now a moderator. <router-link to="/admin">Go to Admin Panel</router-link></p>
    </div>
    <div v-else-if="error" class="error">
      <p>{{ error }}</p>
      <router-link to="/">Go home</router-link>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import api from '@/services/api'

const authStore = useAuthStore()
const route = useRoute()
const token = route.query.token

const loading = ref(false)
const success = ref(false)
const error = ref('')

const redirectTo = ref(route.fullPath)

async function accept() {
  if (!token) {
    error.value = 'Invalid invite link: no token'
    return
  }
  loading.value = true
  error.value = ''
  try {
    await api.post('/admin/invites/accept', { token })
    await authStore.fetchUser()
    success.value = true
  } catch (e) {
    error.value = e.response?.data?.detail || 'Failed to accept invite'
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  if (!token) {
    error.value = 'Invalid invite link: no token'
    return
  }
  if (authStore.isAuthenticated) {
    accept()
  }
})
</script>

<style scoped>
.accept-invite { max-width: 400px; margin: 4rem auto; text-align: center; }
.message p, .success p, .error p { margin-bottom: 1rem; }
.btn { display: inline-block; padding: 0.5rem 1rem; background: #7c3aed; color: white; border-radius: 6px; text-decoration: none; }
.success { color: #34d399; }
.error { color: #f87171; }
</style>

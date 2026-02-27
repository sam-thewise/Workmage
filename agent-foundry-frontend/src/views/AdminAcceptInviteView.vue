<template>
  <div class="accept-invite mx-auto text-center pa-6" style="max-width: 400px;">
    <h1 class="text-h4 mb-4">Moderator Invite</h1>
    <div v-if="!authStore.isAuthenticated" class="message">
      <p class="mb-4">Please log in to accept this invite.</p>
      <v-btn color="primary" :to="`/login?redirect=${encodeURIComponent(redirectTo)}`">Log in</v-btn>
    </div>
    <div v-else-if="loading" class="text-medium-emphasis py-4">Processing...</div>
    <div v-else-if="success" class="success">
      <p class="mb-4">You are now a moderator. <router-link to="/admin" class="text-accent text-decoration-none">Go to Admin Panel</router-link></p>
    </div>
    <div v-else-if="error" class="error">
      <p class="text-error mb-4">{{ error }}</p>
      <router-link to="/" class="text-accent text-decoration-none">Go home</router-link>
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

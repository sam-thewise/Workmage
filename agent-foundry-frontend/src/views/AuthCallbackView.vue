<template>
  <div class="auth-callback mx-auto text-center pa-8" style="max-width: 400px;">
    <p v-if="loading" class="text-medium-emphasis">Completing sign in...</p>
    <p v-else-if="error" class="text-error">{{ error }}</p>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const authStore = useAuthStore()
const router = useRouter()
const route = useRoute()
const loading = ref(true)
const error = ref('')

onMounted(() => {
  const token = route.query.token
  const oauthError = route.query.oauth_error
  if (oauthError) {
    error.value = decodeURIComponent(oauthError)
    loading.value = false
    return
  }
  if (token) {
    authStore.setTokenFromOAuth(token)
    authStore.fetchUser().then(() => {
      router.replace('/dashboard')
    }).catch(() => {
      error.value = 'Failed to load user'
      loading.value = false
    })
  } else {
    error.value = 'No token received'
    loading.value = false
  }
})
</script>

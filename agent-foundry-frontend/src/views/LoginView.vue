<template>
  <div class="auth-form mx-auto pa-4" style="max-width: 400px;">
    <img class="brand-logo d-block mx-auto mb-2" src="/branding/workmage-icon.png" alt="Workmage logo" />
    <h2 class="text-h5 text-center mb-2">Workmage</h2>
    <h1 class="text-h4 mb-6">Login</h1>
    <div v-if="oauthProviders.google || oauthProviders.facebook || oauthProviders.x" class="oauth-buttons d-flex flex-column gap-2 mb-4">
      <a v-if="oauthProviders.google" :href="oauthUrls.google" class="oauth-btn google v-btn v-btn--block v-btn--flat">Continue with Google</a>
      <a v-if="oauthProviders.facebook" :href="oauthUrls.facebook" class="oauth-btn facebook v-btn v-btn--block v-btn--flat">Continue with Facebook</a>
      <a v-if="oauthProviders.x" :href="oauthUrls.x" class="oauth-btn x v-btn v-btn--block v-btn--flat">Continue with X</a>
    </div>
    <p v-if="oauthProviders.google || oauthProviders.facebook || oauthProviders.x" class="text-center text-medium-emphasis my-4">— or —</p>
    <v-form @submit.prevent="submit" class="d-flex flex-column gap-3">
      <v-text-field v-model="email" type="email" label="Email" required density="comfortable" />
      <v-text-field v-model="password" type="password" label="Password" required density="comfortable" />
      <p v-if="error" class="text-error text-body-2">{{ error }}</p>
      <v-btn type="submit" color="primary" block :loading="loading">Login</v-btn>
    </v-form>
    <p class="text-center mt-4">Don't have an account? <router-link to="/register" class="text-accent text-decoration-none">Register</router-link></p>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import api from '@/services/api'

const authStore = useAuthStore()
const router = useRouter()
const route = useRoute()
const redirect = route.query.redirect
const email = ref('')
const password = ref('')
const loading = ref(false)
const error = ref('')
const oauthProviders = ref({ google: false, facebook: false, x: false })

const apiBase = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1'
const oauthUrls = ref({
  google: `${apiBase}/auth/google/start`,
  facebook: `${apiBase}/auth/facebook/start`,
  x: `${apiBase}/auth/x/start`,
})

onMounted(async () => {
  try {
    const { data } = await api.get('/auth/oauth/providers')
    oauthProviders.value = data
  } catch (_) {
    oauthProviders.value = { google: false, facebook: false, x: false }
  }
  const oauthError = new URLSearchParams(window.location.search).get('oauth_error')
  if (oauthError) {
    error.value = decodeURIComponent(oauthError)
  }
})

async function submit() {
  loading.value = true
  error.value = ''
  try {
    await authStore.login(email.value, password.value)
    router.push(redirect && redirect.startsWith('/') ? redirect : '/dashboard')
  } catch (e) {
    error.value = e.response?.data?.detail || 'Login failed'
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.brand-logo { width: 88px; }
.oauth-btn {
  display: block;
  padding: 0.6rem 1rem;
  border-radius: 6px;
  text-align: center;
  text-decoration: none;
  color: #fff;
  border: none;
  cursor: pointer;
  font-size: 0.95rem;
}
.oauth-btn.google { background: #4285f4; }
.oauth-btn.google:hover { background: #357ae8; }
.oauth-btn.facebook { background: #1877f2; }
.oauth-btn.facebook:hover { background: #166fe5; }
.oauth-btn.x { background: #000; }
.oauth-btn.x:hover { background: #333; }
</style>

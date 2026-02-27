<template>
  <div class="auth-form">
    <img class="brand-logo" src="/branding/workmage-icon.png" alt="Workmage logo" />
    <h2 class="brand-title">Workmage</h2>
    <h1>Login</h1>
    <div v-if="oauthProviders.google || oauthProviders.facebook || oauthProviders.x" class="oauth-buttons">
      <a v-if="oauthProviders.google" :href="oauthUrls.google" class="oauth-btn google">Continue with Google</a>
      <a v-if="oauthProviders.facebook" :href="oauthUrls.facebook" class="oauth-btn facebook">Continue with Facebook</a>
      <a v-if="oauthProviders.x" :href="oauthUrls.x" class="oauth-btn x">Continue with X</a>
    </div>
    <p v-if="oauthProviders.google || oauthProviders.facebook || oauthProviders.x" class="divider">— or —</p>
    <form @submit.prevent="submit">
      <div>
        <label>Email</label>
        <input v-model="email" type="email" required />
      </div>
      <div>
        <label>Password</label>
        <input v-model="password" type="password" required />
      </div>
      <p v-if="error" class="error">{{ error }}</p>
      <button type="submit" :disabled="loading">Login</button>
    </form>
    <p>Don't have an account? <router-link to="/register">Register</router-link></p>
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
.auth-form {
  max-width: 400px;
  margin: 0 auto;
}
.brand-logo {
  width: 88px;
  display: block;
  margin: 0 auto 0.5rem;
}
.brand-title {
  text-align: center;
  margin-bottom: 1rem;
}
.auth-form h1 {
  margin-bottom: 1.5rem;
}
.auth-form div {
  margin-bottom: 1rem;
}
.auth-form label {
  display: block;
  margin-bottom: 0.25rem;
  color: var(--wm-text-muted);
}
.auth-form input {
  width: 100%;
}
.auth-form button {
  width: 100%;
  margin-top: 0.5rem;
}
.oauth-buttons { display: flex; flex-direction: column; gap: 0.5rem; margin-bottom: 1rem; }
.oauth-btn {
  display: block;
  padding: 0.6rem 1rem;
  border-radius: 6px;
  text-align: center;
  text-decoration: none;
  color: var(--wm-white);
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
.divider { text-align: center; color: var(--wm-text-muted); margin: 1rem 0; }
.error {
  color: var(--wm-danger);
  margin: 0.5rem 0;
}
</style>

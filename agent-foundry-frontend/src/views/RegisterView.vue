<template>
  <div class="auth-form mx-auto pa-4" style="max-width: 400px;">
    <img class="brand-logo d-block mx-auto mb-2" src="/branding/workmage-icon.png" alt="Workmage logo" />
    <h2 class="text-h5 text-center mb-2">Workmage</h2>
    <h1 class="text-h4 mb-6">Register</h1>
    <v-form @submit.prevent="submit" class="d-flex flex-column gap-3">
      <v-text-field v-model="email" type="email" label="Email" required density="comfortable" />
      <v-text-field v-model="password" type="password" label="Password" required minlength="6" density="comfortable" />
      <v-select v-model="role" :items="[{ title: 'Buyer', value: 'buyer' }, { title: 'Expert', value: 'expert' }]" item-title="title" item-value="value" label="Role" density="comfortable" />
      <p v-if="error" class="text-error text-body-2">{{ error }}</p>
      <v-btn type="submit" color="primary" block :loading="loading">Register</v-btn>
    </v-form>
    <p class="text-center mt-4">Already have an account? <router-link to="/login" class="text-accent text-decoration-none">Login</router-link></p>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const authStore = useAuthStore()
const router = useRouter()
const email = ref('')
const password = ref('')
const role = ref('buyer')
const loading = ref(false)
const error = ref('')

async function submit() {
  loading.value = true
  error.value = ''
  try {
    await authStore.register(email.value, password.value, role.value)
    router.push('/dashboard')
  } catch (e) {
    error.value = e.response?.data?.detail || 'Registration failed'
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.brand-logo { width: 88px; }
</style>

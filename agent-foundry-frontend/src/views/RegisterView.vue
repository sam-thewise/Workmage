<template>
  <div class="auth-form">
    <h1>Register</h1>
    <form @submit.prevent="submit">
      <div>
        <label>Email</label>
        <input v-model="email" type="email" required />
      </div>
      <div>
        <label>Password</label>
        <input v-model="password" type="password" required minlength="6" />
      </div>
      <div>
        <label>Role</label>
        <select v-model="role">
          <option value="buyer">Buyer</option>
          <option value="expert">Expert</option>
        </select>
      </div>
      <p v-if="error" class="error">{{ error }}</p>
      <button type="submit" :disabled="loading">Register</button>
    </form>
    <p>Already have an account? <router-link to="/login">Login</router-link></p>
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
.auth-form {
  max-width: 400px;
  margin: 0 auto;
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
  color: #94a3b8;
}
.auth-form input,
.auth-form select {
  width: 100%;
}
.auth-form select {
  padding: 0.5rem;
  border-radius: 6px;
  border: 1px solid #334155;
  background: #1e293b;
  color: #e2e8f0;
}
.auth-form button {
  width: 100%;
  margin-top: 0.5rem;
}
.error {
  color: #f87171;
  margin: 0.5rem 0;
}
</style>

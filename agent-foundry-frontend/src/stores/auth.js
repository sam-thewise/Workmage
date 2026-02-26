import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import api from '@/services/api'

export const useAuthStore = defineStore('auth', () => {
  const token = ref(localStorage.getItem('token'))
  const user = ref(null)

  const isAuthenticated = computed(() => !!token.value)

  async function login(email, password) {
    const { data } = await api.post('/auth/login', { email, password })
    token.value = data.access_token
    localStorage.setItem('token', data.access_token)
    await fetchUser()
    return data
  }

  async function register(email, password, role = 'buyer') {
    const { data } = await api.post('/auth/register', { email, password, role })
    return login(email, password)
  }

  async function fetchUser() {
    if (!token.value) return
    const { data } = await api.get('/auth/me')
    user.value = data
  }

  function logout() {
    token.value = null
    user.value = null
    localStorage.removeItem('token')
  }

  function setTokenFromOAuth(accessToken) {
    token.value = accessToken
    localStorage.setItem('token', accessToken)
  }

  return { token, user, isAuthenticated, login, register, logout, fetchUser, setTokenFromOAuth }
})

<template>
  <div class="expert-settings">
    <h2>Creator Settings</h2>
    <p v-if="authStore.user?.role !== 'expert'">Experts can link Stripe to receive payments from agent sales.</p>
    <template v-else>
      <div class="stripe-section">
        <h3>Stripe Account</h3>
        <p v-if="stripeLinked" class="linked">✓ Stripe account linked. You can sell paid agents.</p>
        <template v-else>
          <p class="hint">Link your Stripe account to receive payments (80% of each sale). The platform keeps 20% commission.</p>
          <button @click="linkStripe" class="btn primary" :disabled="linking">Link Stripe Account</button>
        </template>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useAuthStore } from '@/stores/auth'
import api from '@/services/api'

const authStore = useAuthStore()
const stripeLinked = ref(false)
const linking = ref(false)

async function loadStatus() {
  if (authStore.user?.role !== 'expert') return
  try {
    const { data } = await api.get('/experts/stripe-connect/status')
    stripeLinked.value = data.linked
  } catch (_) {
    stripeLinked.value = false
  }
}

async function linkStripe() {
  linking.value = true
  try {
    const { data } = await api.get('/experts/stripe-connect/onboard')
    if (data.url) window.location.href = data.url
  } catch (e) {
    alert(e.response?.data?.detail || 'Failed to start Stripe onboarding')
  } finally {
    linking.value = false
  }
}

onMounted(loadStatus)
</script>

<style scoped>
.expert-settings { max-width: 500px; margin-top: 1rem; }
.stripe-section { padding: 1rem; background: #1e293b; border-radius: 8px; border: 1px solid #334155; }
.stripe-section h3 { margin: 0 0 0.5rem; }
.hint { color: #94a3b8; font-size: 0.9rem; margin: 0.5rem 0 1rem; }
.linked { color: #34d399; }
.btn { padding: 0.5rem 1rem; border-radius: 6px; border: none; cursor: pointer; }
.btn.primary { background: #7c3aed; color: white; }
.btn:disabled { opacity: 0.6; cursor: not-allowed; }
</style>

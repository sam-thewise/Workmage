<template>
  <div class="expert-settings mx-auto mt-4" style="max-width: 500px;">
    <h2 class="text-h5 mb-2">Creator Settings</h2>
    <p v-if="authStore.user?.role !== 'expert'" class="text-body-2 text-medium-emphasis mb-4">Experts can link Stripe to receive payments from agent sales.</p>
    <template v-else>
      <v-card variant="tonal" class="pa-4">
        <h3 class="text-h6 mb-2">Stripe Account</h3>
        <p v-if="stripeLinked" class="text-success mb-0">✓ Stripe account linked. You can sell paid agents.</p>
        <template v-else>
          <p class="text-body-2 text-medium-emphasis mb-4">Link your Stripe account to receive payments (80% of each sale). The platform keeps 20% commission.</p>
          <v-btn color="primary" :loading="linking" @click="linkStripe">Link Stripe Account</v-btn>
        </template>
      </v-card>
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

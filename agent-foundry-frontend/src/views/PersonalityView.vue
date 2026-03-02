<template>
  <div class="personality mx-auto" style="max-width: 800px;">
    <h2 class="text-h5 mb-2">Your voice / personality</h2>
    <p class="text-body-2 text-medium-emphasis mb-4">
      Create a profile from your tweets so generated posts and replies match your style. Paste tweet text or a twstalker.com profile URL to analyze, then tweak and save. Chains (e.g. X Content Writer) will use this when creating drafts.
    </p>

    <v-card variant="outlined" class="pa-4 mb-4">
      <h3 class="text-subtitle-1 mb-2">Import from tweets</h3>
      <v-tabs v-model="importTab" density="compact">
        <v-tab value="paste">Paste text</v-tab>
        <v-tab value="url">twstalker URL</v-tab>
      </v-tabs>
      <v-window v-model="importTab" class="mt-2">
        <v-window-item value="paste">
          <v-textarea
            v-model="tweetText"
            label="Paste your tweets or post content"
            placeholder="Paste a block of your tweets here..."
            rows="5"
            density="compact"
            hide-details
            variant="outlined"
          />
        </v-window-item>
        <v-window-item value="url">
          <v-text-field
            v-model="twstalkerUrl"
            label="twstalker.com profile URL"
            placeholder="https://twstalker.com/YourHandle"
            density="compact"
            hide-details
            variant="outlined"
          />
        </v-window-item>
      </v-window>
      <div class="d-flex gap-2 mt-3">
        <v-btn
          color="primary"
          :loading="analyzing"
          :disabled="!hasAnalyzeInput"
          @click="analyze(false)"
        >
          Analyze
        </v-btn>
        <v-btn
          variant="tonal"
          :loading="analyzing"
          :disabled="!hasAnalyzeInput"
          @click="analyze(true)"
        >
          Analyze & save
        </v-btn>
      </div>
    </v-card>

    <v-card variant="outlined" class="pa-4">
      <h3 class="text-subtitle-1 mb-2">Profile (edit and save)</h3>
      <v-textarea
        v-model="profileText"
        label="Voice / beliefs / do's and don'ts"
        placeholder="After analyzing, your profile appears here. You can edit it and save. This text is passed to content generators so drafts match your style."
        rows="10"
        density="compact"
        hide-details
        variant="outlined"
        class="mb-3"
      />
      <v-btn
        color="primary"
        :loading="saving"
        :disabled="!profileText.trim()"
        @click="saveProfile"
      >
        Save profile
      </v-btn>
    </v-card>

    <v-snackbar v-model="snackbar" :timeout="3000" :color="snackbarColor">
      {{ snackbarText }}
    </v-snackbar>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import api from '@/services/api'

const importTab = ref('paste')
const tweetText = ref('')
const twstalkerUrl = ref('')
const profileText = ref('')
const analyzing = ref(false)
const saving = ref(false)
const snackbar = ref(false)
const snackbarText = ref('')
const snackbarColor = ref('success')

const hasAnalyzeInput = computed(() => {
  if (importTab.value === 'paste') return (tweetText.value || '').trim().length > 0
  return (twstalkerUrl.value || '').trim().length > 0
})

async function fetchProfile() {
  try {
    const { data } = await api.get('/personality')
    if (data) {
      profileText.value = data.profile_text || ''
    } else {
      profileText.value = ''
    }
  } catch {
    profileText.value = ''
  }
}

async function analyze(saveAfter) {
  if (!hasAnalyzeInput.value) return
  analyzing.value = true
  snackbarColor.value = 'success'
  try {
    const payload = {
      save: saveAfter,
      tweet_text: importTab.value === 'paste' ? (tweetText.value || '').trim() : undefined,
      twstalker_url: importTab.value === 'url' ? (twstalkerUrl.value || '').trim() : undefined
    }
    const { data } = await api.post('/personality/analyze', payload)
    profileText.value = data.profile_text || ''
    snackbarText.value = saveAfter ? 'Profile analyzed and saved' : 'Profile analyzed — edit and save if you like'
    snackbar.value = true
  } catch (e) {
    snackbarText.value = e.response?.data?.detail || 'Analysis failed'
    snackbarColor.value = 'error'
    snackbar.value = true
  } finally {
    analyzing.value = false
  }
}

async function saveProfile() {
  if (!profileText.value.trim()) return
  saving.value = true
  snackbarColor.value = 'success'
  try {
    await api.put('/personality', { profile_text: profileText.value.trim() })
    snackbarText.value = 'Profile saved'
    snackbar.value = true
  } catch (e) {
    snackbarText.value = e.response?.data?.detail || 'Save failed'
    snackbarColor.value = 'error'
    snackbar.value = true
  } finally {
    saving.value = false
  }
}

onMounted(() => {
  fetchProfile()
})
</script>

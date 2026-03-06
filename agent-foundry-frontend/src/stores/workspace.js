import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import api from '@/services/api'

export const useWorkspaceStore = defineStore('workspace', () => {
  const workspaces = ref([])
  const currentWorkspaceId = ref(null)

  const currentWorkspace = computed(() =>
    workspaces.value.find((w) => w.id === currentWorkspaceId.value)
  )

  async function fetchWorkspaces() {
    try {
      const { data } = await api.get('/workspaces/')
      workspaces.value = data || []
      if (workspaces.value.length && !currentWorkspaceId.value) {
        currentWorkspaceId.value = workspaces.value[0].id
      }
      return workspaces.value
    } catch {
      workspaces.value = []
      return []
    }
  }

  function setCurrentWorkspace(id) {
    currentWorkspaceId.value = id
  }

  return {
    workspaces,
    currentWorkspaceId,
    currentWorkspace,
    fetchWorkspaces,
    setCurrentWorkspace
  }
})

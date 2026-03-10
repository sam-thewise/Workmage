<template>
  <div class="personality-node">
    <div class="personality-node-content">
      <span class="personality-badge">Personality</span>
      {{ data.personalityName || data.personality_id || 'unnamed' }}
    </div>
    <Handle id="output" type="source" position="right" :connectable="true" />
  </div>
</template>

<script setup>
import { Handle } from '@vue-flow/core'

defineProps({
  data: { type: Object, default: () => ({}) },
  id: { type: String, required: true },
})
</script>

<style scoped>
.personality-node {
  padding: 0.5rem 1rem;
  background: var(--wm-surface-alt, #e8f5e9);
  border: 1px solid var(--wm-border);
  border-radius: 8px;
  min-width: 100px;
  position: relative;
}
.personality-node-content {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}
.personality-badge {
  font-size: 0.7rem;
  background: var(--wm-accent, #4caf50);
  color: white;
  padding: 0.15rem 0.4rem;
  border-radius: 4px;
}
:deep(.vue-flow__handle) {
  width: 10px;
  height: 10px;
  background: var(--wm-primary);
  border: 2px solid var(--wm-accent);
  pointer-events: all !important;
}
</style>

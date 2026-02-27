<template>
  <div class="agent-node">
    <Handle id="input" type="target" position="left" :connectable="true" />
    <div class="agent-node-content">
      <span class="badge" v-if="data.isEntry">Start</span>
      {{ data.label }}
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
.agent-node { padding: 0.5rem 1rem; background: var(--wm-bg-soft); border: 1px solid var(--wm-border); border-radius: 8px; min-width: 120px; position: relative; }
.agent-node-content { display: flex; align-items: center; gap: 0.5rem; }
/* Ensure handles are visible and clickable */
:deep(.vue-flow__handle) {
  width: 10px;
  height: 10px;
  background: var(--wm-primary);
  border: 2px solid var(--wm-accent);
  pointer-events: all !important;
}
.badge { font-size: 0.7rem; background: var(--wm-primary); color: var(--wm-white); padding: 0.15rem 0.4rem; border-radius: 4px; }
</style>

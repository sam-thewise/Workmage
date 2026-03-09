<template>
  <div class="loop-node">
    <Handle id="input" type="target" position="left" :connectable="true" />
    <div class="loop-node-content" :class="{ 'drag-handle': dragHandle }">
      <span class="loop-badge">Loop</span>
      {{ data.label || 'for each (max ' + (data.max_iterations ?? 5) + ')' }}
    </div>
    <Handle id="output" type="source" position="right" :connectable="true" />
  </div>
</template>

<script setup>
import { Handle } from '@vue-flow/core'

defineProps({
  data: { type: Object, default: () => ({}) },
  id: { type: String, required: true },
  dragHandle: { type: Boolean, default: true },
})
</script>

<style scoped>
.loop-node {
  padding: 0.5rem 1rem;
  background: var(--wm-bg-soft, #f0f5ff);
  border: 1px solid var(--wm-primary);
  border-radius: 8px;
  min-width: 120px;
  position: relative;
}
.loop-node-content {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}
.loop-node-content.drag-handle {
  cursor: grab;
}
.loop-badge {
  font-size: 0.7rem;
  background: var(--wm-primary);
  color: var(--wm-white);
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

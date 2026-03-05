<template>
  <div class="approval-node">
    <Handle id="input" type="target" position="left" :connectable="true" />
    <div class="approval-node-content" :class="{ 'drag-handle': dragHandle }">
      <span class="approval-badge">Approval</span>
      {{ data.title || 'Review & continue' }}
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
.approval-node {
  padding: 0.5rem 1rem;
  background: var(--wm-bg-soft, #e8f4fd);
  border: 1px solid var(--wm-accent);
  border-radius: 8px;
  min-width: 120px;
  position: relative;
}
.approval-node-content {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}
.approval-node-content.drag-handle {
  cursor: grab;
}
.approval-badge {
  font-size: 0.7rem;
  background: var(--wm-accent);
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

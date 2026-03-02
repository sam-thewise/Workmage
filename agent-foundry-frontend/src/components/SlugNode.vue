<template>
  <div class="slug-node">
    <div class="slug-node-content">
      <span class="slug-badge">Slug</span>
      {{ data.slug || 'unnamed' }}
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
.slug-node {
  padding: 0.5rem 1rem;
  background: var(--wm-surface-alt, #fffbd7);
  border: 1px solid var(--wm-border);
  border-radius: 8px;
  min-width: 100px;
  position: relative;
}
.slug-node-content {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}
.slug-badge {
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

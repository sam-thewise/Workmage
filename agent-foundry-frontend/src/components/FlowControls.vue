<template>
  <Panel position="bottom-left" class="flow-controls-panel">
    <button type="button" class="flow-control-btn" title="Zoom in" :disabled="maxZoomReached" @click="zoomIn">+</button>
    <button type="button" class="flow-control-btn" title="Zoom out" :disabled="minZoomReached" @click="zoomOut">−</button>
    <button type="button" class="flow-control-btn" title="Fit view" @click="fitView">⊡</button>
    <button type="button" class="flow-control-btn" title="Lock/Unlock pan" @click="toggleInteractive">
      {{ isInteractive ? '⊙' : '⊘' }}
    </button>
  </Panel>
</template>

<script setup>
import { computed } from 'vue'
import { Panel, useVueFlow } from '@vue-flow/core'

const { zoomIn, zoomOut, fitView, setInteractive, viewport, minZoom, maxZoom, nodesDraggable, nodesConnectable, elementsSelectable } = useVueFlow()

const isInteractive = computed(() => nodesDraggable.value || nodesConnectable.value || elementsSelectable.value)
const minZoomReached = computed(() => viewport.value.zoom <= minZoom.value)
const maxZoomReached = computed(() => viewport.value.zoom >= maxZoom.value)

function toggleInteractive() {
  setInteractive(!isInteractive.value)
}
</script>

<style scoped>
.flow-controls-panel {
  display: flex;
  gap: 2px;
  padding: 4px;
  background: #1e293b;
  border-radius: 6px;
  border: 1px solid #334155;
  box-shadow: 0 0 4px rgba(0, 0, 0, 0.3);
}

.flow-control-btn {
  width: 28px;
  height: 28px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #334155;
  color: #e2e8f0;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 16px;
  line-height: 1;
  font-family: system-ui, sans-serif;
}

.flow-control-btn:hover:not(:disabled) {
  background: #475569;
}

.flow-control-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
</style>

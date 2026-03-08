<template>
  <div class="formatted-output">
    <template v-if="displayMode === 'json'">
      <pre class="formatted-output-pre json-output" v-html="jsonHtml"></pre>
    </template>
    <template v-else-if="displayMode === 'markdown'">
      <div class="formatted-output-markdown markdown-body" v-html="markdownHtml"></div>
    </template>
    <template v-else>
      <pre class="formatted-output-pre plain-output">{{ content || fallback }}</pre>
    </template>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { marked } from 'marked'
import DOMPurify from 'dompurify'

const props = defineProps({
  content: { type: String, default: '' },
  fallback: { type: String, default: 'No output' },
})

function tryParseJson(str) {
  const s = (str || '').trim()
  if (!s) return null
  if ((s.startsWith('{') && s.endsWith('}')) || (s.startsWith('[') && s.endsWith(']'))) {
    try {
      return JSON.parse(s)
    } catch {
      return null
    }
  }
  return null
}

function escapeHtml(text) {
  const div = document.createElement('div')
  div.textContent = text
  return div.innerHTML
}

function highlightJson(jsonStr) {
  let html = jsonStr
  // Keys (quoted string followed by colon) - escape key content for HTML
  html = html.replace(/"([^"\\]*(?:\\.[^"\\]*)*)"(\s*):/g, (_, key, sp) => '<span class="json-key">"' + escapeHtml(key) + '"</span>' + sp + ':')
  // String values (after : or , or [)
  html = html.replace(/([:\[,])(\s*)"([^"\\]*(?:\\.[^"\\]*)*)"/g, (_, before, sp, val) => before + sp + '<span class="json-string">"' + escapeHtml(val) + '"</span>')
  // Numbers (after colon, not inside strings)
  html = html.replace(/:(\s*)(-?\d+\.?\d*)([,\]\}\s])/g, ': $1<span class="json-number">$2</span>$3')
  // true, false, null
  html = html.replace(/\b(true|false|null)\b/g, '<span class="json-literal">$1</span>')
  return html
}

const displayMode = computed(() => {
  const s = (props.content || '').trim()
  if (!s) return 'plain'
  if (tryParseJson(s) !== null) return 'json'
  return 'markdown'
})

const jsonHtml = computed(() => {
  const parsed = tryParseJson(props.content)
  if (parsed === null) return escapeHtml(props.content || props.fallback)
  const pretty = JSON.stringify(parsed, null, 2)
  return highlightJson(pretty)
})

const markdownHtml = computed(() => {
  const raw = props.content || props.fallback
  const html = marked.parse(raw, { gfm: true, breaks: true })
  return DOMPurify.sanitize(html, { ALLOWED_TAGS: ['p', 'br', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'strong', 'em', 'a', 'ul', 'ol', 'li', 'code', 'pre', 'blockquote', 'hr', 'table', 'thead', 'tbody', 'tr', 'th', 'td'], ALLOWED_ATTR: ['href', 'target', 'rel'] })
})
</script>

<style scoped>
.formatted-output-pre {
  margin: 0;
  padding: 1rem;
  border-radius: 8px;
  background: rgba(0, 0, 0, 0.2);
  overflow-x: auto;
  white-space: pre-wrap;
  word-break: break-word;
  font-size: 0.875rem;
  line-height: 1.5;
}
.formatted-output-markdown {
  font-size: 0.9375rem;
  line-height: 1.6;
}
.formatted-output-markdown :deep(p) { margin: 0 0 0.75em; }
.formatted-output-markdown :deep(p:last-child) { margin-bottom: 0; }
.formatted-output-markdown :deep(h1) { font-size: 1.5rem; margin: 0 0 0.5em; }
.formatted-output-markdown :deep(h2) { font-size: 1.25rem; margin: 1em 0 0.35em; }
.formatted-output-markdown :deep(h3) { font-size: 1.1rem; margin: 0.75em 0 0.25em; }
.formatted-output-markdown :deep(h4), .formatted-output-markdown :deep(h5), .formatted-output-markdown :deep(h6) { font-size: 1rem; margin: 0.5em 0 0.2em; }
.formatted-output-markdown :deep(ul), .formatted-output-markdown :deep(ol) { margin: 0.5em 0; padding-left: 1.5em; }
.formatted-output-markdown :deep(li) { margin: 0.2em 0; }
.formatted-output-markdown :deep(code) { background: rgba(0,0,0,0.25); padding: 0.15em 0.4em; border-radius: 4px; font-size: 0.9em; }
.formatted-output-markdown :deep(pre) { background: rgba(0,0,0,0.25); padding: 1rem; border-radius: 8px; overflow-x: auto; margin: 0.5em 0; }
.formatted-output-markdown :deep(pre code) { background: none; padding: 0; }
.formatted-output-markdown :deep(blockquote) { border-left: 4px solid rgba(var(--v-theme-primary), 0.5); margin: 0.5em 0; padding-left: 1em; opacity: 0.95; }
.formatted-output-markdown :deep(hr) { border: none; border-top: 1px solid rgba(var(--v-border-color), 0.5); margin: 1em 0; }
.formatted-output-markdown :deep(a) { color: rgb(var(--v-theme-accent)); }
.formatted-output-markdown :deep(table) { border-collapse: collapse; width: 100%; margin: 0.5em 0; }
.formatted-output-markdown :deep(th), .formatted-output-markdown :deep(td) { border: 1px solid rgba(var(--v-border-color), 0.5); padding: 0.35em 0.6em; text-align: left; }
.formatted-output-markdown :deep(thead th) { background: rgba(0,0,0,0.2); }

/* JSON syntax highlighting */
.json-output :deep(.json-key) { color: rgb(var(--v-theme-accent)); }
.json-output :deep(.json-string) { color: #34d399; }
.json-output :deep(.json-number) { color: #fde68a; }
.json-output :deep(.json-literal) { color: #608bf7; }
</style>

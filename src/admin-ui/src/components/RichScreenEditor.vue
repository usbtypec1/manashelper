<script setup lang="ts">
import { ref, watch } from 'vue'
import type { FlowNode, Schemas, Text, Value } from '../types'
import { inline } from '../types'
import { t } from '../i18n'
import TextEditor from './TextEditor.vue'
import ValueEditor from './ValueEditor.vue'

const props = defineProps<{
  node: Extract<FlowNode, { kind: 'menu' | 'input' }>
  catalog: Schemas['EditorCatalog']
  fields: string[]
}>()
const emit = defineEmits<{ change: [] }>()
const messageKeys = ref<number[]>([])
let nextKey = 0
watch(
  () => props.node,
  () => {
    messageKeys.value = (props.node.messages ?? []).map(() => nextKey++)
  },
  { immediate: true },
)

type Source = 'media' | 'message_source'
function toggleSource(source: Source, enabled: boolean) {
  const field = source === 'media' ? 'media' : 'messages'
  props.node[source] = enabled
    ? { kind: 'ref', scope: 'data', field: props.fields.includes(field) ? field : (props.fields[0] ?? field) }
    : null
  emit('change')
}
function setSource(source: Source, value: Value) {
  if (value.kind !== 'ref') return
  props.node[source] = value
  emit('change')
}
function addMessage() {
  if ((props.node.messages?.length ?? 0) >= 20) return
  ;(props.node.messages ??= []).push(inline(t('text')))
  messageKeys.value.push(nextKey++)
  emit('change')
}
function setMessage(index: number, text: Text) {
  props.node.messages![index] = text
  emit('change')
}
function removeMessage(index: number) {
  props.node.messages!.splice(index, 1)
  messageKeys.value.splice(index, 1)
  emit('change')
}
function moveMessage(index: number, direction: -1 | 1) {
  const target = index + direction
  const messages = props.node.messages ?? []
  if (target < 0 || target >= messages.length) return
  ;[messages[index], messages[target]] = [messages[target], messages[index]]
  ;[messageKeys.value[index], messageKeys.value[target]] = [
    messageKeys.value[target],
    messageKeys.value[index],
  ]
  emit('change')
}
</script>
<template>
  <section class="stack" :aria-label="t('richScreen')">
    <div class="section-label">{{ t('richScreen') }}</div>
    <fieldset class="binding stack">
      <legend>{{ t('mediaSource') }}</legend>
      <label class="check">
        <input
          type="checkbox"
          :checked="node.media != null"
          @change="toggleSource('media', ($event.target as HTMLInputElement).checked)"
        />{{ t('enabled') }}
      </label>
      <ValueEditor
        v-if="node.media"
        :model-value="node.media"
        :fields="fields"
        reference-only
        @update:model-value="setSource('media', $event)"
      />
    </fieldset>
    <fieldset class="binding stack">
      <legend>{{ t('messageSource') }}</legend>
      <label class="check">
        <input
          type="checkbox"
          :checked="node.message_source != null"
          @change="toggleSource('message_source', ($event.target as HTMLInputElement).checked)"
        />{{ t('enabled') }}
      </label>
      <ValueEditor
        v-if="node.message_source"
        :model-value="node.message_source"
        :fields="fields"
        reference-only
        @update:model-value="setSource('message_source', $event)"
      />
    </fieldset>
    <div class="section-label">{{ t('additionalMessages') }}</div>
    <div v-for="(message, index) in node.messages ?? []" :key="messageKeys[index]" class="binding stack">
      <div class="row between">
        <span class="section-label">#{{ index + 1 }}</span>
        <div class="row">
          <button
            type="button"
            class="icon-button"
            :aria-label="t('moveUp') + ' ' + t('additionalMessages') + ' ' + (index + 1)"
            :disabled="index === 0"
            @click="moveMessage(index, -1)"
          >
            ↑
          </button>
          <button
            type="button"
            class="icon-button"
            :aria-label="t('moveDown') + ' ' + t('additionalMessages') + ' ' + (index + 1)"
            :disabled="index === (node.messages?.length ?? 0) - 1"
            @click="moveMessage(index, 1)"
          >
            ↓
          </button>
          <button
            type="button"
            class="icon-button danger"
            :aria-label="t('remove') + ' ' + t('additionalMessages') + ' ' + (index + 1)"
            @click="removeMessage(index)"
          >
            ×
          </button>
        </div>
      </div>
      <TextEditor
        :model-value="message"
        :catalog="catalog"
        :fields="fields"
        :label="t('additionalMessages') + ' ' + (index + 1)"
        @update:model-value="setMessage(index, $event)"
      />
    </div>
    <button type="button" class="small" :disabled="(node.messages?.length ?? 0) >= 20" @click="addMessage">
      ＋ {{ t('addMessage') }}
    </button>
  </section>
</template>

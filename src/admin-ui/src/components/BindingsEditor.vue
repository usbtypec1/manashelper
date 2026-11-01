<script setup lang="ts">
import { ref } from 'vue'
import type { Value } from '../types'
import { identifier } from '../types'
import { t } from '../i18n'
import ValueEditor from './ValueEditor.vue'
const props = defineProps<{ modelValue: Record<string, Value>; fields: string[]; label: string }>()
const emit = defineEmits<{ 'update:modelValue': [Record<string, Value>] }>()
const name = ref('')
function update(key: string, value?: Value) {
  const result = { ...props.modelValue }
  if (value === undefined) delete result[key]
  else result[key] = value
  emit('update:modelValue', result)
}
function add() {
  if (!identifier.test(name.value) || name.value in props.modelValue) return
  update(name.value, { kind: 'literal', value: '' })
  name.value = ''
}
</script>
<template>
  <div class="bindings">
    <div class="section-label">{{ label }}</div>
    <div v-for="(value, key) in modelValue" :key="key" class="binding">
      <div class="row between">
        <code>{{ key }}</code
        ><button
          class="icon-button danger"
          type="button"
          :aria-label="t('remove') + ' ' + key"
          @click="update(key)"
        >
          ×
        </button>
      </div>
      <ValueEditor :model-value="value" :fields="fields" @update:model-value="update(key, $event)" />
    </div>
    <div class="row">
      <input
        v-model="name"
        :aria-label="t('field')"
        :placeholder="t('field')"
        @keydown.enter.prevent="add"
      /><button
        type="button"
        class="small"
        :disabled="!identifier.test(name) || name in modelValue"
        @click="add"
      >
        ＋
      </button>
    </div>
  </div>
</template>

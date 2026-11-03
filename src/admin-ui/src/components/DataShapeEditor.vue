<script setup lang="ts">
import { computed, ref } from 'vue'
import type { Schemas } from '../types'
import { identifier } from '../types'
import { t } from '../i18n'

type DataField = Schemas['DataField']
const props = withDefaults(defineProps<{ modelValue: DataField; depth?: number }>(), { depth: 0 })
const emit = defineEmits<{ 'update:modelValue': [DataField] }>()
const propertyName = ref('')
const fieldTypes = ['text', 'integer', 'number', 'boolean', 'list', 'object', 'secret'] as const
const canNest = computed(() => props.depth < 7)
function changeType(type: DataField['type']) {
  if (!canNest.value && (type === 'list' || type === 'object')) return
  emit('update:modelValue', {
    ...props.modelValue,
    type,
    items: type === 'list' ? (props.modelValue.items ?? { type: 'text', nullable: false }) : null,
    properties: type === 'object' ? (props.modelValue.properties ?? {}) : {},
  })
}
function property(key: string, value: DataField | null) {
  const properties = { ...props.modelValue.properties }
  if (value) properties[key] = value
  else delete properties[key]
  emit('update:modelValue', { ...props.modelValue, properties })
}
function addProperty() {
  const key = propertyName.value
  if (
    !canNest.value ||
    !identifier.test(key) ||
    key in (props.modelValue.properties ?? {}) ||
    Object.keys(props.modelValue.properties ?? {}).length >= 64
  )
    return
  property(key, { type: 'text', nullable: false })
  propertyName.value = ''
}
function maxItems(input: HTMLInputElement) {
  const value = Number(input.value)
  if (Number.isInteger(value) && value >= 1 && value <= 1000)
    emit('update:modelValue', { ...props.modelValue, max_items: value })
}
</script>
<template>
  <div class="data-shape-editor stack">
    <select
      :value="modelValue.type"
      :aria-label="t('type')"
      @change="changeType(($event.target as HTMLSelectElement).value as DataField['type'])"
    >
      <option
        v-for="type in fieldTypes"
        :key="type"
        :value="type"
        :disabled="!canNest && (type === 'list' || type === 'object')"
      >
        {{ type === 'secret' ? t('secret') : type }}
      </option>
    </select>
    <label class="check">
      <input
        type="checkbox"
        :checked="modelValue.nullable"
        @change="
          emit('update:modelValue', {
            ...modelValue,
            nullable: ($event.target as HTMLInputElement).checked,
          })
        "
      />{{ t('nullable') }}
    </label>
    <template v-if="modelValue.type === 'list'">
      <label>
        {{ t('maxItems') }}
        <input
          type="number"
          :value="modelValue.max_items ?? 100"
          min="1"
          max="1000"
          step="1"
          required
          @input="maxItems($event.target as HTMLInputElement)"
        />
      </label>
      <fieldset v-if="canNest" class="binding stack">
        <legend>{{ t('itemType') }}</legend>
        <DataShapeEditor
          :model-value="modelValue.items ?? { type: 'text', nullable: false }"
          :depth="depth + 1"
          @update:model-value="emit('update:modelValue', { ...modelValue, items: $event })"
        />
      </fieldset>
    </template>
    <fieldset v-if="modelValue.type === 'object' && canNest" class="binding stack">
      <legend>{{ t('properties') }}</legend>
      <div v-for="(field, key) in modelValue.properties ?? {}" :key="key" class="binding stack">
        <div class="row between">
          <code>{{ key }}</code>
          <button
            type="button"
            class="icon-button danger"
            :aria-label="t('remove') + ' ' + key"
            @click="property(key, null)"
          >
            ×
          </button>
        </div>
        <DataShapeEditor
          :model-value="field"
          :depth="depth + 1"
          @update:model-value="property(key, $event)"
        />
      </div>
      <div class="row">
        <input
          v-model="propertyName"
          :aria-label="t('properties') + ': ' + t('field')"
          :placeholder="t('field')"
          @keydown.enter.prevent="addProperty"
        />
        <button
          type="button"
          class="small"
          :disabled="
            !identifier.test(propertyName) ||
            propertyName in (modelValue.properties ?? {}) ||
            Object.keys(modelValue.properties ?? {}).length >= 64
          "
          @click="addProperty"
        >
          ＋ {{ t('addField') }}
        </button>
      </div>
    </fieldset>
  </div>
</template>

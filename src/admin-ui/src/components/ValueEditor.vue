<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import type { Value, Scalar } from '../types'
import { identifier } from '../types'
import { t } from '../i18n'
const props = defineProps<{ modelValue: Value; fields?: string[]; referenceOnly?: boolean }>()
const emit = defineEmits<{ 'update:modelValue': [Value] }>()
const literalType = computed(() =>
  props.modelValue.kind === 'literal'
    ? props.modelValue.value === null
      ? 'null'
      : Array.isArray(props.modelValue.value)
        ? 'array'
        : typeof props.modelValue.value
    : 'string',
)
const jsonBuffer = ref(''),
  pathBuffer = ref('[]')
const jsonInput = ref<HTMLTextAreaElement | null>(null),
  pathInput = ref<HTMLInputElement | null>(null)
watch(
  () => (props.modelValue.kind === 'literal' ? JSON.stringify(props.modelValue.value) : null),
  () => {
    jsonBuffer.value =
      props.modelValue.kind === 'literal' ? JSON.stringify(props.modelValue.value, null, 2) : ''
    jsonInput.value?.setCustomValidity('')
  },
  { immediate: true },
)
watch(
  () => (props.modelValue.kind === 'ref' ? JSON.stringify(props.modelValue.path ?? []) : null),
  () => {
    pathBuffer.value = props.modelValue.kind === 'ref' ? JSON.stringify(props.modelValue.path ?? []) : '[]'
    pathInput.value?.setCustomValidity('')
  },
  { immediate: true },
)
function mode(value: string) {
  emit(
    'update:modelValue',
    value === 'ref'
      ? { kind: 'ref', scope: 'data', field: props.fields?.[0] ?? 'value' }
      : { kind: 'literal', value: '' },
  )
}
function setLiteral(value: string) {
  let parsed: Scalar = value
  if (literalType.value === 'number') parsed = Number(value)
  if (literalType.value === 'boolean') parsed = value === 'true'
  if (literalType.value === 'null') parsed = null
  emit('update:modelValue', { kind: 'literal', value: parsed })
}
function changeLiteralType(type: string) {
  const defaults: Record<string, Scalar> = {
    string: '',
    number: 0,
    boolean: false,
    null: null,
    array: [],
    object: {},
  }
  emit('update:modelValue', { kind: 'literal', value: defaults[type] })
}
function dataValue(value: unknown, depth = 0): value is Scalar {
  if (depth > 8) return false
  if (value === null || typeof value === 'string' || typeof value === 'boolean') return true
  if (typeof value === 'number') return Number.isFinite(value)
  if (Array.isArray(value)) return value.every((item) => dataValue(item, depth + 1))
  if (typeof value === 'object') return Object.values(value).every((item) => dataValue(item, depth + 1))
  return false
}
function setJson(input: HTMLTextAreaElement) {
  jsonBuffer.value = input.value
  try {
    const value: unknown = JSON.parse(input.value)
    if (
      !dataValue(value) ||
      (literalType.value === 'array'
        ? !Array.isArray(value)
        : value === null || Array.isArray(value) || typeof value !== 'object')
    )
      throw new Error()
    input.setCustomValidity('')
    emit('update:modelValue', { kind: 'literal', value })
  } catch {
    input.setCustomValidity(t('jsonValue'))
  }
}
function setPath(input: HTMLInputElement) {
  pathBuffer.value = input.value
  if (props.modelValue.kind !== 'ref') return
  try {
    const value: unknown = JSON.parse(input.value)
    if (
      !Array.isArray(value) ||
      value.length > 8 ||
      !value.every((part) =>
        typeof part === 'string'
          ? identifier.test(part)
          : typeof part === 'number' && Number.isInteger(part) && part >= 0 && part <= 999,
      )
    )
      throw new Error()
    input.setCustomValidity('')
    emit('update:modelValue', { ...props.modelValue, path: value })
  } catch {
    input.setCustomValidity(t('referencePath'))
  }
}
</script>
<template>
  <div class="value-editor">
    <select
      v-if="!referenceOnly"
      :aria-label="t('type')"
      :value="modelValue.kind"
      @change="mode(($event.target as HTMLSelectElement).value)"
    >
      <option value="literal">{{ t('literal') }}</option>
      <option value="ref">{{ t('reference') }}</option>
    </select>
    <template v-if="modelValue.kind === 'ref'">
      <select
        :value="modelValue.scope"
        aria-label="scope"
        @change="
          emit('update:modelValue', {
            ...modelValue,
            scope: ($event.target as HTMLSelectElement).value as 'data',
          })
        "
      >
        <option>data</option>
        <option>user</option>
        <option>capabilities</option>
        <option>item</option>
      </select>
      <input
        :value="modelValue.field"
        :aria-label="t('field')"
        pattern="[a-z][a-z0-9_]{0,31}"
        required
        @input="
          emit('update:modelValue', { ...modelValue, field: ($event.target as HTMLInputElement).value })
        "
      />
      <label>
        {{ t('referencePath') }}
        <input
          ref="pathInput"
          :value="pathBuffer"
          :aria-label="t('referencePath')"
          placeholder="[]"
          required
          @input="setPath($event.target as HTMLInputElement)"
        />
      </label>
    </template>
    <template v-else>
      <select
        :value="literalType"
        :aria-label="t('type')"
        @change="changeLiteralType(($event.target as HTMLSelectElement).value)"
      >
        <option value="string">text</option>
        <option value="number">number</option>
        <option value="boolean">boolean</option>
        <option value="null">null</option>
        <option value="array">list</option>
        <option value="object">object</option>
      </select>
      <select
        v-if="literalType === 'boolean'"
        :value="String(modelValue.value)"
        :aria-label="t('literal')"
        @change="setLiteral(($event.target as HTMLSelectElement).value)"
      >
        <option>true</option>
        <option>false</option>
      </select>
      <textarea
        v-else-if="literalType === 'array' || literalType === 'object'"
        ref="jsonInput"
        :value="jsonBuffer"
        :aria-label="t('jsonValue')"
        rows="5"
        required
        @input="setJson($event.target as HTMLTextAreaElement)"
      />
      <input
        v-else-if="literalType !== 'null'"
        :type="literalType === 'number' ? 'number' : 'text'"
        step="any"
        :aria-label="t('literal')"
        :value="modelValue.value as string"
        @input="setLiteral(($event.target as HTMLInputElement).value)"
      />
    </template>
  </div>
</template>

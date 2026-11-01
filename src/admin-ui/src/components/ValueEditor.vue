<script setup lang="ts">
import { computed } from 'vue'
import type { Value, Scalar } from '../types'
import { t } from '../i18n'
const props = defineProps<{ modelValue: Value; fields?: string[]; referenceOnly?: boolean }>()
const emit = defineEmits<{ 'update:modelValue': [Value] }>()
const literalType = computed(() =>
  props.modelValue.kind === 'literal'
    ? props.modelValue.value === null
      ? 'null'
      : typeof props.modelValue.value
    : 'string',
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
    </template>
    <template v-else>
      <select
        :value="literalType"
        :aria-label="t('type')"
        @change="
          emit('update:modelValue', {
            kind: 'literal',
            value: ({ string: '', number: 0, boolean: false, null: null } as Record<string, Scalar>)[
              ($event.target as HTMLSelectElement).value
            ],
          })
        "
      >
        <option value="string">text</option>
        <option value="number">number</option>
        <option value="boolean">boolean</option>
        <option value="null">null</option>
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

<script setup lang="ts">
import type { Predicate, Schemas } from '../types'
import { t } from '../i18n'
import ValueEditor from './ValueEditor.vue'
import JsonField from './JsonField.vue'
defineProps<{ modelValue: Predicate; fields: string[]; atomic?: boolean }>()
const emit = defineEmits<{ 'update:modelValue': [Predicate] }>()
function change(kind: string) {
  const reference: Schemas['ReferenceValue'] = { kind: 'ref', scope: 'user', field: 'id' }
  const predicate: Predicate =
    kind === 'exists'
      ? { kind, reference }
      : kind === 'all' || kind === 'any'
        ? { kind, conditions: [{ kind: 'exists', reference }] }
        : { kind: 'compare', left: reference, operator: 'eq', right: { kind: 'literal', value: '' } }
  emit('update:modelValue', predicate)
}
</script>
<template>
  <div class="condition-editor">
    <select
      :value="modelValue.kind"
      :aria-label="t('condition')"
      @change="change(($event.target as HTMLSelectElement).value)"
    >
      <option value="compare">compare</option>
      <option value="exists">exists</option>
      <option v-if="!atomic" value="all">{{ t('all') }}</option>
      <option v-if="!atomic" value="any">{{ t('any') }}</option>
    </select>
    <ValueEditor
      v-if="modelValue.kind === 'exists'"
      :model-value="modelValue.reference"
      :fields="fields"
      reference-only
      @update:model-value="
        emit('update:modelValue', { ...modelValue, reference: $event as Schemas['ReferenceValue'] })
      "
    />
    <template v-else-if="modelValue.kind === 'compare'">
      <ValueEditor
        :model-value="modelValue.left"
        :fields="fields"
        reference-only
        @update:model-value="
          emit('update:modelValue', { ...modelValue, left: $event as Schemas['ReferenceValue'] })
        "
      />
      <select
        :value="modelValue.operator"
        aria-label="operator"
        @change="
          emit('update:modelValue', {
            ...modelValue,
            operator: ($event.target as HTMLSelectElement).value as 'eq',
            right: ($event.target as HTMLSelectElement).value === 'in' ? [] : { kind: 'literal', value: '' },
          })
        "
      >
        <option v-for="operator in ['eq', 'ne', 'in', 'lt', 'le', 'gt', 'ge']" :key="operator">
          {{ operator }}
        </option>
      </select>
      <JsonField
        v-if="Array.isArray(modelValue.right)"
        :model-value="modelValue.right"
        :label="t('choices')"
        @update:model-value="
          emit('update:modelValue', { ...modelValue, right: $event as Schemas['Compare']['right'] })
        "
      />
      <ValueEditor
        v-else
        :model-value="modelValue.right"
        :fields="fields"
        @update:model-value="emit('update:modelValue', { ...modelValue, right: $event })"
      />
    </template>
    <template v-else>
      <div v-for="(condition, index) in modelValue.conditions" :key="index" class="binding">
        <ConditionEditor
          :model-value="condition"
          :fields="fields"
          atomic
          @update:model-value="modelValue.conditions[index] = $event as Schemas['Compare']"
        />
        <button
          type="button"
          class="text-button danger"
          :disabled="modelValue.conditions.length < 2"
          @click="modelValue.conditions.splice(index, 1)"
        >
          {{ t('remove') }}
        </button>
      </div>
      <button
        type="button"
        class="small"
        :disabled="modelValue.conditions.length >= 16"
        @click="
          modelValue.conditions.push({
            kind: 'exists',
            reference: { kind: 'ref', scope: 'user', field: 'id' },
          })
        "
      >
        {{ t('addCondition') }}
      </button>
    </template>
  </div>
</template>

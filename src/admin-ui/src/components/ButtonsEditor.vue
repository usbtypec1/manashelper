<script setup lang="ts">
import type { Button, Schemas } from '../types'
import { inline, uniqueId } from '../types'
import { t } from '../i18n'
import TextEditor from './TextEditor.vue'
import BindingsEditor from './BindingsEditor.vue'
import ConditionEditor from './ConditionEditor.vue'
import TargetSelect from './TargetSelect.vue'
const props = defineProps<{
  modelValue: Button[][]
  nodes: string[]
  fields: string[]
  catalog: Schemas['EditorCatalog']
  reply?: boolean
}>()
const emit = defineEmits<{ 'update:modelValue': [Button[][]] }>()
function add(row?: number) {
  const id = uniqueId(
    'button',
    props.modelValue.flat().map((button) => button.id),
  )
  const button: Button = {
    kind: 'transition',
    id,
    label: inline(t('continue')),
    target: props.nodes[0] ?? '',
    assignments: {},
  }
  if (row === undefined) emit('update:modelValue', [...props.modelValue, [button]])
  else props.modelValue[row].push(button)
}
function remove(row: number, index: number) {
  props.modelValue[row].splice(index, 1)
  emit(
    'update:modelValue',
    props.modelValue.filter((row) => row.length),
  )
}
function move(row: number, direction: number) {
  const rows = [...props.modelValue]
  ;[rows[row], rows[row + direction]] = [rows[row + direction], rows[row]]
  emit('update:modelValue', rows)
}
</script>
<template>
  <section class="stack">
    <div class="section-label">{{ t('buttons') }}</div>
    <div v-for="(row, rowIndex) in modelValue" :key="rowIndex" class="button-row-editor">
      <div class="row between">
        <span class="eyebrow">{{ rowIndex + 1 }}</span>
        <div class="row">
          <button
            type="button"
            class="icon-button"
            :aria-label="t('moveUp')"
            :disabled="rowIndex === 0"
            @click="move(rowIndex, -1)"
          >
            ↑</button
          ><button
            type="button"
            class="icon-button"
            :aria-label="t('moveDown')"
            :disabled="rowIndex === modelValue.length - 1"
            @click="move(rowIndex, 1)"
          >
            ↓
          </button>
        </div>
      </div>
      <details v-for="(button, index) in row" :key="index" open class="button-editor">
        <summary>{{ button.id }}</summary>
        <label
          >{{ t('buttonId') }}<input v-model="button.id" pattern="[a-z][a-z0-9_]{0,31}" required
        /></label>
        <select
          :aria-label="t('type')"
          :value="button.kind"
          @change="
            row[index] =
              ($event.target as HTMLSelectElement).value === 'url'
                ? {
                    kind: 'url',
                    id: button.id,
                    label: button.label,
                    url: 'https://example.com',
                    when: button.when,
                  }
                : {
                    kind: 'transition',
                    id: button.id,
                    label: button.label,
                    target: nodes[0] ?? '',
                    assignments: {},
                    when: button.when,
                  }
          "
        >
          <option value="transition">{{ t('transition') }}</option>
          <option v-if="!reply" value="url">{{ t('url') }}</option>
        </select>
        <TextEditor v-model="button.label" :catalog="catalog" :fields="fields" :label="t('label')" />
        <TargetSelect
          v-if="button.kind === 'transition'"
          v-model="button.target"
          :nodes="nodes"
          :label="t('target')"
        />
        <label v-else>{{ t('url') }}<input v-model="button.url" type="url" required /></label>
        <details v-if="button.kind === 'transition'">
          <summary>{{ t('assignment') }}</summary>
          <BindingsEditor
            :model-value="button.assignments ?? {}"
            :fields="fields"
            :label="t('fields')"
            @update:model-value="button.assignments = $event"
          />
        </details>
        <label class="check"
          ><input
            type="checkbox"
            :checked="!!button.when"
            @change="
              button.when = ($event.target as HTMLInputElement).checked
                ? { kind: 'exists', reference: { kind: 'ref', scope: 'user', field: 'id' } }
                : null
            "
          />{{ t('when') }}</label
        >
        <ConditionEditor v-if="button.when" v-model="button.when" :fields="fields" />
        <button type="button" class="text-button danger" @click="remove(rowIndex, index)">
          {{ t('remove') }}
        </button>
      </details>
      <button type="button" class="small" :disabled="row.length >= 8" @click="add(rowIndex)">
        ＋ {{ t('addButton') }}
      </button>
    </div>
    <button type="button" class="secondary" :disabled="modelValue.length >= 20" @click="add()">
      ＋ {{ t('addRow') }}
    </button>
  </section>
</template>

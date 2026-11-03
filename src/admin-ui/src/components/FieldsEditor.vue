<script setup lang="ts">
import { ref, watch } from 'vue'
import type { Document, Schemas } from '../types'
import { identifier } from '../types'
import { t } from '../i18n'
import ValueEditor from './ValueEditor.vue'
import DataShapeEditor from './DataShapeEditor.vue'
const props = defineProps<{ document: Document }>()
const name = ref('')
const outputName = ref(''),
  outcomeName = ref('')
watch(
  () => JSON.stringify(props.document.fields),
  () => {
    for (const key of Object.keys(props.document.inputs ?? {})) {
      const field = props.document.fields?.[key]
      if (field) props.document.inputs![key] = { ...field }
      else delete props.document.inputs![key]
    }
  },
)
function remove(key: string) {
  delete props.document.fields?.[key]
  delete props.document.initial_data?.[key]
  delete props.document.inputs?.[key]
}
function shape(key: string, value: Schemas['DataField'], output = false) {
  if (value.type === 'list' || value.type === 'object' || value.type === 'secret')
    props.document.schema_version = 2
  if (output) (props.document.outputs ??= {})[key] = value
  else (props.document.fields ??= {})[key] = value
}
function add() {
  if (!identifier.test(name.value) || name.value in (props.document.fields ?? {})) return
  ;(props.document.fields ??= {})[name.value] = { type: 'text', nullable: false }
  name.value = ''
}
function input(key: string, enabled: boolean) {
  props.document.schema_version = 2
  if (enabled) (props.document.inputs ??= {})[key] = { ...props.document.fields![key] }
  else delete props.document.inputs?.[key]
}
function addOutput() {
  const key = outputName.value
  if (!identifier.test(key) || key in (props.document.outputs ?? {})) return
  props.document.schema_version = 2
  ;(props.document.outputs ??= {})[key] = { type: 'text', nullable: false }
  outputName.value = ''
}
function addOutcome() {
  const key = outcomeName.value
  if (!identifier.test(key) || (props.document.outcomes ?? ['completed']).includes(key)) return
  props.document.schema_version = 2
  ;(props.document.outcomes ??= ['completed']).push(key)
  outcomeName.value = ''
}
function changeOutcome(index: number, value: string) {
  props.document.schema_version = 2
  ;(props.document.outcomes ??= ['completed'])[index] = value
}
function removeOutcome(index: number) {
  if ((props.document.outcomes ?? ['completed']).length <= 1) return
  props.document.schema_version = 2
  props.document.outcomes!.splice(index, 1)
}
</script>
<template>
  <div class="fields-editor stack">
    <label
      >{{ t('studyEntry')
      }}<select
        :value="document.navigation_entries?.study ?? ''"
        @change="
          ($event.target as HTMLSelectElement).value
            ? ((document.navigation_entries ??= {}).study = ($event.target as HTMLSelectElement).value)
            : delete document.navigation_entries?.study
        "
      >
        <option value="">—</option>
        <option v-for="node in document.nodes.filter((node) => node.kind === 'menu')" :key="node.id">
          {{ node.id }}
        </option>
      </select></label
    >
    <div v-for="(field, key) in document.fields ?? {}" :key="key" class="binding stack">
      <div class="row between">
        <code>{{ key }}</code
        ><button
          type="button"
          class="icon-button danger"
          :aria-label="t('remove') + ' ' + key"
          @click="remove(key)"
        >
          ×
        </button>
      </div>
      <DataShapeEditor :model-value="field" @update:model-value="shape(key, $event)" />
      <label class="check"
        ><input
          type="checkbox"
          :checked="key in (document.initial_data ?? {})"
          @change="
            ($event.target as HTMLInputElement).checked
              ? ((document.initial_data ??= {})[key] = null)
              : delete document.initial_data?.[key]
          "
        />{{ t('initial') }}</label
      >
      <ValueEditor
        v-if="key in (document.initial_data ?? {})"
        :model-value="{ kind: 'literal', value: document.initial_data![key] }"
        @update:model-value="
          $event.kind === 'literal' ? ((document.initial_data ??= {})[key] = $event.value) : null
        "
      />
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
        :disabled="!identifier.test(name) || name in (document.fields ?? {})"
        @click="add"
      >
        ＋ {{ t('addField') }}
      </button>
    </div>
    <details>
      <summary>{{ t('scenarioInputs') }}</summary>
      <div class="stack">
        <label v-for="(field, key) in document.fields ?? {}" :key="key" class="check">
          <input
            type="checkbox"
            :checked="key in (document.inputs ?? {})"
            @change="input(key, ($event.target as HTMLInputElement).checked)"
          />
          <code>{{ key }}</code> · {{ field.type }}{{ field.nullable ? '?' : '' }}
        </label>
      </div>
    </details>
    <details>
      <summary>{{ t('scenarioOutputs') }}</summary>
      <div class="stack">
        <div v-for="(field, key) in document.outputs ?? {}" :key="key" class="binding stack">
          <div class="row between">
            <code>{{ key }}</code>
            <button
              type="button"
              class="icon-button danger"
              :aria-label="t('remove') + ' ' + key"
              @click="delete document.outputs?.[key]"
            >
              ×
            </button>
          </div>
          <DataShapeEditor :model-value="field" @update:model-value="shape(key, $event, true)" />
        </div>
        <div class="row">
          <input
            v-model="outputName"
            :aria-label="t('scenarioOutputs') + ': ' + t('field')"
            :placeholder="t('field')"
            @keydown.enter.prevent="addOutput"
          />
          <button
            type="button"
            class="small"
            :disabled="!identifier.test(outputName) || outputName in (document.outputs ?? {})"
            @click="addOutput"
          >
            ＋ {{ t('addField') }}
          </button>
        </div>
      </div>
    </details>
    <details>
      <summary>{{ t('scenarioOutcomes') }}</summary>
      <div class="stack">
        <div v-for="(outcome, index) in document.outcomes ?? ['completed']" :key="index" class="row">
          <input
            :value="outcome"
            :aria-label="t('outcome') + ' ' + (index + 1)"
            pattern="[a-z][a-z0-9_]{0,31}"
            required
            @input="changeOutcome(index, ($event.target as HTMLInputElement).value)"
          />
          <button
            type="button"
            class="icon-button danger"
            :aria-label="t('remove') + ' ' + outcome"
            :disabled="(document.outcomes ?? ['completed']).length <= 1"
            @click="removeOutcome(index)"
          >
            ×
          </button>
        </div>
        <div class="row">
          <input
            v-model="outcomeName"
            :aria-label="t('scenarioOutcomes') + ': ' + t('outcome')"
            :placeholder="t('outcome')"
            @keydown.enter.prevent="addOutcome"
          />
          <button
            type="button"
            class="small"
            :disabled="
              !identifier.test(outcomeName) ||
              (document.outcomes ?? ['completed']).includes(outcomeName) ||
              (document.outcomes ?? ['completed']).length >= 32
            "
            @click="addOutcome"
          >
            ＋ {{ t('outcome') }}
          </button>
        </div>
      </div>
    </details>
  </div>
</template>

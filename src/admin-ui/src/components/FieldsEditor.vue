<script setup lang="ts">
import { ref } from 'vue'
import type { Document } from '../types'
import { identifier } from '../types'
import { t } from '../i18n'
import ValueEditor from './ValueEditor.vue'
const props = defineProps<{ document: Document }>()
const name = ref('')
function remove(key: string) {
  delete props.document.fields?.[key]
  delete props.document.initial_data?.[key]
}
function add() {
  if (!identifier.test(name.value) || name.value in (props.document.fields ?? {})) return
  ;(props.document.fields ??= {})[name.value] = { type: 'text', nullable: false }
  name.value = ''
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
      <select v-model="field.type" :aria-label="t('type')">
        <option>text</option>
        <option>integer</option>
        <option>number</option>
        <option>boolean</option>
      </select>
      <label class="check"><input v-model="field.nullable" type="checkbox" />{{ t('nullable') }}</label>
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
  </div>
</template>

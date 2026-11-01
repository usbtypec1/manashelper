<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { AdminApi } from '../api'
import type { Document, Locale, Theme, Scalar, Schemas } from '../types'
import { clone, locales } from '../types'
import { t, uiLocale } from '../i18n'
import ValueEditor from './ValueEditor.vue'
import TelegramText from './TelegramText.vue'
const props = defineProps<{
  document: Document
  api: AdminApi
  delegates: Schemas['DelegateDefinition'][]
  catalog: Schemas['EditorCatalog']
}>()
const emit = defineEmits<{ failure: [unknown]; select: [string] }>()
const locale = ref<Locale>(uiLocale.value),
  theme = ref<Theme>('basic')
const userId = ref(1),
  eders = ref(Boolean(props.catalog.capabilities.eders_enabled))
const result = ref<Schemas['PreviewResult'] | null>(null),
  busy = ref(false),
  input = ref('')
const stubs = ref<Record<string, Schemas['PreviewDelegateResult']>>({})
const data = ref<Record<string, Scalar>>({})
const node = computed(() => props.document.nodes.find((node) => node.id === result.value?.node_id))
const used = computed(() =>
  props.delegates.filter((item) =>
    props.document.nodes.some((node) => node.kind === 'action' && node.delegate === item.id),
  ),
)
const finished = computed(() => node.value?.kind === 'end' && !!result.value?.screen)
watch(
  () => JSON.stringify(props.document),
  () => {
    result.value = null
    data.value = {}
  },
)
watch([locale, theme, userId, eders], () => {
  result.value = null
})
watch(
  () => JSON.stringify([data.value, stubs.value]),
  () => {
    result.value = null
  },
)
function stub(definition: Schemas['DelegateDefinition'], enabled: boolean) {
  if (!enabled) {
    delete stubs.value[definition.id]
    return
  }
  const defaults: Record<string, Scalar> = { text: '', integer: 0, number: 0, boolean: false }
  stubs.value[definition.id] = {
    outcome: definition.outcomes[0],
    values: Object.fromEntries(
      Object.entries(definition.outputs ?? {}).map(([name, field]) => [
        name,
        field.nullable ? null : defaults[field.type],
      ]),
    ),
  }
}
async function run(kind?: 'button' | 'input', button?: string) {
  if (busy.value) return
  busy.value = true
  try {
    const body: Schemas['PreviewRequest'] = {
      document: clone(props.document),
      user: { id: userId.value, chat_id: userId.value, locale: locale.value, theme: theme.value },
      eders_enabled: eders.value,
      delegate_results: clone(stubs.value),
      data: clone(result.value?.data ?? data.value),
      node_id: result.value?.node_id ?? null,
    }
    if (kind) {
      const identity = {
        update_id: 1,
        user_id: userId.value,
        chat_id: userId.value,
        session_id: 'preview',
        expected_revision: 0,
      }
      body.event =
        kind === 'button'
          ? { ...identity, kind, button_id: button! }
          : { ...identity, kind, text: input.value }
    }
    const response = await props.api.request<Schemas['PreviewResult']>(
      `/flows/${props.document.id}/preview`,
      'POST',
      body,
    )
    result.value = response
    if (!response.issues.length) emit('select', response.node_id)
    input.value = ''
  } catch (error) {
    emit('failure', error)
  } finally {
    busy.value = false
  }
}
function restart() {
  result.value = null
  void run()
}
</script>
<template>
  <div class="preview-pane stack">
    <p class="hint">{{ t('previewHint') }}</p>
    <div class="row">
      <label
        >{{ t('locale')
        }}<select v-model="locale">
          <option v-for="code in locales" :key="code">{{ code }}</option>
        </select></label
      ><label
        >{{ t('theme')
        }}<select v-model="theme">
          <option value="basic">{{ t('basic') }}</option>
          <option value="halloween">{{ t('halloween') }}</option>
        </select></label
      >
    </div>
    <details>
      <summary>{{ t('previewContext') }}</summary>
      <div class="stack">
        <label>{{ t('userId') }}<input v-model.number="userId" type="number" min="1" required /></label>
        <label class="check"><input v-model="eders" type="checkbox" />{{ t('edersEnabled') }}</label>
        <div v-for="(_, field) in document.fields ?? {}" :key="field" class="binding">
          <label class="check"
            ><input
              type="checkbox"
              :checked="field in data"
              @change="
                ($event.target as HTMLInputElement).checked ? (data[field] = null) : delete data[field]
              "
            />{{ field }}</label
          ><ValueEditor
            v-if="field in data"
            :model-value="{ kind: 'literal', value: data[field] }"
            @update:model-value="
              (value) => {
                if (value.kind === 'literal') {
                  data[field] = value.value
                  result = null
                }
              }
            "
          />
        </div>
      </div>
    </details>
    <details v-if="used.length" open>
      <summary>{{ t('stubs') }}</summary>
      <p class="hint">{{ t('stubHint') }}</p>
      <div v-for="item in used" :key="item.id" class="binding">
        <label class="check"
          ><input
            type="checkbox"
            :checked="item.id in stubs"
            @change="stub(item, ($event.target as HTMLInputElement).checked)"
          /><code>{{ item.id }}</code></label
        >
        <template v-if="stubs[item.id]"
          ><select v-model="stubs[item.id].outcome" :aria-label="t('outcome')">
            <option v-for="outcome in item.outcomes" :key="outcome">{{ outcome }}</option>
          </select>
          <label v-for="(_, field) in item.outputs ?? {}" :key="field"
            >{{ field
            }}<ValueEditor
              :model-value="{ kind: 'literal', value: stubs[item.id].values?.[field] ?? null }"
              @update:model-value="
                (value) => {
                  if (value.kind === 'literal') {
                    ;(stubs[item.id].values ??= {})[field] = value.value
                    result = null
                  }
                }
              "
          /></label>
        </template>
      </div>
    </details>
    <button type="button" class="secondary" :disabled="busy" @click="restart">▷ {{ t('reset') }}</button>
    <div v-if="result?.issues.length" class="notice error">
      <p v-for="issue in result.issues" :key="issue.path + issue.code">
        <code>{{ issue.code }}</code> · {{ issue.path }}
      </p>
    </div>
    <div v-if="result?.screen" class="phone-preview">
      <div class="phone-title">
        <span class="avatar">M</span>
        <div>
          <strong>Manashelper</strong><small>{{ result.node_id }}</small>
        </div>
        <span class="online-dot" />
      </div>
      <div class="chat-surface">
        <div class="message-bubble"><TelegramText :text="result.screen.text" /></div>
        <div v-for="(row, index) in result.screen.buttons" :key="index" class="preview-button-row">
          <button
            v-for="button in row"
            :key="button.id"
            type="button"
            :title="button.url ?? ''"
            :disabled="busy || !!button.url || finished"
            @click="run('button', button.id)"
          >
            {{ button.label }}<span v-if="button.url"> ↗</span>
          </button>
        </div>
        <div v-if="finished" class="hint centered">
          {{ result.screen.feature ? t('handoff') + ': ' + result.screen.feature : t('previewStopped') }}
          <p v-if="result.screen.return_flow">{{ t('returnFlow') }}: {{ result.screen.return_flow }}</p>
        </div>
      </div>
      <form v-if="node?.kind === 'input' && !finished" class="preview-input" @submit.prevent="run('input')">
        <input v-model="input" :aria-label="t('input')" :disabled="busy" /><button
          type="submit"
          :disabled="busy"
          :aria-label="t('send')"
        >
          ➤
        </button>
      </form>
    </div>
  </div>
</template>

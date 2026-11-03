<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { AdminApi, ApiError } from '../api'
import { clone, type Schemas } from '../types'
import { t, type CopyKey } from '../i18n'

const props = defineProps<{
  api: AdminApi
  flows: Schemas['FlowSummary'][]
  ask: (key: CopyKey, detail?: string) => Promise<boolean>
}>()
const emit = defineEmits<{ dirty: [boolean]; failure: [unknown] }>()
const draft = ref<Schemas['TriggerDraftContent'] | null>(null)
const versions = ref<Schemas['TriggerReleaseContent'][]>([])
const saved = ref(''),
  selected = ref(0),
  busy = ref(false)
const error = ref<CopyKey | null>(null),
  issues = ref<Schemas['ContractIssue'][]>([])
const form = ref<HTMLFormElement | null>(null)
const binding = computed(() => draft.value?.document.bindings[selected.value])
const dirty = computed(() => !!draft.value && JSON.stringify(draft.value.document) !== saved.value)
watch(dirty, (value) => emit('dirty', value), { immediate: true })
const publishedFlows = computed(() => props.flows.filter((flow) => flow.published_version))
const editableMatcher = computed(
  () => binding.value?.target.kind === 'scenario' && !binding.value.fallback_adapter,
)
const sources = [
  ['argument', 'triggerArgumentField'],
  ['actor_id', 'triggerActorField'],
  ['chat_id', 'triggerChatField'],
] as const
function field(source: (typeof sources)[number][0]) {
  if (binding.value?.target.kind !== 'scenario') return ''
  return Object.entries(binding.value.target.arguments ?? {}).find(([, value]) => value === source)?.[0] ?? ''
}
function setField(source: (typeof sources)[number][0], event: Event) {
  if (binding.value?.target.kind !== 'scenario') return
  const fields = (binding.value.target.arguments ??= {})
  for (const [key, value] of Object.entries(fields)) if (value === source) delete fields[key]
  const key = (event.target as HTMLInputElement).value.trim()
  if (key) fields[key] = source
}
function failed(failure: unknown) {
  error.value = failure instanceof ApiError && failure.status === 409 ? 'conflict' : 'requestFailed'
  issues.value = failure instanceof ApiError ? failure.issues : []
  const index = issues.value[0]?.path.match(/^\/bindings\/(\d+)/)?.[1]
  if (index) selected.value = Number(index)
  emit('failure', failure)
}
async function load() {
  if (dirty.value && !(await props.ask('discardChanges'))) return
  busy.value = true
  try {
    const [value, releases] = await Promise.all([
      props.api.request<Schemas['TriggerDraftContent']>('/triggers'),
      props.api.request<Schemas['TriggerVersions']>('/triggers/releases'),
    ])
    draft.value = value
    saved.value = JSON.stringify(value.document)
    versions.value = releases.items
    selected.value = Math.min(selected.value, Math.max(0, value.document.bindings.length - 1))
    error.value = null
    issues.value = []
  } catch (failure) {
    failed(failure)
  } finally {
    busy.value = false
  }
}
async function save() {
  if (!draft.value || !form.value?.reportValidity()) return
  busy.value = true
  try {
    const value = await props.api.request<Schemas['TriggerDraftContent']>('/triggers', 'PUT', {
      document: clone(draft.value.document),
      expected_revision: draft.value.revision,
    })
    draft.value = value
    saved.value = JSON.stringify(value.document)
    error.value = null
    issues.value = []
  } catch (failure) {
    failed(failure)
  } finally {
    busy.value = false
  }
}
async function publish() {
  if (!draft.value || dirty.value || !(await props.ask('triggerPublishConfirm'))) return
  busy.value = true
  try {
    await props.api.request('/triggers/publish', 'POST', { expected_revision: draft.value.revision })
    await load()
  } catch (failure) {
    failed(failure)
  } finally {
    busy.value = false
  }
}
async function activate(release: number) {
  if (!draft.value || !(await props.ask('triggerActivateConfirm', 'v' + release))) return
  busy.value = true
  try {
    const value = await props.api.request<Schemas['TriggerDraftContent']>('/triggers/activate', 'POST', {
      release_id: release,
      expected_current_release: draft.value.current_release,
    })
    // Activation changes admission only; keep the operator's unsaved document.
    draft.value.current_release = value.current_release
    error.value = null
  } catch (failure) {
    failed(failure)
  } finally {
    busy.value = false
  }
}
function add() {
  if (!draft.value) return
  let count = 1
  while (draft.value.document.bindings.some((item) => item.id === 'entry_' + count)) count++
  draft.value.document.bindings.push({
    id: 'entry_' + count,
    matcher: { kind: 'command', key: 'entry_' + count, arguments: 'none' },
    target: { kind: 'scenario', flow_id: publishedFlows.value[0]?.id ?? '', arguments: {} },
    policy: 'reject_if_busy',
    scope: 'private',
    access: 'public',
    capabilities: [],
  })
  selected.value = draft.value.document.bindings.length - 1
}
async function remove() {
  if (!draft.value || !(await props.ask('triggerRemoveConfirm', binding.value?.id))) return
  draft.value.document.bindings.splice(selected.value, 1)
  selected.value = Math.max(0, selected.value - 1)
}
onMounted(load)
</script>

<template>
  <section class="trigger-editor" data-testid="trigger-editor">
    <header class="row between">
      <div>
        <h1>{{ t('triggers') }}</h1>
        <p>{{ t('triggerHint') }}</p>
        <span v-if="draft" class="pill"
          >r{{ draft.revision }} · {{ t('textCurrentRelease') }}
          {{ draft.current_release ? 'v' + draft.current_release : '—' }}</span
        >
      </div>
      <div class="row">
        <button type="button" :disabled="busy" @click="load">{{ t('reload') }}</button>
        <button type="button" :disabled="busy || !draft" @click="save">{{ t('save') }}</button>
        <button type="button" class="primary" :disabled="busy || dirty || !draft" @click="publish">
          {{ t('publish') }}
        </button>
      </div>
    </header>
    <div v-if="error" role="alert" class="notice-bar error">
      {{ t(error) }}
      <ul>
        <li v-for="issue in issues" :key="issue.path + issue.code">{{ issue.message }} · {{ issue.path }}</li>
      </ul>
    </div>
    <span class="pill">{{ dirty ? t('unsaved') : t('saved') }}</span>
    <div class="trigger-body">
      <nav :aria-label="t('triggers')">
        <button
          type="button"
          :disabled="busy || !publishedFlows.length || (draft?.document.bindings.length ?? 0) >= 256"
          @click="add"
        >
          {{ t('triggerAdd') }}
        </button>
        <button
          v-for="(item, index) in draft?.document.bindings"
          :key="index"
          type="button"
          :class="{ active: selected === index }"
          :disabled="busy"
          @click="selected = index"
        >
          {{ item.id }}
        </button>
      </nav>
      <form ref="form" class="trigger-form" @submit.prevent="save">
        <template v-if="binding">
          <label class="field"
            >{{ t('triggerId')
            }}<input
              v-model="binding.id"
              pattern="[a-z][a-z0-9_]{0,63}"
              required
              :disabled="busy || !editableMatcher"
          /></label>
          <fieldset :disabled="busy || !editableMatcher">
            <label class="field"
              >{{ t('triggerMatcher')
              }}<select v-model="binding.matcher.kind">
                <option value="command">{{ t('triggerCommand') }}</option>
                <option value="deep_link">{{ t('triggerDeepLink') }}</option>
                <option value="prefix">{{ t('triggerPrefix') }}</option>
                <option value="reply_label">{{ t('triggerReplyLabel') }}</option>
                <option v-if="binding.matcher.kind === 'callback'" value="callback">{{ t('inline') }}</option>
                <option v-if="binding.matcher.kind === 'native_reply'" value="native_reply">
                  {{ t('reply') }}
                </option>
              </select></label
            >
            <label class="field"
              >{{ t('triggerKey') }}<input v-model="binding.matcher.key" required maxlength="120"
            /></label>
            <label class="field"
              >{{ t('arguments')
              }}<select v-model="binding.matcher.arguments">
                <option value="none">{{ t('triggerNoArgument') }}</option>
                <option value="text">{{ t('text') }}</option>
                <option value="uuid">UUID</option>
                <option v-if="binding.matcher.arguments === 'flow_id'" value="flow_id">
                  {{ t('flowId') }}
                </option>
              </select></label
            >
          </fieldset>
          <template v-if="binding.target.kind === 'scenario'">
            <fieldset :disabled="busy">
              <label class="field"
                >{{ t('triggerTarget')
                }}<select v-model="binding.target.flow_id" required>
                  <option v-for="flow in publishedFlows" :key="flow.id" :value="flow.id">
                    {{ flow.id }}
                  </option>
                </select></label
              >
              <label class="field"
                >{{ t('entry')
                }}<input
                  :value="binding.target.entry ?? ''"
                  pattern="[a-z][a-z0-9_]{0,31}"
                  @input="binding.target.entry = ($event.target as HTMLInputElement).value || null"
              /></label>
              <label class="field"
                >{{ t('triggerAccess')
                }}<select v-model="binding.access">
                  <option value="public">{{ t('allUsers') }}</option>
                  <option value="admin">{{ t('adminOnly') }}</option>
                </select></label
              >
              <label class="field"
                >{{ t('triggerPolicy')
                }}<select v-model="binding.policy">
                  <option value="reject_if_busy">{{ t('triggerRejectBusy') }}</option>
                  <option value="resume">{{ t('triggerResume') }}</option>
                  <option value="replace">{{ t('triggerReplace') }}</option>
                  <option value="call">{{ t('triggerCall') }}</option>
                </select></label
              >
              <label v-for="[source, label] in sources" :key="source" class="field"
                >{{ t(label)
                }}<input
                  :value="field(source)"
                  pattern="[a-z][a-z0-9_]{0,31}"
                  @input="setField(source, $event)"
              /></label>
            </fieldset>
            <button v-if="editableMatcher" type="button" :disabled="busy" @click="remove">
              {{ t('remove') }}
            </button>
          </template>
          <p v-else>
            {{ t('triggerLegacy') }} <code>{{ binding.target.adapter }}</code>
          </p>
        </template>
      </form>
    </div>
    <details v-if="draft">
      <summary>{{ t('triggerReleases') }}</summary>
      <div v-for="release in versions" :key="release.id" class="row">
        <span>v{{ release.id }} · r{{ release.draft_revision }} · {{ release.published_at }}</span>
        <button
          type="button"
          :disabled="busy || release.id === draft.current_release"
          @click="activate(release.id)"
        >
          {{ t('activate') }}
        </button>
      </div>
    </details>
  </section>
</template>

<style scoped>
.trigger-editor {
  padding: 20px;
  overflow: auto;
  flex: 1;
  min-height: 0;
  min-width: 0;
}
.trigger-editor p {
  color: var(--muted);
}
.trigger-body {
  display: grid;
  grid-template-columns: minmax(150px, 270px) minmax(0, 1fr);
  gap: 20px;
  margin: 16px 0;
}
nav {
  display: flex;
  flex-direction: column;
  max-height: 65vh;
  overflow: auto;
}
nav button {
  text-align: left;
  justify-content: flex-start;
  overflow-wrap: anywhere;
}
nav .active {
  background: var(--accent-wash);
}
.trigger-form {
  min-width: 0;
  max-width: 900px;
}
fieldset {
  border: 0;
  padding: 0;
  margin: 0;
}
@media (max-width: 650px) {
  .trigger-editor > header {
    display: block;
  }
  .trigger-editor > header > .row {
    flex-wrap: wrap;
    margin-top: 12px;
  }
  .trigger-body {
    grid-template-columns: minmax(0, 1fr);
  }
  nav {
    max-height: 160px;
  }
}
</style>
